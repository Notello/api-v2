from concurrent.futures import ThreadPoolExecutor
from typing import Dict
import uuid
from flask_app.src.shared.common_fn import load_embedding_model
from flask import current_app
import logging
from itertools import combinations

from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from retry import retry
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.src.graphDB_dataAccess import graphDBdataAccess

class EntityGroup(BaseModel):
    final_label: str = Field(description="The final label for the merged entity")
    entities: List[str] = Field(description="List of entities to be merged into the final label")

class Disambiguate(BaseModel):
    merge_groups: List[EntityGroup] = Field(
        description="Groups of entities that should be merged, with their final labels"
    )

def setup_llm():
    system_prompt = """You are a data processing assistant. Your task is to identify duplicate entities in a list and decide which of them should be merged.
    The entities might be slightly different in format or content, but essentially refer to the same thing. Use your analytical skills to determine duplicates.

    Here are the rules for identifying duplicates:
    1. You do not need to merge all entities, it is up to your discretion.
    2. Entities with minor typographical differences should be considered duplicates.
    3. Entities with different formats but the same content should be considered duplicates.
    4. Entities should only be merged if they refer to the same real-world object or concept.
    5. If it refers to different numbers, dates, or products, do not merge results.
    6. If it refers to a name of a person or thing, choose the full name as the final label.

    ## IMPORTANT NOTES:
    - Do not merge nodes just because they have the same words in them, they MUST be the same real world entity.
    - Example: entity1 = 'America', entity2 = 'American Football', DO NOT merge these entities (One is a country, the other is a sport).
    - Example: entity1 = 'New York', entity2 = 'New York City', DO merge these entities (they are the same city).
    - Example: entity1 = 'Aidan Gollan', entity2 = 'Audrey Gollan', DO merge these entities (they are siblings not the same person).

    Your output should be a list of groups, where each group is represented by a dictionary. The dictionary should have a 'final_label' key with the chosen label for the merged entity, and an 'entities' key with a list of all entities that should be merged into this label.
    """
    
    user_template = """
    Here is the list of entities to process:
    {entities}

    Please identify duplicates, merge them, and provide the merged groups in the specified format.
    """

    extraction_llm = ChatOpenAI(model_name='gpt-3.5-turbo-0125').with_structured_output(Disambiguate)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

@retry(tries=3, delay=2)
def entity_resolution(entities: List[str]) -> Optional[List[Dict[str, List[str]]]]:
    extraction_chain = setup_llm()
    result = extraction_chain.invoke({"entities": entities})
    
    return [
        {group.final_label: group.entities}
        for group in result.merge_groups
    ]

