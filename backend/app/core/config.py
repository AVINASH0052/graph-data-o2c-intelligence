from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "mistralai/mistral-large-3-675b-instruct-2512"
    data_dir: str = str(BASE_DIR / "data")
    db_path: str = str(BASE_DIR / "data" / "o2c.duckdb")
    graph_cache_path: str = str(BASE_DIR / "data" / "graph_cache.pkl")
    enable_louvain: bool = False
    cors_origins: str = "*"
    max_graph_nodes: int = 5000  # cap for frontend perf

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
