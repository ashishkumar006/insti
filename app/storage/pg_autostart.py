"""Start the bundled Postgres automatically so nobody runs anything by hand.

Called at API startup before migrations. If port 5432 is already open, does
nothing. Otherwise tries `pg_ctl start` on var/pgsql (user console: works;
restricted sandboxes: fails silently and boot continues degraded).
"""
import os
import socket
import subprocess
import time
from urllib.parse import urlparse


def _open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def ensure_postgres(timeout_s: int = 60) -> bool:
    from app.config import cfg
    try:
        u = urlparse(cfg.database_url)
        host, port = u.hostname or "127.0.0.1", u.port or 5432
    except Exception:
        return False
    if _open(host, port):
        return True
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    exe = ".exe" if os.name == "nt" else ""
    pg_ctl = os.path.join(root, "var", "pgsql", "bin", "pg_ctl" + exe)
    pgdata = os.path.join(root, "var", "pgdata")
    log = os.path.join(root, "var", "logs", "pg.log")
    if not (os.path.isfile(pg_ctl) and os.path.isfile(os.path.join(pgdata, "PG_VERSION"))):
        return False
    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        subprocess.Popen([pg_ctl, "-D", pgdata, "-l", log, "-w", "-t", "30", "start"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL)
    except Exception:
        return False
    end = time.time() + timeout_s
    while time.time() < end:
        if _open(host, port):
            return True
        time.sleep(2)
    return _open(host, port)
