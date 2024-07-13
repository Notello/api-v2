import json
import logging
import random
from typing import Any, Dict, List, Tuple
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask import current_app
from flask_app.models.Quiz import QuizQuestion

class GraphQueryService():

    @staticmethod
    def get_com_string(communityType: str, communityId: str) -> str:
        return f"{communityType}_{communityId}_community"

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
    def get_topic_graph(courseId: str = None,
                        noteId: str = None, 
                        specifierParam: str = None,
                        topics: List[str] = []
                    ) -> str | None:
        if specifierParam == 'noteId':
            return GraphQueryService.get_topic_graph_from_param(param="noteId", id=noteId, topics=topics)
        elif specifierParam == 'courseId':
            return GraphQueryService.get_topic_graph_from_param(param="courseId", id=courseId, topics=topics)
        else:
            return None

        
    @staticmethod
    def get_topic_graph_from_param(param: str, 
                                   id: str, 
                                   topics: List[str] = None
                                   ) -> str | None:

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
            communities = random.sample(communities, min(3, len(communities)))


        MAIN_QUERY = f"""
        // Match Concept-Concept relationships
        MATCH (c1:Concept)-[r]-(c2:Concept)
        WHERE c1['{com_string}'] IN {communities} AND c2['{com_string}'] IN {communities}

        // Match Chunk nodes
        WITH COLLECT(DISTINCT {{source: c1.id, type: r.type, target: c2.id}}) AS conceptRels
        MATCH (chunk:Chunk)
        WHERE chunk['{com_string}'] IN {communities}

        RETURN 
            conceptRels,
            COLLECT(DISTINCT {{
                id: chunk.id,
                text: chunk.text,
                noteId: chunk.noteId,
                position: chunk.position
            }}) AS chunks
        """

        result = graphAccess.execute_query(MAIN_QUERY)

        return result[0]
    
    @staticmethod
    def get_quiz_questions_by_id(quizId: str) -> List[QuizQuestion]:
        graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

        QUERY = f"""
        MATCH (q:QuizQuestion)
        WHERE q.quizId = $quizId
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
