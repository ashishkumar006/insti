"""App factory. Old flat main.py left untouched; this is the clean entrypoint."""
import os
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import student, admin, system

app = FastAPI(title="CampusGuide")


@app.on_event("startup")
def _startup():
    try:
        from app.storage.pg_autostart import ensure_postgres
        ensure_postgres()
        from app.storage.db import run_migrations, get_conn
        from app.storage.repositories.users_repo import ensure_seed_admin
        run_migrations()
        with get_conn() as conn:
            ensure_seed_admin(conn)
    except Exception as e:  # noqa - never crash boot on DB down
        print("[startup] db not ready:", e)
    try:
        from app.keepalive import start_keepalive
        start_keepalive()  # free hosts sleep after ~15 idle min; self-ping prevents it
    except Exception:
        pass


app.include_router(system.router, prefix="/api/v1")
app.include_router(student.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1/admin")

# Student + admin UIs live inside app/web/ so the whole app ships as one folder.
_web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
for _p, _sub in (("/student", "student"), ("/admin", "admin"), ("/assets", "assets")):
    _d = os.path.join(_web, _sub)
    if os.path.isdir(_d):
        app.mount(_p, StaticFiles(directory=_d, html=True), name=_p.strip("/"))


@app.get("/")
def root():
    return RedirectResponse("/student")
