import os
from dotenv import load_dotenv

load_dotenv()

# ArangoDB
ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DB", "memory_poc")
ARANGO_USERNAME = os.getenv("ARANGO_USERNAME", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "openSesame")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5-coder:7b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Retrieval
TOP_K_VECTOR = int(os.getenv("TOP_K_VECTOR", "5"))
TOP_K_BM25 = int(os.getenv("TOP_K_BM25", "5"))
TOP_K_GRAPH = int(os.getenv("TOP_K_GRAPH", "5"))
