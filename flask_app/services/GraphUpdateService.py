import networkx as nx
import numpy as np
from flask_app.services.SupaGraphService import SupaGraphService

class GraphUpdateService:
    @staticmethod
    def update_graph_positions(courseId):
        graph = SupaGraphService.get_graph_for_param(param='courseId', id=courseId, courseId=courseId)
        relationships = graph['relationships']
        topics = graph['topics']

        G = nx.Graph()

        for topic in topics:
            G.add_node(topic['id'], name=topic['name'])

        for rel in relationships:
            G.add_edge(rel['topicId'], rel['relatedTopicId'])

        positions = nx.spring_layout(G, k=1, iterations=50)

        pos_array = np.array(list(positions.values()))
        min_x, min_y = pos_array.min(axis=0)
        max_x, max_y = pos_array.max(axis=0)

        normalized_positions = {
            node: ((pos[0] - min_x) / (max_x - min_x), 
                   (pos[1] - min_y) / (max_y - min_y))
            for node, pos in positions.items()
        }

        topics_with_positions = []
        for topic in topics:
            pos = normalized_positions.get(topic['id'], (0.5, 0.5))
            topic['x'] = pos[0]
            topic['y'] = pos[1]
            topics_with_positions.append(topic)

        SupaGraphService.update_topics(topics_with_positions)