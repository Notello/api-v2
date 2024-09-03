import logging
from langchain_core.prompts import ChatPromptTemplate


from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_4O_MINI

from flask_app.src.entities.KnowledgeGraph import KnowledgeGraph


def setup_llm(text: str, summary: str):
    system_prompt = """
        - You are a top-tier algorithm designed for extracting information in structured formats to build a detailed knowledge graph. 
        - Your task is to identify as many concepts and entities in the text and relations between them as possible. 
        - You will provide at least three relationships for every entity you identify.
        - You will also provide descriptions for each node as they would appear on a flashcard.
        - You will use the summary of the text provided to you to guide what types of concepts and entities to extract. 
        - You should use the summary to correct any typos in the source text based on the context provided.
        - You will always output node ids in all lowercase with spaces between words.

        # Output Format #
        You will output the knowledge graph in the following format, it is extremely important that you follow this format:
        nodes: A list of nodes, where each node is a dictionary with the following keys:
            id: The unique identifier of the node. Must be all lowercase with spaces between words.
            description: The description of the node as would be read on a flashcard.
        relationships: A list of relationships, where a relationship is a dictionary with the following keys:
            source: The unique identifier of the source node, must match a node in the nodes list. Must be all lowercase with spaces between words.
            target: The unique identifier of the target node, must match a node in the nodes list. Must be all lowercase with spaces between words.
            type: The type of the relationship.

        ## IMPORTANT GUIDELINES ##
        - You should add *AS MANY* relations as possible, you should infer at least three relationships oer each entity.
        - Maintain Entity Consistency: When extracting entities or concepts, it's vital to ensure consistency. 
        - If an entity, such as "John Doe", is mentioned multiple times in the text but is referred to by different names or pronouns (e.g., "Joe", "he"), always use the most complete identifier for that entity.

        ## FINAL POINT ##
        It is extremely important that you extract as many nodes and relationships as possible. You should aim for 20-30 nodes minimum.
    """

    user_template = f"""
        Based on the following text and summary, extract *AS MANY* entities/concepts and relationships between them as possible.
        Please remember to provide a description for each node as it would appear on a flashcard.

        Summary of document:
        {summary}

        Text to extract from:
        {text}
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(KnowledgeGraph, include_raw=True)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

class CustomKGBuilder:
    @staticmethod
    def create_knowledge_graph(text: str, summary: str) -> KnowledgeGraph:
        try:
            logging.info("Generating knowledge graph.")
            
            llm_chain = setup_llm(text=text, summary=summary)

            try:
                result = llm_chain.invoke({"text": text, "summary": summary})
                logging.info(f"LLM output: {result}")

                final_result = KnowledgeGraph.parse_llm_output(result)
                logging.info(f"Final result: {final_result}")

                return final_result

            except Exception as e:
                logging.exception(f"Error processing LLM output: {str(e)}")
                # Return an empty KnowledgeGraph if there's an error
                return KnowledgeGraph(nodes=[], relationships=[])

        except Exception as e:
            logging.exception(f"Error in create_knowledge_graph: {str(e)}")
            # Return an empty KnowledgeGraph if there's an error
            return KnowledgeGraph(nodes=[], relationships=[])