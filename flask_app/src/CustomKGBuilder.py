import logging
from langchain_core.prompts import ChatPromptTemplate


from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_4O_MINI

from flask_app.src.entities.KnowledgeGraph import KnowledgeGraph


def setup_llm(
    text: str,
    summary: str
):
    
    system_prompt = f"""
        - You are a top-tier algorithm designed for extracting information in structured formats to build a detailed knowledge graph. 
        - Your task is to identify as many concepts and entities in the text and relations between them as possible. 
        - You will use the summary of the text provided to you to guide what types of concepts and entities to extract. 
        - You should use the summary to correct any typos in the source text based on the context provided.

        ## IMPORTANT GUIDELINES ##
        - You should add *AS MANY* relations as possible, you should infer relationships between entities and concepts based on the context if necessary.
        - Maintain Entity Consistency: When extracting entities or concepts, it's vital to ensure consistency. 
        - If an entity, such as "John Doe", is mentioned multiple times in the text but is referred to by different names or pronouns 
        (e.g., "Joe", "he"), always use the most complete identifier for that entity.
    """

    user_template = f"""
        Based on the following text and summary, extract *AS MANY* entities/concepts and relationships between them as possible.

        Summary of document:
        {summary}

        Text to extract from:
        {text}
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(KnowledgeGraph)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

class CustomKGBuilder:
    @staticmethod
    def create_knowledge_graph(
        text: str,
        summary: str
    ) -> KnowledgeGraph:
        try:
            logging.info(f"Generating knowledge graph.")
            
            knowledge_graph = setup_llm(
                text=text,
                summary=summary
            )

            result: KnowledgeGraph = knowledge_graph.invoke({})

            logging.info(f"Generated knowledge graph.")

            print(result)

            return result

        except Exception as e:
            logging.exception(f"Error generating knowledge graph: {str(e)}")
            raise