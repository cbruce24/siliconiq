"""Database connection and schema initialization."""
import sqlite3
import pathlib

DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "siliconiq.db"
SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"


def get_connection(db_path: str | pathlib.Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str | pathlib.Path = DB_PATH) -> None:
    db_path = pathlib.Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql = SCHEMA_PATH.read_text()
    with get_connection(db_path) as conn:
        conn.executescript(sql)
