import uuid
import logging
from typing import Dict
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from neo4j.exceptions import ClientError, TransientError, TransactionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm import tqdm

from .Neo4jTransactionManager import transactional
from flask_app.src.shared.common_fn import load_embedding_model, embed_name
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.EntityResolver import entity_resolution
from flask_app.constants import NOTEID

class NodeUpdateService:
    @staticmethod
    @transactional
    def merge_similar_nodes(tx, distance: int = 3, embedding_cutoff: float = 0.95) -> None:
        query = """
        MATCH (e:Concept)
        WHERE e.embedding IS NOT NULL
        CALL {
        WITH e
        CALL db.index.vector.queryNodes('concept_embedding', 10, e.embedding)
        YIELD node, score
        WITH node, score
        WHERE score > toFloat($embedding_cutoff)
            AND (toLower(node.id) CONTAINS toLower(e.id) OR toLower(e.id) CONTAINS toLower(node.id)
                OR apoc.text.distance(toLower(node.id), toLower(e.id)) < $distance)
            AND labels(e) = labels(node)
        WITH node, score
        ORDER BY node.id
        RETURN collect(node) AS nodes
        }
        WITH distinct nodes
        WHERE size(nodes) > 1
        WITH collect([n in nodes | n.id]) AS results
        UNWIND range(0, size(results)-1, 1) as index
        WITH results, index, results[index] as result
        WITH apoc.coll.sort(reduce(acc = result, index2 IN range(0, size(results)-1, 1) |
                CASE WHEN index <> index2 AND
                    size(apoc.coll.intersection(acc, results[index2])) > 0
                    THEN apoc.coll.union(acc, results[index2])
                    ELSE acc
                END
        )) as combinedResult
        WITH distinct(combinedResult) as combinedResult
        WITH collect(combinedResult) as allCombinedResults
        UNWIND range(0, size(allCombinedResults)-1, 1) as combinedResultIndex
        WITH allCombinedResults[combinedResultIndex] as combinedResult, combinedResultIndex, allCombinedResults
        WHERE NOT any(x IN range(0,size(allCombinedResults)-1,1)
            WHERE x <> combinedResultIndex
            AND apoc.coll.containsAll(allCombinedResults[x], combinedResult)
        )
        RETURN combinedResult
        """

        logging.info(f"query: {query}, distance: {distance}, embedding_cutoff: {embedding_cutoff}")
        result = tx.run(query, {'distance': distance, 'embedding_cutoff': embedding_cutoff})

        two_options = []
        llm_options = []
        combined_words = []

        bad_ends = ['s', 'ed', 'ing', 'er']

        for record in result:
            if len(record['combinedResult']) == 2:
                two_options.append(record['combinedResult'])
            else:
                llm_options.append(record['combinedResult'])

        for option in two_options:
            word1, word2 = option
            seen = False
            for ending in bad_ends:
                if word1.endswith(ending) and word2 == word1[:-len(ending)]:
                    logging.info(f"Easy Merge: {word2} -> {word1}")
                    two_options.remove(option)
                    combined_words.append({word2: [word1, word2]})
                    seen = True
                elif word2.endswith(ending) and word1 == word2[:-len(ending)]:
                    logging.info(f"Easy Merge: {word1} -> {word2}")
                    two_options.remove(option)
                    combined_words.append({word1: [word1, word2]})
                    seen = True
            
            if not seen:
                llm_options.append(option)

        # if llm_options:       
        #     with ThreadPoolExecutor(max_workers=10) as executor:
        #         future = executor.submit(entity_resolution, llm_options)
        #         for merged_group in tqdm([future], total=1, desc="Processing with LLM"):
        #             merged = merged_group.result()
        #             if merged:
        #                 combined_words.extend(merged)
        #                 logging.info(f"LLM merged: {merged}")
        
        logging.info(f"Combined words: {combined_words}")

        # Merge the nodes
        for merge_group in combined_words:
            for final_label, entities in merge_group.items():
                sorted_entities = sorted(entities)
                primary_node = sorted_entities[0]
                
                merge_query = """
                MATCH (primary:Concept {id: $primary_id})
                UNWIND $other_ids AS other_id
                MATCH (other:Concept {id: other_id})
                WHERE other <> primary
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
                    "primary_id": primary_node,
                    "other_ids": sorted_entities[1:],
                    "final_label": final_label
                }
                
                try:
                    result = tx.run(merge_query, merge_params)
                    result.consume()  # Ensure the query is executed
                    logging.info(f"Merged nodes: {sorted_entities} into {final_label}")
                    
                except Exception as e:
                    logging.error(f"Error merging nodes {sorted_entities}: {str(e)}")
                    # Continue with the next merge instead of raising the exception

        logging.info("Node merging process completed.")

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, TransientError)),
        reraise=True
    )
    @transactional
    def update_embeddings(tx, noteId: str) -> None:
        embeddings, dimension = load_embedding_model()

        query = """
        MATCH (n:Concept) 
        WHERE $noteId IN n.noteId AND n.embedding IS NULL
        RETURN n.id as id
        """

        result = tx.run(query, {NOTEID: noteId})

        nodes_to_update = []
        futures = []

        with ThreadPoolExecutor(max_workers=200) as executor:
            for record in result:
                name = record['id']
                futures.append(
                    executor.submit(
                        embed_name,
                        name=name,
                        embeddings=embeddings
                    ))

            for future in concurrent.futures.as_completed(futures):
                name, embedding = future.result()

                logging.info(f"Embedded: {name}")

                nodes_to_update.append({'id': name, 'embedding': embedding})

        update_query = """
        UNWIND $nodes AS node
        MATCH (n:Concept)
        WHERE $noteId IN n.noteId AND n.id = node.id
        SET n.embedding = node.embedding
        RETURN count(n) as updatedCount
        """

        update_result = tx.run(update_query, {'nodes': nodes_to_update, NOTEID: noteId})
        logging.info(f"Updated nodes: {update_result.single()['updatedCount']}")

        return dimension

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, TransientError)),
        reraise=True
    )
    @transactional
    def create_embedding_index(tx, dimension: int) -> None:
        index_query = f"""
        CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
        FOR (n:Concept)
        ON (n.embedding)
        OPTIONS {{indexConfig: {{
        `vector.dimensions`: {dimension},
        `vector.similarity_function`: 'cosine'
        }}}}
        """

        tx.run(index_query)
        logging.info("Created or updated embedding index")

    @staticmethod
    def update_note_embeddings(noteId: str) -> None:
        dimension = NodeUpdateService.update_embeddings(noteId)
        
        NodeUpdateService.create_embedding_index(dimension)

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ClientError, TransientError)),
        reraise=True
    )
    @transactional
    def update_page_rank(tx, param: str, id: str) -> Dict:
        page_rank_string = GraphQueryService.get_page_rank_string(param=param, id=id)
        max_iterations = 20
        damping_factor = 0.85
        unique_id = str(uuid.uuid4())

        # First, check if there are any relevant nodes
        check_query = f"""
        MATCH (c:Concept)
        WHERE "{id}" IN c.{param}
        RETURN count(c) AS nodeCount
        """

        result = tx.run(check_query)
        node_count = result.single()["nodeCount"]

        if node_count == 0:
            logging.info(f"No relevant nodes found for {param} with id {id}")
            return {"updatedNodes": 0, "nodeCount": 0}

        # Step 1: Compute PageRank
        query = f"""
        MATCH (c:Concept)
        WHERE "{id}" IN c.{param}
        WITH collect(c) AS relevantNodes

        CALL gds.graph.project.cypher(
        'noteGraph_{unique_id}',
        'MATCH (c) WHERE c IN $relevantNodes RETURN id(c) AS id',
        'MATCH (c1)-[:RELATED]-(c2) 
        WHERE c1 IN $relevantNodes AND c2 IN $relevantNodes 
        RETURN id(c1) AS source, id(c2) AS target',
        {{parameters: {{relevantNodes: relevantNodes}}}}
        )
        YIELD graphName, nodeCount, relationshipCount

        CALL gds.pageRank.stream(
        graphName,
        {{
            maxIterations: {max_iterations},
            dampingFactor: {damping_factor}
        }}
        )
        YIELD nodeId, score

        WITH gds.util.asNode(nodeId) AS node, score, graphName

        WITH collect({{node: node, score: score}}) AS pageRanks, graphName

        CALL gds.graph.drop(graphName)
        YIELD graphName AS droppedGraph

        UNWIND pageRanks AS pageRank
        RETURN pageRank.node AS node, pageRank.score AS score
        """
        
        try:
            result = tx.run(query)
            records = list(result)

            logging.info(f"Page ranks computed: {len(records)}")

            if len(records) == 0:
                logging.info(f"No page ranks found for {param} with id {id}")
                return {"updatedNodes": 0, "nodeCount": node_count}

            page_ranks = [(record["node"].id, record["score"]) for record in records]

            # Step 2: Update nodes with PageRank scores
            update_query = f"""
            UNWIND $pageRanks AS pageRank
            MATCH (n:Concept)
            WHERE id(n) = pageRank[0]
            SET n.{page_rank_string} = pageRank[1]
            """

            update_result = tx.run(update_query, {"pageRanks": page_ranks})
            
            stats = {
                "updatedNodes": update_result.consume().counters.properties_set,
                "nodeCount": len(page_ranks)
            }

            logging.info(f"Updated page rank for param: {param}, id: {id}")
            logging.info(f"PageRank stats: {stats}")

            return stats

        except Exception as e:
            logging.error(f"Error in update_page_rank: {str(e)}")
            # If there was an error, attempt to drop the graph
            try:
                tx.run(f"CALL gds.graph.drop('noteGraph_{unique_id}')")
            except Exception as drop_error:
                logging.error(f"Error dropping graph after failure: {str(drop_error)}")
            raise

    @staticmethod
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        retry=retry_if_exception_type((ClientError, TransientError, AttributeError)),
        reraise=True
    )
    @transactional
    def update_communities_for_param(tx, id_type: str, target_id: str) -> Dict:
        com_string = GraphQueryService.get_com_string(communityType=id_type, communityId=target_id)
        graph_id = str(uuid.uuid4())

        # First, check if there are any nodes that match the criteria
        check_query = f"""
        MATCH (n)
        WHERE "{target_id}" IN n.{id_type}
        RETURN count(n) AS nodeCount
        """

        result = tx.run(check_query)
        node_count = result.single()["nodeCount"]

        if node_count == 0:
            logging.info(f"No nodes found for {id_type}: {target_id}")
            return {"updatedNodes": 0, "communityCount": 0}

        # If nodes exist, proceed with the community detection
        query = f"""
        MATCH (n)
        WHERE "{target_id}" IN n.{id_type}
        WITH collect(n) AS nodes

        CALL gds.graph.project.cypher(
        '{graph_id}_temp_graph',
        'UNWIND $nodes AS n RETURN id(n) AS id',
        'UNWIND $nodes AS n1
        MATCH (n1)-[r]-(n2)
        WHERE n2 IN $nodes
        RETURN id(n1) AS source, id(n2) AS target',
        {{parameters: {{nodes: nodes}}}}
        )
        YIELD graphName, nodeCount, relationshipCount

        CALL gds.louvain.stream(graphName)
        YIELD nodeId, communityId

        WITH gds.util.asNode(nodeId) AS node, communityId, graphName

        WITH collect({{node: node, communityId: communityId}}) AS communities, graphName

        CALL gds.graph.drop(graphName)
        YIELD graphName AS droppedGraph

        UNWIND communities AS community
        RETURN community.node AS node, community.communityId AS communityId
        """

        try:
            result = tx.run(query)
            communities = [(record["node"].id, record["communityId"]) for record in result if record is not None and record["node"] is not None and record["communityId"] is not None]

            if not communities:
                logging.info(f"No communities detected for {id_type}: {target_id}")
                return {"updatedNodes": 0, "communityCount": 0}

            # Step 2: Update nodes with community information
            update_query = f"""
            UNWIND $communities AS community
            MATCH (n)
            WHERE id(n) = community[0]
            SET n.{com_string} = community[1]
            """

            update_result = tx.run(update_query, {"communities": communities})
            
            stats = {
                "updatedNodes": update_result.consume().counters.properties_set,
                "communityCount": len(set(c[1] for c in communities))
            }
            
            logging.info(f"Updated communities for {id_type}: {target_id}")
            logging.info(f"Community stats: {stats}")

            return stats

        except Exception as e:
            logging.error(f"Error in update_communities_for_param: {str(e)}")
            # If there was an error, attempt to drop the graph
            try:
                tx.run(f"CALL gds.graph.drop('{graph_id}_temp_graph')")
            except Exception as drop_error:
                logging.error(f"Error dropping graph after failure: {str(drop_error)}")
            raise