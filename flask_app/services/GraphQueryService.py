import json
import logging
import random
from typing import Any, Dict, List, Tuple
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.shared.common_fn import get_graph

class GraphQueryService():

    @staticmethod
    def get_com_string(communityType: str, communityId: str) -> str:
        return f"{communityType}_{communityId}_community".replace("-", "_")

    @staticmethod
    def get_page_rank_string(param: str, id: str) -> str:
        return f"{param}_{id}_pagerank".replace("-", "_")

    @staticmethod
    def get_default_graph_params(communityType: str, communityId: str) -> List[Tuple[str, str]]:
        com_string = GraphQueryService.get_com_string(communityType=communityType, communityId=communityId)
        page_rank_string = GraphQueryService.get_page_rank_string(param=communityType, id=communityId)

        return [
        
            ("ID(n)", "nodeId"), ("LABELS(n)", "nodeLabels"), 
            ("n.position", "position"), ("n.fileName", "fileName"), 
            ("n.id", "conceptId"),
            (f"n.{com_string}", "communityId"), (f"n.{page_rank_string}", "pageRank"),
            ("n.uuid[0]", "nodeUuid"), ('n.offset', 'offset'),


            ("rel.type", "relType"), 
            
            ("ID(r)", "relatedNodeId"), ("LABELS(r)", "relatedNodeLabels"), 
            ("r.position", "relatedNodePosition"), ("r.fileName", "relatedNodeFileName"),

            ("r.id", "relatedNodeConceptId"),
            (f"r.{com_string}", "relatedNodeCommunityId"), (f"r.{page_rank_string}", "relatedNodePageRank"),
            ('r.uuid[0]', 'relatedNodeUuid'), ('r.offset', 'relatedNodeOffset'),
            ]
    
    
    
    @staticmethod
    def get_graph_for_param(
        key: str, 
        value: str, 
        return_params: List[Tuple[str, str]] = None
    ) -> Tuple[Dict[str, List[Dict]], List[Dict[str, Any]]]:
        try:
            graphDb_data_Access = graphDBdataAccess(get_graph())

            final_params = return_params if return_params is not None else \
                GraphQueryService.get_default_graph_params(communityType=key, communityId=value)
            
            print(final_params)

            return_clause = ", ".join(f"{param[0]} AS {param[1]}" for param in final_params)

            QUERY = f"""
            MATCH (n)
            WHERE n.{key} = $value OR $value IN n.{key}
            OPTIONAL MATCH (n)-[rel]->(r)
            WHERE r.{key} = $value or $value IN r.{key}
            RETURN {return_clause}
            """

            parameters = {
                "value": value
            }

            result = graphDb_data_Access.execute_query(QUERY, parameters)

            nodes = {
                'documents': {},
                'chunks': {},
                'concepts': {}
            }
            relationships = []

            for record in result:
                node_data = {}
                related_node_data = {}
                rel_type = None

                for param in final_params:
                    attr_name = param[1]
                    attr_value = record.get(attr_name)
                    
                    if attr_name.startswith("relatedNode"):
                        related_node_data[attr_name.replace("relatedNode", "")] = attr_value
                    elif attr_name == "relType":
                        rel_type = attr_value
                    else:
                        node_data[attr_name] = attr_value

                if 'nodeId' in node_data and 'nodeLabels' in node_data:
                    node_type = next((label for label in ['Document', 'Chunk', 'Concept'] if label in node_data['nodeLabels']), None)
                    if node_type:
                        node_info = nodes[node_type.lower() + 's'].get(node_data['nodeId'], {})
                        node_info['id'] = node_data['nodeId']
                        if node_type == 'Document':
                            node_info['fileName'] = node_data.get('fileName')
                        elif node_type == 'Chunk':
                            node_info['position'] = node_data.get('position')
                            node_info['offset'] = node_data.get('offset')
                        elif node_type == 'Concept':
                            node_info['conceptId'] = node_data.get('conceptId')
                            node_info['pageRank'] = node_data.get('pageRank')
                            node_info['nodeUuid'] = node_data.get('nodeUuid')
                        
                        if 'communityId' in node_data and 'communityId' not in node_info:
                            node_info['communityId'] = node_data['communityId']
                        
                        nodes[node_type.lower() + 's'][node_data['nodeId']] = node_info

                if related_node_data.get('Id') is not None and related_node_data.get('Labels') is not None:
                    related_node_type = next((label for label in ['Document', 'Chunk', 'Concept'] if label in related_node_data['Labels']), None)
                    if related_node_type:
                        related_node_info = nodes[related_node_type.lower() + 's'].get(related_node_data['Id'], {})
                        related_node_info['id'] = related_node_data['Id']
                        if related_node_type == 'Chunk':
                            related_node_info['position'] = related_node_data.get('relatedNodePosition')
                            related_node_info['offset'] = related_node_data.get('relatedNodeOffset')
                        
                        if 'relatedNodeCommunityId' in related_node_data and 'communityId' not in related_node_info:
                            related_node_info['communityId'] = related_node_data['relatedNodeCommunityId']
                        
                        nodes[related_node_type.lower() + 's'][related_node_data['Id']] = related_node_info

                if 'nodeId' in node_data and related_node_data.get('Id') is not None and rel_type is not None:
                    relationships.append({
                        "start_node_id": node_data['nodeId'], 
                        "relationship_type": rel_type, 
                        "end_node_id": related_node_data['Id']
                    })

            for node_type in nodes:
                nodes[node_type] = list(nodes[node_type].values())

            return nodes, relationships

        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None, None
        

    @staticmethod
    def get_communities_for_param(param: str, 
                                id: str, 
                                topics: List[str] = None,
                                num_communities: int = None,
                                min_node_count: int = 10
                                ) -> List[int] | None:
        
        logging.info(f"Getting communities for {param} with id {id}")

        graphAccess = graphDBdataAccess(get_graph())
        com_string = GraphQueryService.get_com_string(communityType=param, communityId=id)

        parameters = {
            'value': id,
            'min_node_count': min_node_count
        }

        if len(topics) > 0:
            TOPIC_COMMUNITIES_QUERY = f"""
            MATCH (n)
            WHERE ANY(label IN labels(n) WHERE label IN ['Concept', 'Chunk']) AND $value in n.{param}
            WITH n
            WHERE ANY(topic IN {topics} WHERE n.id = topic)
            WITH n['{com_string}'] AS community_id, COUNT(n) AS node_count
            WHERE node_count >= $min_node_count
            RETURN DISTINCT community_id AS community_id
            """

            result = graphAccess.execute_query(TOPIC_COMMUNITIES_QUERY, parameters)
            communities = [community['community_id'] for community in result]
        else:
            ALL_COMMUNITIES_QUERY = f"""
            MATCH (n)
            WHERE $value in n.{param}
            WITH n['{com_string}'] AS community_id, COUNT(n) AS node_count
            WHERE community_id IS NOT NULL AND node_count >= $min_node_count
            RETURN DISTINCT community_id AS community_id
            """

            result = graphAccess.execute_query(ALL_COMMUNITIES_QUERY, parameters)
            communities = [community['community_id'] for community in result]

        logging.info(f"Query: {ALL_COMMUNITIES_QUERY if len(topics) == 0 else TOPIC_COMMUNITIES_QUERY}")
        logging.info(f"Result: {communities}")

        if num_communities is not None:
            communities = random.sample(communities, min(num_communities, len(communities)))
        
        logging.info(f"Filtered communities for {param} with id {id}: {communities}")

        return communities
    
    @staticmethod
    def get_random_topics(
        param: str, 
        id: str,
        num_topics: int = 1
    ):
        graphAccess = graphDBdataAccess(get_graph())
        
        QUERY = f"""
        MATCH (c:Concept)
        WHERE '{id}' IN c.{param}
        WITH c, rand() AS r
        ORDER BY r
        LIMIT {num_topics}
        RETURN c.id AS id, c.uuid AS uuid
        """
        
        result = graphAccess.execute_query(query=QUERY)
        
        if len(result) == 0:
            logging.error(f"Failed to get random topics for {param} with id {id}")
            return None
        
        return [{'id': item['id'], 'uuid': item['uuid']} for item in result]

    @staticmethod
    def get_topic_graph(
        param: str, 
        id: str, 
        num_rels: int = 5,
        topics: List[str] = [],
    ):
        if len(topics) == 0:
            random_topics = GraphQueryService.get_random_topics(param=param, id=id, num_topics=num_rels)
            if random_topics is None:
                return None
            topics = [topic['id'] for topic in random_topics]
        
        logging.info(f"Generating topic graph for topics {topics}")
        
        topic_graph = GraphQueryService.get_topic_graph_for_topics(topics=topics, param=param, id=id, num_rels=num_rels)
        
        logging.info(f"Topic graph for topics {topics} generated.")

        return topic_graph

    @staticmethod
    def get_topic_graph_for_topics(
        topics: List[str],
        param: str,
        id: str,
        num_rels: int = 5,
        chunks_per_rel: int = 1
    ):
        graphAccess = graphDBdataAccess(get_graph())

        MAIN_QUERY = f"""
        WITH {topics} AS allTopics
        UNWIND range(0, {num_rels} - 1) AS i
        WITH allTopics[i % size(allTopics)] AS topic, i
        MATCH (start:Concept)
        WHERE topic IN start.id
        MATCH (start)-[rel]-(related:Concept)
        WHERE '{id}' IN related.{param}
        WITH start, rel, related, i
        ORDER BY i, rand()
        WITH DISTINCT start, rel, related
        LIMIT {num_rels}

        MATCH (chunk:Chunk)
        WHERE chunk.{param} = '{id}'
        WITH start, rel, related, chunk,
            apoc.coll.sum([
            CASE WHEN exists((chunk)-[:REFERENCES]->(start)) THEN 1 ELSE 0 END,
            CASE WHEN exists((chunk)-[:REFERENCES]->(related)) THEN 1 ELSE 0 END
            ]) AS relevance
        ORDER BY relevance DESC
        WITH start, rel, related, collect(chunk)[0..{chunks_per_rel}] AS relevantChunks

        RETURN {{
            source: start.id,
            sourceUUID: start.uuid,
            target: related.id,
            targetUUID: related.uuid,
            type: rel.type,
            chunks: [chunk IN relevantChunks | {{
                id: chunk.id,
                text: chunk.text,
                noteId: chunk.noteId,
                position: chunk.position,
                document_name: chunk.document_name
            }}]
        }} AS result
        """

        result = graphAccess.execute_query(query=MAIN_QUERY)

        logging.info(f"Len of result: {len(result)}")


        if len(result) == 0:
            logging.error(f"Failed to get topic graph for topics {topics}: {result}")
            logging.info(f"Query: {MAIN_QUERY}")
            return None
                
        return result

    @staticmethod
    def get_importance_graph_by_param(param: str, id: str) -> str | None:
        graphAccess = graphDBdataAccess(get_graph())
        pagerank_string = GraphQueryService.get_page_rank_string(param=param, id=id)

        QUERY = f"""
        // Calculate graph size and importance scores for all nodes
        MATCH (c:Concept)
        WHERE $id IN c.{param} AND c[$pagerank_string] IS NOT NULL
        WITH count(c) AS graphSize, collect(c) AS allNodes, $pagerank_string AS prString

        UNWIND allNodes AS c
        WITH graphSize, c, prString, COUNT {{ (c)-[:RELATED]-() }} AS connectionCount
        WITH graphSize, c, prString, connectionCount, c[prString] * log(1 + connectionCount) AS importanceScore

        // Calculate statistics
        WITH graphSize, prString,
            collect({{
                node: c, 
                score: importanceScore, 
                connections: connectionCount, 
                pageRank: c[prString]
                }}) AS nodeScores,
            avg(importanceScore) AS meanScore,
            stDev(importanceScore) AS stdDevScore,
            avg(connectionCount) AS avgConnections,
            avg(c[prString]) AS avgPageRank

        // Calculate 75th percentile (Q3)
        WITH graphSize, nodeScores, meanScore, stdDevScore, avgConnections, avgPageRank, prString,
            [score IN nodeScores | score.score] AS scores
        WITH graphSize, nodeScores, meanScore, stdDevScore, avgConnections, avgPageRank, prString,
            scores ORDER BY scores
        WITH graphSize, nodeScores, meanScore, stdDevScore, avgConnections, avgPageRank, prString,
            scores[toInteger(0.75 * size(scores))] AS q3Score

        // Determine adaptive threshold based on graph size
        WITH *, CASE 
            WHEN graphSize < 100 THEN 0.5  // Less strict for small graphs
            WHEN graphSize < 500 THEN 1.0  // Moderately strict for medium graphs
            ELSE 1.5  // More strict for large graphs
        END AS thresholdMultiplier

        // Filter nodes using adaptive criteria
        UNWIND nodeScores AS nodeScore
        WITH nodeScore.node AS c, nodeScore.score AS importanceScore, 
            nodeScore.connections AS connectionCount, nodeScore.pageRank AS pageRank,
            meanScore, stdDevScore, q3Score, avgConnections, avgPageRank, thresholdMultiplier, prString
        WHERE importanceScore > meanScore + thresholdMultiplier * stdDevScore  // Adaptive threshold
        AND importanceScore > q3Score  // Must be in top 25%
        AND (connectionCount > avgConnections OR pageRank > avgPageRank)  // Must be above average in at least one metric

        // Find immediate neighbors of important nodes
        MATCH (c)-[:RELATED]-(neighbor:Concept)
        WHERE $id IN neighbor.{param}

        // Find related chunks
        WITH c, pageRank, connectionCount, importanceScore, collect(neighbor) AS neighbors,
            meanScore, stdDevScore, q3Score, avgConnections, avgPageRank, thresholdMultiplier, prString
        MATCH (chunk:Chunk)-[:REFERENCES]->(relatedConcept:Concept)
        WHERE relatedConcept = c OR relatedConcept IN neighbors
        WITH c, pageRank, connectionCount, importanceScore, neighbors, chunk, count(DISTINCT relatedConcept) AS relevanceScore,
            meanScore, stdDevScore, q3Score, avgConnections, avgPageRank, thresholdMultiplier, prString
        ORDER BY relevanceScore DESC
        WITH c, pageRank, connectionCount, importanceScore, neighbors,
            COLLECT({{
                id: chunk.id,
                text: chunk.text, 
                document_name: chunk.document_name,
                offset: chunk.offset,
                noteId: chunk.noteId
                }})[0..3] AS topChunks,
            meanScore, stdDevScore, q3Score, avgConnections, avgPageRank, thresholdMultiplier, prString

        // Return the results
        RETURN DISTINCT
            c.id AS conceptId,
            c.uuid[0] as conceptUuid,
            pageRank AS conceptPageRank,
            connectionCount,
            importanceScore,
            [neighbor IN neighbors | {{id: neighbor.id, uuid: neighbor.uuid[0], pageRank: neighbor[prString]}}] AS relatedConcepts,
            topChunks,
            meanScore,
            stdDevScore,
            q3Score,
            avgConnections,
            avgPageRank,
            thresholdMultiplier  // Include this to see the applied threshold
        ORDER BY importanceScore DESC
        LIMIT 10
        """

        parameters = {
            "id": id,
            "pagerank_string": pagerank_string
        }


        try:
            result = graphAccess.execute_query(QUERY, parameters)   
            return result
        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None
        
    @staticmethod
    def get_quiz_questions_by_id(quizId: str):
        graphDb_data_Access = graphDBdataAccess(get_graph())

        QUERY = f"""
        MATCH (q:QuizQuestion)
        WHERE $quizId in q.quizId
        RETURN q
        """

        parameters = {
            "quizId": quizId
        }

        result = graphDb_data_Access.execute_query(QUERY, parameters)

        out = []

        for record in result:
            question = record.get('q')
            question['answers'] = json.loads(question.get('answers'))
            out.append(question)

        return out

    @staticmethod
    def get_topic_graph_for_topic_uuid(
        topic_uuid: str,
        num_chunks: int = 5
    ): 
        graphAccess = graphDBdataAccess(get_graph())
        
        MAIN_QUERY = f"""
            WITH $topic_uuid AS topic_uuid
            MATCH (start:Concept)
            WHERE topic_uuid IN start.uuid

            // Find related concepts
            OPTIONAL MATCH (start)-[r1:RELATED]-(related:Concept)
            WHERE NOT topic_uuid IN related.uuid

            // Find chunks related to the start concept
            OPTIONAL MATCH (chunk:Chunk)-[r2:REFERENCES]-(start)

            // Collect results
            WITH start, 
                COLLECT(DISTINCT {{
                    uuid: related.uuid[0],
                    id: related.id,
                    relation_type: r1.type
                }}) AS related_concepts,
                COLLECT(DISTINCT {{
                    document_name: chunk.document_name,
                    text: chunk.text,
                    id: chunk.id,
                    offset: chunk.offset,
                    noteId: chunk.noteId
                }})[..{num_chunks}] AS related_chunks

            // Return the results
            RETURN {{
                start_concept: {{
                    uuid: start.uuid[0],
                    id: start.id
                }},
                related_concepts: related_concepts,
                related_chunks: related_chunks
            }} as result
        """

        parameters = {
            'topic_uuid': topic_uuid
        }

        result = graphAccess.execute_query(query=MAIN_QUERY, param=parameters)

        return result
    
    @staticmethod
    def get_display_topic_graph(uuid: str, courseId: str) -> Tuple[Dict[str, List[Dict]], List[Dict[str, Any]]] | None:
        try:
            graphAccess = graphDBdataAccess(get_graph())

            com_string = GraphQueryService.get_com_string(communityType='courseId', communityId=courseId)
            page_rank_string = GraphQueryService.get_page_rank_string(param='courseId', id=courseId)

            print(com_string, page_rank_string)

            QUERY = f"""
            MATCH (c:Concept)
            WHERE $uuid IN c.uuid
            OPTIONAL MATCH (c)-[r1]-(chunk:Chunk)
            OPTIONAL MATCH (c)-[r2]-(doc:Document)
            OPTIONAL MATCH (c)-[r3]-(relatedConcept:Concept)
            WHERE relatedConcept <> c
            OPTIONAL MATCH (relatedConcept)-[r4]-(otherRelatedConcept:Concept)
            WHERE otherRelatedConcept <> c AND otherRelatedConcept <> relatedConcept
            RETURN 
                c.id AS conceptId, ID(c) AS conceptNodeId, c.{com_string} AS conceptCommunityId, 
                c.uuid[0] AS conceptUuid, c.{page_rank_string} AS conceptPageRank,
                
                chunk.id AS chunkId, ID(chunk) AS chunkNodeId, chunk.position AS chunkPosition, 
                chunk.{com_string} AS chunkCommunityId, chunk.offset AS chunkOffset,
                
                doc.id AS docId, ID(doc) AS docNodeId, doc.fileName AS docFileName, 
                doc.{com_string} AS docCommunityId,
                
                relatedConcept.id AS relatedConceptId, ID(relatedConcept) AS relatedConceptNodeId, 
                relatedConcept.{com_string} AS relatedConceptCommunityId, 
                relatedConcept.uuid[0] AS relatedConceptUuid, 
                relatedConcept.{page_rank_string} AS relatedConceptPageRank,
                
                otherRelatedConcept.id AS otherRelatedConceptId, 
                ID(otherRelatedConcept) AS otherRelatedConceptNodeId,
                
                r1.type AS chunkRelType, r2.type AS docRelType, r3.type AS conceptRelType,
                r4.type AS interConceptRelType
            """

            parameters = {"uuid": uuid}
            result = graphAccess.execute_query(QUERY, parameters)

            nodes = {
                'documents': {},
                'chunks': {},
                'concepts': {}
            }
            relationships = []

            for record in result:
                # Process concept node
                if record['conceptNodeId'] and record['conceptNodeId'] not in nodes['concepts']:
                    nodes['concepts'][record['conceptNodeId']] = {
                        'node_type': 'Concept',
                        'id': record['conceptNodeId'],
                        'conceptId': record['conceptId'],
                        'communityId': record['conceptCommunityId'],
                        'nodeUuid': record['conceptUuid'],
                        'pageRank': record['conceptPageRank'],
                    }

                # Process chunk node
                if record['chunkNodeId'] and record['chunkNodeId'] not in nodes['chunks']:
                    nodes['chunks'][record['chunkNodeId']] = {
                        'node_type': 'Chunk',
                        'id': record['chunkNodeId'],
                        'position': record['chunkPosition'],
                        'communityId': record['chunkCommunityId'],
                        'offset': record['chunkOffset'],
                    }

                # Process document node
                if record['docNodeId'] and record['docNodeId'] not in nodes['documents']:
                    nodes['documents'][record['docNodeId']] = {
                        'node_type': 'Document',
                        'id': record['docNodeId'],
                        'fileName': record['docFileName'],
                        'communityId': record['docCommunityId'],
                    }

                # Process related concept node
                if record['relatedConceptNodeId'] and record['relatedConceptNodeId'] not in nodes['concepts']:
                    nodes['concepts'][record['relatedConceptNodeId']] = {
                        'node_type': 'Concept',
                        'id': record['relatedConceptNodeId'],
                        'conceptId': record['relatedConceptId'],
                        'communityId': record['relatedConceptCommunityId'],
                        'nodeUuid': record['relatedConceptUuid'],
                        'pageRank': record['relatedConceptPageRank'],
                    }

                # Process relationships
                if record['chunkNodeId']:
                    relationships.append({
                        'start_node_id': record['conceptNodeId'],
                        'end_node_id': record['chunkNodeId'],
                        'relationship_type': record['chunkRelType']
                    })
                if record['docNodeId']:
                    relationships.append({
                        'start_node_id': record['conceptNodeId'],
                        'end_node_id': record['docNodeId'],
                        'relationship_type': record['docRelType']
                    })
                if record['relatedConceptNodeId']:
                    relationships.append({
                        'start_node_id': record['conceptNodeId'],
                        'end_node_id': record['relatedConceptNodeId'],
                        'relationship_type': record['conceptRelType']
                    })
                if record['otherRelatedConceptNodeId'] and record['otherRelatedConceptNodeId'] in nodes['concepts']:
                    relationships.append({
                        'start_node_id': record['relatedConceptNodeId'],
                        'end_node_id': record['otherRelatedConceptNodeId'],
                        'relationship_type': record['interConceptRelType']
                    })

            # Convert dictionaries to lists
            for node_type in nodes:
                nodes[node_type] = list(nodes[node_type].values())

            return nodes, relationships

        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None

    @staticmethod
    def get_summary_for_param(param: str, id: str) -> str | None:
        graphAccess = graphDBdataAccess(get_graph())
        
        QUERY = f"""
        MATCH (n:Concept)
        WHERE $id IN n.{param}
        OPTIONAL MATCH (n)-[r:HAS_SUMMARY]->(s:Summary) 
        WHERE $id = s.{param}
        RETURN n.id AS conceptId, s
        """

        parameters = {
            'id': id
        }

        result = graphAccess.execute_query(QUERY, parameters)

        return {
            'summaries': [res.get('s') for res in result if res.get('s') is not None],
            'concept': result[0].get('conceptId') if len(result) > 0 else None
        }

    @staticmethod
    def get_topic_summary(uuid: str) -> str | None:
        graphAccess = graphDBdataAccess(get_graph())

        QUERY = f"""
        Match (n:Concept)
        WHERE '{uuid}' IN n.uuid
        OPTIONAL MATCH (n)-[r:HAS_SUMMARY]->(s:Summary) 
        RETURN n.id AS conceptId, s
        """

        result = graphAccess.execute_query(QUERY)

        return {
            'summaries': [res.get('s') for res in result if res.get('s') is not None],
            'concept': result[0].get('conceptId') if len(result) > 0 else None
        }

    
    @staticmethod
    def get_topics_for_param(param: str, id: str) -> List[str] | None:
        graphAccess = graphDBdataAccess(get_graph())
        
        QUERY = f"""
        MATCH (n:Concept)
        WHERE $id IN n.{param}
        RETURN n.id AS conceptId, n.uuid[0] AS conceptUuid, n.noteId AS noteId
        """

        parameters = {
            'id': id
        }

        print(f"Query: {QUERY}")
        print(f"Parameters: {parameters}")

        result = graphAccess.execute_query(QUERY, parameters)

        return result
