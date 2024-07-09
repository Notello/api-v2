import json
import logging
from typing import Any, Dict, List, Tuple
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask import current_app
from flask_app.models.Quiz import QuizQuestion

class GraphQueryService():
    DEFAULT_GRAPH_PARAMS = [("ID(n)", "nodeId"), ("LABELS(n)", "nodeLabels"), 
            ("n.fileName", "fileName"), ("n.position", "position"), ("n.id", "conceptId"),("n.description", "description"),
            ("r.type", "relType"), ("ID(relatedNode)", "relatedNodeId"), ("LABELS(relatedNode)", "relatedNodeLabels"),
            ("relatedNode.fileName", "relatedNodeFileName"), ("relatedNode.position", "relatedNodePosition"), 
            ("relatedNode.id", "relatedNodeConceptId"), ("relatedNode.description", "relatedNodeDescription")]
    
    @staticmethod
    def get_graph_for_param(
        key: str, 
        value: str, 
        return_params: List[Tuple[str, str]] = DEFAULT_GRAPH_PARAMS
    ) -> Tuple[Dict[str, List[Dict]], List[Dict[str, Any]]]:
        try:
            graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            return_clause = ", ".join([f"{param[0]} AS {param[1]}" for param in return_params])

            QUERY = f"""
            MATCH (n)
            WHERE n.{key} = $value OR $value IN n.{key}
            OPTIONAL MATCH (n)-[r]->(relatedNode)
            WHERE relatedNode.{key} = $value or $value IN relatedNode.{key}
            RETURN {return_clause}
            """

            parameters = {
                "value": value
            }

            result = graphDb_data_Access.execute_query(QUERY, parameters)

            nodes = {
                'documents': [],
                'chunks': [],
                'concepts': []
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
                        node_info = {'id': node_data['nodeId']}
                        if node_type == 'Document':
                            node_info['fileName'] = node_data.get('fileName')
                        elif node_type == 'Chunk':
                            node_info['position'] = node_data.get('position')
                        elif node_type == 'Concept':
                            node_info['conceptId'] = node_data.get('conceptId')
                            node_info['description'] = node_data.get('description')
                        nodes[node_type.lower() + 's'].append(node_info)

                if related_node_data.get('Id') is not None and related_node_data.get('Labels') is not None:
                    related_node_type = next((label for label in ['Document', 'Chunk', 'Concept'] if label in related_node_data['Labels']), None)
                    if related_node_type:
                        related_node_info = {'id': related_node_data['Id']}
                        if related_node_type == 'Document':
                            related_node_info['fileName'] = related_node_data.get('FileName')
                        elif related_node_type == 'Chunk':
                            related_node_info['position'] = related_node_data.get('Position')
                        elif related_node_type == 'Concept':
                            related_node_info['conceptId'] = related_node_data.get('ConceptId')
                            related_node_info['description'] = related_node_data.get('Description')
                        nodes[related_node_type.lower() + 's'].append(related_node_info)

                if 'nodeId' in node_data and related_node_data.get('Id') is not None and rel_type is not None:
                    relationships.append({
                        "start_node_id": node_data['nodeId'], 
                        "relationship_type": rel_type, 
                        "end_node_id": related_node_data['Id']
                    })

            for node_type in nodes:
                nodes[node_type] = [dict(t) for t in {tuple(d.items()) for d in nodes[node_type]}]

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
        return {'message': 'Not implemented'}, 200
    
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
