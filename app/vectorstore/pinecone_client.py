from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from app.config import settings
from app.vectorstore.embeddings import PineconeLlamaEmbeddings

# Singleton instances
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
embeddings = PineconeLlamaEmbeddings(pc, model_name=settings.EMBEDDING_MODEL)

vectorstore = PineconeVectorStore(
    index_name=settings.PINECONE_INDEX_NAME,
    embedding=embeddings,
)
