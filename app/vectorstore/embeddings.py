from langchain_core.embeddings import Embeddings
from pinecone import Pinecone

class PineconeLlamaEmbeddings(Embeddings):
    """
    Custom embeddings using Pinecone's hosted llama-text-embed-v2.

    CRITICAL: input_type must differ between indexing and querying.
    - Indexing (embed_documents): input_type = "passage"
    - Querying (embed_query):     input_type = "query"
    Mismatching these is the #1 cause of low similarity scores.
    """

    def __init__(self, pc_client: Pinecone, model_name: str = "llama-text-embed-v2"):
        self.pc = pc_client
        self.model = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.pc.inference.embed(
            model=self.model,
            inputs=texts,
            parameters={"input_type": "passage", "truncate": "END"},
        )
        return [item.values for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        response = self.pc.inference.embed(
            model=self.model,
            inputs=[text],
            parameters={"input_type": "query", "truncate": "END"},
        )
        return response.data[0].values
