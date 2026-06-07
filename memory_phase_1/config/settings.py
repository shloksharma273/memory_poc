from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    arango_host: str = "http://localhost:8529"
    arango_db: str = "memory_poc"
    arango_username: str = "root"
    arango_password: str = "openSesame"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5-coder:7b"
    ollama_embed_model: str = "nomic-embed-text"

    memory_threshold: float = 0.50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
