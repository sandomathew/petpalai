import chromadb
from chromadb.utils import embedding_functions

# Embedding function that is compatible with your LLM (e.g., Llama 3)
# Ollama provides a hostable embedding model like "nomic-embed-text" or "mxbai-embed-large"
# Make sure your Ollama instance is running with this model.
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    model_name="nomic-embed-text",
    url="http://localhost:11434"
)

def get_food_label_collection():
    client = chromadb.Client()
    collection = client.get_or_create_collection(
        name="food_label_collection",
        embedding_function=ollama_ef
    )
    return collection