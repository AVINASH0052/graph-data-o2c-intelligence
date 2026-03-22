import duckdb
from pathlib import Path
from app.core.config import settings

_conn: duckdb.DuckDBPyConnection | None = None


def get_db() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        _conn = duckdb.connect(settings.db_path)
    return _conn


def close_db():
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
