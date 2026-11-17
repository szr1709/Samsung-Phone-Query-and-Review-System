
from agents.tools import retrieve_phone_information
from chatbot.prompt import build_prompt
from chatbot.ollama_client import generate_response


class SpecificationRetrievalAgent:
    """
    Agent 1: Retrieves phone specifications
    from PostgreSQL and ChromaDB.
    """

    def run(self, question):
        print("\n[Agent 1] Retrieving phone information...")

        result = retrieve_phone_information(question)

        if not result["success"]:
            return None

        print("[Agent 1] Information retrieved successfully.")

        return result["context"]


class ReviewGenerationAgent:
    """
    Agent 2: Generates a detailed phone review
    using retrieved information.
    """

    def run(self, question, context):
        print("\n[Agent 2] Generating phone review...")

        prompt = build_prompt(
            question=question,
            sql_context=context,
            semantic_context=""
        )

        review = generate_response(
            prompt,
            temperature=0.2,
            num_predict=2200
        )

        print("[Agent 2] Review generation completed.")

        return review


class PhoneReviewCrew:
    """
    Coordinates the two agents.
    """

    def __init__(self):
        self.retrieval_agent = SpecificationRetrievalAgent()
        self.review_agent = ReviewGenerationAgent()

    def run(self, question):

        # Agent 1: Retrieve evidence
        context = self.retrieval_agent.run(question)

        if not context:
            return "No relevant phone information found."

        # Agent 2: Generate review
        review = self.review_agent.run(question, context)

        return review
