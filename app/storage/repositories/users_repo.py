"""Admin auth: bcrypt passwords + JWT."""
import datetime
import bcrypt
import jwt

from app.config import cfg


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_password(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False


def make_token(user_id: str, email: str) -> str:
    exp = datetime.datetime.utcnow() + datetime.timedelta(hours=cfg.jwt_hours)
    return jwt.encode({"sub": user_id, "email": email, "exp": exp},
                      cfg.jwt_secret, algorithm="HS256")


def read_token(token: str):
    try:
        return jwt.decode(token, cfg.jwt_secret, algorithms=["HS256"])
    except Exception:
        return None


def ensure_seed_admin(conn):
    """Create first admin from env once; existing data untouched."""
    if not cfg.admin_email or not cfg.admin_password:
        return
    cur = conn.cursor()
    cur.execute("SELECT id FROM admin_users WHERE email=%s", (cfg.admin_email.strip().lower(),))
    if cur.fetchone():
        return
    cur.execute("INSERT INTO admin_users(email,name,password_hash) VALUES(%s,%s,%s)",
                (cfg.admin_email.strip().lower(), "Admin", hash_password(cfg.admin_password)))


def verify_login(conn, email: str, password: str):
    cur = conn.cursor()
    cur.execute("SELECT id,email,password_hash,is_active FROM admin_users WHERE email=%s", (email,))
    r = cur.fetchone()
    if not r or not r[3] or not check_password(password, r[2]):
        return None
    return {"id": str(r[0]), "email": r[1]}
