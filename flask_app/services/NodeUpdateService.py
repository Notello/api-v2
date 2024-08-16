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
from flask_app.src.CustomKGBuilder import KnowledgeGraph
from flask_app.services.Neo4jQueueManager import queued_transaction
from flask_app.constants import COMMUNITY_DETECTION, COURSEID, LOUVAIN, NOTEID, PAGERANK, USERID
from nltk.stem import WordNetLemmatizer


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
        graph_document,
        graphAccess: graphDBdataAccess,
    ):
        try:
            nodes = graph_document['nodes']
            rels = graph_document['relationships']

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

            graphAccess.execute_query(node_query, {"nodes": nodes})
            graphAccess.execute_query(relationship_query, {"relationships": rels})

            return graph_document['nodes']
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

        # Step 1: Identify all nodes with the given conditions
        NODE_QUERY = f"""
        MATCH (n:Concept)
        WHERE '{target_id}' IN n.{id_type}
        WITH n
        MATCH (other:Concept)
        WHERE '{target_id}' IN other.{id_type} AND n.uuid[0] <> other.uuid[0]
        AND (
            (n.embedding IS NOT NULL AND other.embedding IS NOT NULL AND 
            gds.similarity.cosine(n.embedding, other.embedding) > {embedding_cutoff}) 
            OR 
            apoc.text.levenshteinDistance(n.id, other.id) <= {distance}
        )
        RETURN DISTINCT n.id AS id, n.uuid AS uuid
        """

        logging.info(f"Query: {NODE_QUERY}")
        
        result = tx.run(NODE_QUERY)
        nodes = [(record["id"], record["uuid"]) for record in result]

        logging.info(f"Nodes found: {nodes}")

        # Filter out None values
        nodes = [(node_id, uuid) for node_id, uuid in nodes if node_id is not None and uuid is not None]

        if not nodes:
            logging.warning(f"No valid nodes found for {id_type}: {target_id}")
            return

        # Step 3: Reduce nodes to their lexical root
        lemmatizer = WordNetLemmatizer()
        root_map: Dict[str, List[str]] = {}
        
        for node_id, uuid in nodes:
            try:
                root = lemmatizer.lemmatize(node_id)
            except AttributeError as e:
                logging.error(f"Error lemmatizing node_id '{node_id}': {str(e)}")
                root = node_id  # Use the original node_id if lemmatization fails
            
            if root not in root_map:
                root_map[root] = []
            root_map[root].extend(uuid)  # Extend instead of append to handle uuid as a list

        logging.info(f"Root map: {root_map}")

        if not root_map:
            logging.warning("No nodes to merge after processing")
            return
        
        embeddings, dimension = load_embedding_model()

        futures = []
        root_embeddings = {}

        with ThreadPoolExecutor(max_workers=200) as executor:
            for node in root_map.keys():
                futures.append(
                    executor.submit(
                        embed_name,
                        name=node,
                        embeddings=embeddings
                    ))

            for future in concurrent.futures.as_completed(futures):
                name, embedding = future.result()

                root_embeddings[name] = embedding

        # Step 5: Merge nodes with the same root in a single transaction
        MERGE_QUERY = """
        UNWIND $root_map AS root_entry
        MATCH (n:Concept)
        WHERE n.uuid[0] IN root_entry.uuids
        WITH root_entry.root AS new_id, collect(n) AS nodes, root_entry.embedding AS new_embedding
        CALL apoc.refactor.mergeNodes(nodes, {
            properties: {
                noteId: "combine",
                courseId: "combine",
                userId: "combine",
                uuid: "combine",
                embedding: "discard"
            },
            mergeRels: true
        })
        YIELD node
        SET node.id = new_id, node.embedding = new_embedding
        RETURN count(node) AS merged_count
        """
        
        root_map_list = [{"root": root, "uuids": uuids, "embedding": root_embeddings[root]} for root, uuids in root_map.items()]
        result = tx.run(MERGE_QUERY, root_map=root_map_list)
        merged_count = result.single()["merged_count"]

        logging.info(f"Node merging process completed. Merged {merged_count} node groups.")
        end = datetime.now()
        logging.info(f"Ending at {end}")
        logging.info(f"Query took: {end - start}")