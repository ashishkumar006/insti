"""Postgres connection pool (psycopg2, py3.8 compatible)."""
from contextlib import contextmanager
from typing import Iterator

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
except Exception:  # pragma: no cover - import-time only
    psycopg2 = None  # type: ignore
    pg_pool = None  # type: ignore

from app.config import cfg

_pool = None


def get_pool():
    global _pool
    if _pool is not None:
        return _pool
    if psycopg2 is None:
        raise RuntimeError("psycopg2 not installed. pip install -r requirements.txt")
    _pool = pg_pool.SimpleConnectionPool(1, 10, dsn=cfg.database_url)
    return _pool


@contextmanager
def get_conn() -> Iterator[object]:
    p = get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        p.putconn(conn)


def run_migrations():
    """Apply SQL files in migrations/ in order."""
    import pathlib
    mig_dir = pathlib.Path(__file__).resolve().parents[2] / "migrations"
    files = sorted(mig_dir.glob("*.sql"))
    with get_conn() as conn:
        cur = conn.cursor()
        for f in files:
            cur.execute(f.read_text(encoding="utf-8"))