class NodeUpdateService:
    @staticmethod
    def merge_similar_nodes() -> None:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

        distance = 3
        embedding_cutoff = 0.95

        query = """
        MATCH (e:Concept)
        WHERE e.embedding IS NOT NULL
        CALL {
        WITH e
        CALL db.index.vector.queryNodes('concept_embedding', 10, e.embedding)
        YIELD node, score
        WITH node, score
        WHERE score > toFLoat($embedding_cutoff)
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
        result = graphAccess.execute_query(query, {'distance': distance, 'embedding_cutoff': embedding_cutoff})

        print(f"Potential merges: {result}")

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
                    

        if llm_options:       
            with ThreadPoolExecutor(max_workers=10) as executor:
                future = executor.submit(entity_resolution, llm_options)
                for merged_group in tqdm([future], total=1, desc="Processing with LLM"):
                    merged = merged_group.result()
                    if merged:
                        combined_words.extend(merged)
                        logging.info(f"LLM merged: {merged}")
        
        logging.info(f"Combined words: {combined_words}")

        # Merge the nodes
        for merge_group in combined_words:
            for final_label, entities in merge_group.items():
                # Sort entities to ensure consistent merging
                sorted_entities = sorted(entities)
                primary_node = sorted_entities[0]
                
                # Merge properties and relationships
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
                    result = graphAccess.execute_query(merge_query, merge_params)
                    logging.info(f"Merged nodes: {sorted_entities} into {final_label}")
                    
                    # Log the properties of the merged node
                    if result and result[0]['node']:
                        merged_node = result[0]['node']
                        logging.info(f"Merged node properties: {dict(merged_node)}")
                    
                except Exception as e:
                    logging.error(f"Error merging nodes {sorted_entities}: {str(e)}")

        logging.info("Node merging process completed.")

    @staticmethod
    def update_note_embeddings(noteId: str) -> None:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
        embeddings, dimension = load_embedding_model()

        query = """
        MATCH (n:Concept) 
        WHERE $noteId IN n.noteId AND n.embedding IS NULL
        RETURN n.id as id
        """

        result = graphAccess.execute_query(query, {'noteId': noteId})

        for record in result:
            name = record['id']
            embedding = embeddings.embed_query(text=name)
            record['embedding'] = embedding

        update_query = """
        UNWIND $nodes AS node
        MATCH (n)
        WHERE $noteId IN n.noteId AND n.id = node.id
        SET n += node
        RETURN count(n) as updatedCount
        """

        update_result = graphAccess.execute_query(update_query, {'nodes': result, 'noteId': noteId})

        index_query = f"""
        CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
        FOR (n:Concept)
        ON (n.embedding)
        OPTIONS {{indexConfig: {{
        `vector.dimensions`: {dimension},
        `vector.similarity_function`: 'cosine'
        }}}}
        """

        index_result = graphAccess.execute_query(index_query)

        logging.info(f"Updated nodes: {update_result}")

    @staticmethod
    def update_communities_for_param(id_type: str, target_id: str) -> Dict:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
        com_string = GraphQueryService.get_com_string(communityType=id_type, communityId=target_id)

        try:
            query = f"""
            MATCH (n)-[r]-(relatedNode)
            WHERE "{target_id}" IN n.{id_type} AND "{target_id}" IN relatedNode.{id_type}

            WITH collect(distinct n) + collect(distinct relatedNode) AS nodes, collect(distinct r) AS rels

            CALL gds.graph.project.cypher(
            '{target_id}_temp_graph',
            'UNWIND $nodes AS n RETURN id(n) AS id',
            'UNWIND $rels AS r RETURN id(startNode(r)) AS source, id(endNode(r)) AS target',
            {{parameters: {{nodes: nodes, rels: rels}}}}
            )
            YIELD graphName

            CALL gds.louvain.stream('{target_id}_temp_graph')
            YIELD nodeId, communityId

            WITH gds.util.asNode(nodeId) AS node, communityId

            WITH collect({{node: node, communityId: communityId}}) AS results

            CALL gds.graph.drop('{target_id}_temp_graph') YIELD graphName

            UNWIND results AS result
            RETURN result.node AS node, result.communityId AS communityId
            """

            result = graphAccess.execute_query(query)

            updated_nodes = []

            for record in result:
                node = record['node']
                communityId = record['communityId']

                node[com_string] = communityId

                updated_nodes.append(node)


            update_query = """
            UNWIND $nodes AS node
            MATCH (n)
            WHERE n.id = node.id
            SET n += node
            RETURN count(n) as updatedCount
            """

            update_result = graphAccess.execute_query(update_query, {'nodes': updated_nodes})

            logging.info(f"Updated nodes: {update_result}")

        except ValueError as ve:
            logging.error(f"Invalid input: {str(ve)}")
            raise
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            raise
    
    @staticmethod
    def update_page_rank(param: str, id: str) -> None:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
        page_rank_string = GraphQueryService.get_page_rank_string(param=param, id=id)
        max_iterations = 20
        damping_factor = 0.85
        
        # Generate a unique identifier for this PageRank calculation
        unique_id = str(uuid.uuid4())
        
        # Create the unique property name for this note's PageRank
        
        QUERY = f"""
        // First, filter and collect the relevant nodes
        MATCH (c:Concept)
        WHERE "{id}" IN c.{param}
        WITH collect(c) AS relevantNodes

        // Now project the graph using only these relevant nodes
        CALL gds.graph.project.cypher(
          'noteGraph_{unique_id}',
          'MATCH (c) WHERE c IN $relevantNodes RETURN id(c) AS id',
          'MATCH (c1)-[:RELATED]-(c2) 
           WHERE c1 IN $relevantNodes AND c2 IN $relevantNodes 
           RETURN id(c1) AS source, id(c2) AS target',
          {{
            parameters: {{relevantNodes: relevantNodes}}
          }}
        )
        YIELD graphName, nodeCount, relationshipCount

        CALL gds.pageRank.write(
          'noteGraph_{unique_id}',
          {{
            maxIterations: {max_iterations},
            dampingFactor: {damping_factor},
            writeProperty: '{page_rank_string}'
          }}
        )
        YIELD nodePropertiesWritten, ranIterations

        CALL gds.graph.drop('noteGraph_{unique_id}')
        YIELD graphName AS droppedGraph

        RETURN nodeCount, relationshipCount, nodePropertiesWritten, ranIterations, droppedGraph
        """
        
        try:
            graphAccess.execute_query(QUERY)
            logging.info(f"Updated page rank for param: {param}, id: {id}")
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            raise
