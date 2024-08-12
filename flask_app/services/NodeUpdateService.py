from datetime import datetime
import logging
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from langchain_community.graphs.graph_document import GraphDocument

from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.shared.common_fn import load_embedding_model, embed_name
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.RunpodService import RunpodService
from flask_app.services.Neo4jQueueManager import queued_transaction
from flask_app.constants import COMMUNITY_DETECTION, COURSEID, LOUVAIN, NOTEID, PAGERANK, USERID

class NodeUpdateService:
    @staticmethod
    def update_embeddings(noteId: str, nodes_data) -> None:
        embeddings, dimension = load_embedding_model()

        nodes_to_update = []
        futures = []

        with ThreadPoolExecutor(max_workers=200) as executor:
            for node in nodes_data:
                name = node['id']
                futures.append(
                    executor.submit(
                        embed_name,
                        name=name,
                        embeddings=embeddings
                    ))

            for future in concurrent.futures.as_completed(futures):
                name, embedding = future.result()

                nodes_to_update.append({'id': name, 'embedding': embedding})

        update_query = """
        UNWIND $nodes AS node
        MATCH (n:Concept)
        WHERE $noteId IN n.noteId AND n.id = node.id
        SET n.embedding = node.embedding
        RETURN count(n) as updatedCount
        """

        graphAccess = graphDBdataAccess()

        update_result = graphAccess.execute_query(update_query, {'nodes': nodes_to_update, NOTEID: noteId})
        logging.info(f"Updated nodes: {update_result}")

        return dimension

    @staticmethod
    def create_embedding_index(dimension: int) -> None:
        index_query = f"""
        CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
        FOR (n:Concept)
        ON (n.embedding)
        OPTIONS {{indexConfig: {{
        `vector.dimensions`: {dimension},
        `vector.similarity_function`: 'cosine'
        }}}}
        """

        graphAccess = graphDBdataAccess()

        graphAccess.execute_query(index_query)

        logging.info("Created or updated embedding index")
    
    @staticmethod
    def update_graph_documents(
        graph_document_list: List[GraphDocument], 
        graphAccess: graphDBdataAccess,
        noteId: str = None, 
        courseId: str = None, 
        userId: str = None
    ):
        try:
            nodes_data = []
            relationships_data = []

            for graph_document in graph_document_list:
                for node in graph_document.nodes:
                    node_data = {
                        "id": node.id,
                        "type": node.type,
                        'uuid': [node.properties['uuid']],
                        COURSEID: [courseId],
                        USERID: [userId],
                        NOTEID: [noteId]
                    }
                    nodes_data.append(node_data)

                for relationship in graph_document.relationships:
                    relationships_data.append({
                        "type": relationship.type,
                        'source_uuid': [relationship.source.properties['uuid']],
                        'target_uuid': [relationship.target.properties['uuid']],
                    })

            node_query = """
            UNWIND $nodes AS node
            MERGE (n:Concept {uuid: node.uuid})
            ON CREATE SET 
                n.id = node.id,
                n.type = node.type,
                n.courseId = node.courseId,
                n.userId = node.userId,
                n.uuid = node.uuid,
                n.noteId = node.noteId
            """

            relationship_query = """
            UNWIND $relationships AS rel
            MATCH (source:Concept {uuid: rel.source_uuid})
            MATCH (target:Concept {uuid: rel.target_uuid})
            MERGE (source)-[r:RELATED {type: rel.type}]->(target)
            """

            graphAccess.execute_query(node_query, {"nodes": nodes_data})
            graphAccess.execute_query(relationship_query, {"relationships": relationships_data})

            return nodes_data
        except Exception as e:
            logging.exception(f"Error in update_graph_documents: {e}")
            logging.exception("#############################################################################################")


    @queued_transaction(task_type='pagerank')
    def update_page_rank(tx, id_type: str, target_id: str, note_id: str) -> Dict:
        page_rank_string = GraphQueryService.get_page_rank_string(param=id_type, id=target_id)

        # Query to get the graph data
        query = f"""
        MATCH (n)
        WHERE n:Concept AND "{target_id}" IN n.{id_type}
        WITH n
        OPTIONAL MATCH (n)-[:RELATED]-(m)
        WHERE m:Concept AND "{target_id}" IN m.{id_type}
        RETURN id(n) AS id, collect(distinct id(m)) AS relations
        """

        result = tx.run(query)
        graph_data = [{"id": record["id"], "relations": record["relations"]} for record in result]

        if not graph_data:
            logging.info(f"No nodes found for {id_type}: {target_id}")
            return {"updatedNodes": 0, "nodeCount": 0}

        # Run PageRank using RunPod
        page_ranks = RunpodService.run_gds(
            graph=graph_data,
            algorithm_type=PAGERANK,
            algorithm=PAGERANK
        )

        if page_ranks is None:
            logging.error(f"PageRank calculation failed for {id_type}: {target_id}")
            return {"updatedNodes": 0, "nodeCount": 0}

        # Update nodes with PageRank scores
        update_query = f"""
        UNWIND $pageRanks AS pageRank
        MATCH (n:Concept)
        WHERE id(n) = pageRank.id
        SET n.{page_rank_string} = pageRank.score
        """

        update_params = {
            "pageRanks": [{"id": int(node_id), "score": score} 
                        for node_id, score in page_ranks.items()]
        }

        update_result = tx.run(update_query, update_params)
        
        stats = {
            "updatedNodes": update_result.consume().counters.properties_set,
            "nodeCount": len(page_ranks)
        }
        
        logging.info(f"Updated PageRank for {id_type}: {target_id}")
        logging.info(f"PageRank stats: {stats}")

        return stats

    @queued_transaction(task_type='community')
    def update_communities_for_param(tx, id_type: str, target_id: str, note_id: str) -> Dict:
        com_string = GraphQueryService.get_com_string(communityType=id_type, communityId=target_id)

        # Query to get the graph data
        query = f"""
        MATCH (n)
        WHERE (n:{' OR n:'.join(['Concept', 'Chunk', 'Document'])}) AND "{target_id}" IN n.{id_type}
        WITH n
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE (m:{' OR m:'.join(['Concept', 'Chunk', 'Document'])}) AND "{target_id}" IN m.{id_type}
        RETURN id(n) AS id, collect(distinct id(m)) AS relations
        """

        result = tx.run(query)
        graph_data = [{"id": record["id"], "relations": record["relations"]} for record in result]

        if not graph_data:
            logging.info(f"No nodes found for {id_type}: {target_id}")
            return {"updatedNodes": 0, "communityCount": 0}

        # Run community detection using RunPod
        communities = RunpodService.run_gds(
            graph=graph_data,
            algorithm_type=COMMUNITY_DETECTION,
            algorithm=LOUVAIN
        )

        if communities is None:
            logging.error(f"Community detection failed for {id_type}: {target_id}")
            return {"updatedNodes": 0, "communityCount": 0}

        # Update nodes with community information
        update_query = f"""
        UNWIND $communities AS community
        MATCH (n)
        WHERE id(n) = community.id
        SET n.{com_string} = community.community
        """

        update_params = {
            "communities": [{"id": int(node_id), "community": community} 
                            for node_id, community in communities.items()]
        }

        update_result = tx.run(update_query, update_params)
        
        stats = {
            "updatedNodes": update_result.consume().counters.properties_set,
            "communityCount": len(set(communities.values()))
        }
        
        logging.info(f"Updated communities for {id_type}: {target_id}")
        logging.info(f"Community stats: {stats}")

        return stats
    

    @staticmethod
    @queued_transaction(task_type='merge')
    def merge_similar_nodes(tx, id_type: str, target_id: str, note_id: str, distance: int = 2, embedding_cutoff: float = 0.95) -> None:
        logging.info(f"Merging similar nodes for {id_type}: {target_id}")
        start = datetime.now()
        logging.info(f"Starting at {start}")

        query = f"""
        MATCH (e:Concept)
        WHERE e.embedding IS NOT NULL AND size(e.uuid) > 0 AND '{target_id}' IN e.{id_type}
        CALL {{
        WITH e
        CALL db.index.vector.queryNodes('concept_embedding', 50, e.embedding)
        YIELD node, score
        WITH node, score
        WHERE score > toFloat($embedding_cutoff) AND size(node.uuid) > 0
        WITH collect({{id: node.id, uuid: node.uuid[0]}}) AS nodes
        UNWIND nodes AS n1
        WITH n1, nodes
        UNWIND nodes AS n2
        WITH n1, n2
        WHERE n1.id <= n2.id
        WITH n1, n2, apoc.text.levenshteinDistance(n1.id, n2.id) AS dist
        WHERE dist <= $distance
        WITH n1, collect(n2) AS similar_nodes
        RETURN n1.id AS base_word, similar_nodes AS group
        }}
        RETURN base_word, group
        """

        logging.info(f"Query: {query}")

        result = tx.run(query, {'distance': distance, 'embedding_cutoff': embedding_cutoff})

        combined_words = []
        for record in result:
            base_word = record['base_word']
            group = record['group']
            if len(group) > 1:  # Only include groups with more than one word
                combined_words.append({base_word: group})

        # Merge the nodes
        for merge_group in combined_words:
            for final_label, entities in merge_group.items():
                primary_node = entities[0]
                
                merge_query = """
                MATCH (primary:Concept)
                WHERE $primary_uuid IN primary.uuid
                UNWIND $other_uuids AS other_uuid
                MATCH (other:Concept)
                WHERE other_uuid IN other.uuid AND other <> primary
                WITH primary, other, 
                    apoc.map.removeKeys(primary, ['id', 'userId', 'noteId', 'courseId', 'uuid']) AS primary_props,
                    apoc.map.removeKeys(other, ['id', 'userId', 'noteId', 'courseId', 'uuid']) AS other_props

                // Merge list properties
                WITH primary, other, primary_props, other_props,
                    CASE WHEN primary.userId IS NULL THEN [] ELSE primary.userId END + 
                    CASE WHEN other.userId IS NULL THEN [] ELSE other.userId END AS merged_userId,
                    CASE WHEN primary.noteId IS NULL THEN [] ELSE primary.noteId END + 
                    CASE WHEN other.noteId IS NULL THEN [] ELSE other.noteId END AS merged_noteId,
                    CASE WHEN primary.courseId IS NULL THEN [] ELSE primary.courseId END + 
                    CASE WHEN other.courseId IS NULL THEN [] ELSE other.courseId END AS merged_courseId,
                    CASE WHEN primary.uuid IS NULL THEN [] ELSE primary.uuid END + 
                    CASE WHEN other.uuid IS NULL THEN [] ELSE other.uuid END AS merged_uuid

                // Merge other properties
                WITH primary, other, primary_props, other_props, merged_userId, merged_noteId, merged_courseId, merged_uuid,
                    apoc.map.mergeList([primary_props, other_props]) AS merged_props

                // Set properties on primary node
                SET primary = merged_props,
                    primary.id = $final_label,
                    primary.userId = apoc.coll.toSet(merged_userId),
                    primary.noteId = apoc.coll.toSet(merged_noteId),
                    primary.courseId = apoc.coll.toSet(merged_courseId),
                    primary.uuid = apoc.coll.toSet(merged_uuid)

                // Use WITH clause before CALL
                WITH primary, other

                // Merge relationships
                CALL apoc.refactor.mergeNodes([primary, other], {properties: "discard", mergeRels: true})
                YIELD node

                RETURN node
                """
                
                merge_params = {
                    "primary_uuid": primary_node['uuid'],
                    "other_uuids": [e['uuid'] for e in entities[1:]],
                    "final_label": final_label
                }
                
                try:
                    result = tx.run(merge_query, merge_params)
                    result.consume()  # Ensure the query is executed
                    
                except Exception as e:
                    logging.error(f"Error merging nodes {entities}: {str(e)}")
                    # Continue with the next merge instead of raising the exception

        logging.info("Node merging process completed.")
        end = datetime.now()
        logging.info(f"Ending at {end}")
        logging.info(f"Query took: {end - start}")