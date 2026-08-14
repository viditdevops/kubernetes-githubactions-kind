"""
db.py - Database connectivity layer.

Credentials arrive as environment variables sourced from the Vault Agent
Injector sidecar (see entrypoint.sh) - never hardcoded, never read from a
Kubernetes Secret object.
"""
import os
import psycopg2

REQUIRED_DB_VARS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]


def _load_db_config() -> dict:
    missing = [v for v in REQUIRED_DB_VARS if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required DB env vars: {missing}. "
            f"Expected these to be sourced from /vault/secrets/db-env at container "
            f"startup (see entrypoint.sh + VAULT-SETUP.md). No hardcoded fallback exists."
        )
    return {
        "host": os.environ["DB_HOST"],
        "port": os.environ["DB_PORT"],
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


DB_CONFIG = _load_db_config()


def get_connection():
    return psycopg2.connect(connect_timeout=3, **DB_CONFIG)


def check_connection() -> None:
    conn = get_connection()
    conn.close()


def init_schema() -> None:
    """Ensure required tables exist. Called once at app startup."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def fetch_recent_items(limit: int = 10):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, created_at FROM items ORDER BY id DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close()
        return [{"id": r[0], "name": r[1], "created_at": str(r[2])} for r in rows]
    finally:
        conn.close()


def insert_item(name: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO items (name) VALUES (%s) RETURNING id", (name,))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return new_id
    finally:
        conn.close()
