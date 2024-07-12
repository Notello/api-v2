from concurrent.futures import ThreadPoolExecutor
from typing import Dict
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

from flask_app.src.graphDB_dataAccess import graphDBdataAccess

# Define the data models for structured output
class DuplicateEntities(BaseModel):
    entities: List[str] = Field(
        description="Entities that represent the same object or real-world entity and should be merged"
    )

class Disambiguate(BaseModel):
    merge_entities: Optional[List[DuplicateEntities]] = Field(
        description="Lists of entities that represent the same object or real-world entity and should be merged"
    )

def setup_llm():
    # Set up the LLM
    system_prompt = """You are a data processing assistant. Your task is to identify duplicate entities in a list and decide which of them should be merged.
    The entities might be slightly different in format or content, but essentially refer to the same thing. Use your analytical skills to determine duplicates.

    Here are the rules for identifying duplicates:
    1. Entities with minor typographical differences should be considered duplicates.
    2. Entities with different formats but the same content should be considered duplicates.
    3. Entities that refer to the same real-world object or concept, even if described differently, should be considered duplicates.
    4. If it refers to different numbers, dates, or products, do not merge results
    """
    
    user_template = """
    Here is the list of entities to process:
    {entities}

    Please identify duplicates, merge them, and provide the merged list.
    """

    extraction_llm = ChatOpenAI(model_name='gpt-3.5-turbo-0125').with_structured_output(Disambiguate)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

@retry(tries=3, delay=2)
def entity_resolution(entities: List[str]) -> Optional[List[str]]:
    extraction_chain = setup_llm()
    return [
        el.entities
        for el in extraction_chain.invoke({"entities": entities}).merge_entities
    ]

class NodeUpdateService:
    @staticmethod
    def merge_similar_nodes() -> None:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

        distance = 3
        embedding_cutoff = 0.95

        query = """
        MATCH (e:Concept)
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

        result = graphAccess.execute_query(query, {'distance': distance, 'embedding_cutoff': embedding_cutoff})

        all_options = []
        words_to_test = []
        words_to_combine = []

        bad_ends = ['s', 'ed', 'ing', 'er']

        for record in result:
            options = record['combinedResult']
            for option in combinations(options, 2):
                words_to_test.append(option)
                all_options.append(option)
        
        for option in all_options:
            for option in combinations(options, 2):
                word1, word2 = option
                for ending in bad_ends:
                    if word1.endswith(ending) and word2 == word1[:-len(ending)]:
                        print(f"Yes: {word2} -> {word1}")
                        words_to_combine.append(option)
                        words_to_test.remove(option)
                        break
                    elif word2.endswith(ending) and word1 == word2[:-len(ending)]:
                        print(f"Yes: {word1} -> {word2}")
                        words_to_combine.append(option)
                        words_to_test.remove(option)
                        break

        if words_to_test:       
            with ThreadPoolExecutor(max_workers=10) as executor:
                future = executor.submit(entity_resolution, words_to_test)
                for merged_group in tqdm([future], total=1, desc="Processing with LLM"):
                    merged = merged_group.result()
                    if merged:
                        words_to_combine.extend(merged)
                        print(f"LLM merged: {merged}")
        
        print(words_to_combine)

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

                node[f'{id_type}_{target_id}_community'] = communityId

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