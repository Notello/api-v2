import logging
import random
from typing import Any, Dict, List, Tuple
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask import current_app

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

        return [
        
            ("ID(n)", "nodeId"), ("LABELS(n)", "nodeLabels"), 
            ("n.position", "position"), ("n.fileName", "fileName"), 
            ("n.id", "conceptId"), ("n.description", "description"), 
            (f"n['{com_string}']", "communityId"),


            ("rel.type", "relType"), 
            
            ("ID(r)", "relatedNodeId"), ("LABELS(r)", "relatedNodeLabels"), 
            ("r.position", "relatedNodePosition"), ("r.fileName", "relatedNodeFileName"),

            ("r.id", "relatedNodeConceptId"), ("r.description", "relatedNodeDescription"),
            (f"r['{com_string}']", "relatedNodeCommunityId"),
            ]
    
    
    
    @staticmethod
    def get_graph_for_param(
        key: str, 
        value: str, 
        return_params: List[Tuple[str, str]] = None
    ) -> Tuple[Dict[str, List[Dict]], List[Dict[str, Any]]]:
        try:
            graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            final_params = return_params = return_params if return_params is not None else \
                GraphQueryService.get_default_graph_params(communityType=key, communityId=value)

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

                for param in return_params:
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
                        elif node_type == 'Concept':
                            node_info['conceptId'] = node_data.get('conceptId')
                            node_info['description'] = node_data.get('description')
                        
                        if 'communityId' in node_data and 'communityId' not in node_info:
                            node_info['communityId'] = node_data['communityId']
                        
                        nodes[node_type.lower() + 's'][node_data['nodeId']] = node_info

                if related_node_data.get('Id') is not None and related_node_data.get('Labels') is not None:
                    related_node_type = next((label for label in ['Document', 'Chunk', 'Concept'] if label in related_node_data['Labels']), None)
                    if related_node_type:
                        related_node_info = nodes[related_node_type.lower() + 's'].get(related_node_data['Id'], {})
                        related_node_info['id'] = related_node_data['Id']
                        if related_node_type == 'Document':
                            related_node_info['fileName'] = related_node_data.get('FileName')
                        elif related_node_type == 'Chunk':
                            related_node_info['position'] = related_node_data.get('Position')
                        elif related_node_type == 'Concept':
                            related_node_info['conceptId'] = related_node_data.get('ConceptId')
                            related_node_info['description'] = related_node_data.get('Description')
                        
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
    def get_topic_graph(id: str | None = None, 
                        specifierParam: str = None,
                        topics: List[str] = [],
                        num_communities: int = None
                    ) -> str | None:
                
        communities = GraphQueryService.get_communities_for_param(
            param=specifierParam, 
            id=id, 
            topics=topics,
            num_communities=num_communities
            )

        if len(communities) == 0:
            return None

        return GraphQueryService.get_topic_graph_for_communities(
            param=specifierParam, 
            id=id, 
            communities=communities
            )

        
    @staticmethod
    def get_communities_for_param(param: str, 
                                   id: str, 
                                   topics: List[str] = None,
                                   num_communities: int = None
                                   ) -> str | None:
        
        logging.info(f"Getting topic graph for {param} with id {id}")

        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
        com_string = GraphQueryService.get_com_string(communityType=param, communityId=id)

        
        parameters = {
            'value': id,
        }

        communities = []

        if len(topics) > 0:
            TOPIC_COMMUNITIES_QUERY = f"""
            MATCH (n)
            WHERE ANY(label IN labels(n) WHERE label IN ['Concept', 'Chunk']) AND $value in n.{param}
            WITH n
            WHERE ANY(topic IN {topics} WHERE n.id = topic)
            RETURN COLLECT(DISTINCT n['{com_string}']) AS all_community_ids
            """

            topics_communities = graphAccess.execute_query(TOPIC_COMMUNITIES_QUERY, parameters)

            communities = topics_communities[0]['all_community_ids']
        else:
            ALL_COMMUNITIES_QUERY = f"""
            MATCH (n)
            WHERE $value in n.{param}
            RETURN COLLECT(DISTINCT n['{com_string}']) AS all_community_ids
            """

            topics_communities = graphAccess.execute_query(ALL_COMMUNITIES_QUERY, parameters)

            communities = topics_communities[0]['all_community_ids']
            if num_communities is not None:
                communities = random.sample(communities, min(num_communities, len(communities)))

        return communities
    
    @staticmethod
    def get_topic_graph_for_communities(
        param: str,
        id: str,
        communities: List[str],
        num_rels: int = 50,
        num_chunks: int = 3
    ):
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
        com_string = GraphQueryService.get_com_string(communityType=param, communityId=id)

        MAIN_QUERY = f"""
        // First, collect up to num_rels relationships
        MATCH (c1:Concept)-[r]-(c2:Concept)
        WHERE c1['{com_string}'] IN {communities}
        AND c2['{com_string}'] IN {communities}
        WITH c1, r, c2
        LIMIT {num_rels}

        WITH COLLECT(DISTINCT {{
            source: c1.id, 
            sourceUUID: c1.uuid,
            type: r.type, 
            target: c2.id,
            targetUUID: c2.uuid
            }}) AS conceptRels, 
            COLLECT(DISTINCT c1) + COLLECT(DISTINCT c2) AS allConcepts

        // Then, match up to num_chunks chunks related to these concepts
        MATCH (chunk:Chunk)
        WHERE chunk['{com_string}'] IN {communities}
        WITH conceptRels, chunk
        LIMIT {num_chunks}

        RETURN 
        conceptRels, 
        COLLECT(DISTINCT {{
            id: chunk.id,
            text: chunk.text,
            noteId: chunk.noteId,
            position: chunk.position,
            document_name: chunk.document_name
        }}) AS chunks
        """

        result = graphAccess.execute_query(query=MAIN_QUERY)

        if len(result) == 0:
            return None
        
        return result[0]

    @staticmethod
    def get_importance_graph_by_param(param: str, id: str) -> str | None:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
        pagerank_string = GraphQueryService.get_page_rank_string(param=param, id=id)
        print(pagerank_string)

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
                relevanceScore: relevanceScore
                }})[0..3] AS topChunks,
            meanScore, stdDevScore, q3Score, avgConnections, avgPageRank, thresholdMultiplier, prString

        // Return the results
        RETURN DISTINCT
            c.id AS conceptId,
            pageRank AS conceptPageRank,
            connectionCount,
            importanceScore,
            [neighbor IN neighbors | {{id: neighbor.id, pageRank: neighbor[prString]}}] AS relatedConcepts,
            topChunks,
            meanScore,
            stdDevScore,
            q3Score,
            avgConnections,
            avgPageRank,
            thresholdMultiplier  // Include this to see the applied threshold
        ORDER BY importanceScore DESC
        """

        parameters = {
            "id": id,
            "pagerank_string": pagerank_string
        }

        print(QUERY)

        try:
            result = graphAccess.execute_query(QUERY, parameters)   
            print(result)
            return result
        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None