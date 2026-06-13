from app.vectorstore.pinecone_client import vectorstore
from app.config import settings

def get_retriever(doc_types: list[str] = None, top_k: int = 15):
    """
    Creates a Pinecone retriever scoped to the NF QueryGPT namespace.

    Args:
        doc_types: Filter by document type — ["schema", "few_shot", "glossary"].
                   None = retrieve from all types.
        top_k:     Number of chunks to retrieve.

    Why no score threshold:
        Low-scoring but correct chunks get silently dropped with thresholds.
        Better to retrieve more and let the LLM ignore irrelevant ones.
    """
    search_kwargs: dict = {
        "k": top_k,
        "namespace": settings.PINECONE_NAMESPACE,
    }

    if doc_types:
        search_kwargs["filter"] = {
            "doc_type": {"$in": doc_types}
        }

    return vectorstore.as_retriever(
        search_type="similarity",  # no score threshold — don't drop weak hits
        search_kwargs=search_kwargs,
    )

def get_schema_retriever(top_k: int = 5):
    """Retrieve only schema descriptions for the relevant tables."""
    return get_retriever(doc_types=["schema"], top_k=top_k)

def get_few_shot_retriever(top_k: int = 5):
    """Retrieve the most similar NL→SQL examples."""
    return get_retriever(doc_types=["few_shot"], top_k=top_k)

def get_full_retriever(top_k: int = 15):
    """Retrieve schema + few-shot + glossary — the full context."""
    return get_retriever(doc_types=None, top_k=top_k)
