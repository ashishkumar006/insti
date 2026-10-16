"""Background self-ping: keeps a free-tier web service from sleeping.

Render (and similar free hosts) spin a service down after ~15 minutes with no
inbound traffic. Requesting the service's own PUBLIC URL counts as traffic, so a
small background thread pinging /api/v1/health every N minutes prevents sleep
between visits.

Hard limit, by design: a self-ping cannot WAKE a sleeping service - while asleep
no code runs, so there is nobody to send the ping. For wake-from-sleep plus
downtime alerts, pair this with an external monitor (e.g. UptimeRobot). Also
note: /api/v1/health touches Postgres, so this keeps a scale-to-zero database
warm too.

Enabled only when the host publishes its public URL (Render sets
RENDER_EXTERNAL_URL automatically). No-op in local dev.
"""
import os
import threading
import time

_lock = threading.Lock()
_started = False


def _loop():
    # short first delay: never compete with boot-time migrations
    first = min(20.0, _interval())
    if first > 0:
        time.sleep(first)
    import httpx
    url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/") + "/api/v1/health"
    while True:
        try:
            httpx.get(url, timeout=15.0)
        except Exception:
            pass  # never let keep-alive noise crash anything
        wait = _interval()
        if wait <= 0:
            return
        time.sleep(wait)


def _interval() -> float:
    secs = os.getenv("KEEPALIVE_SECONDS", "")
    if secs:
        try:
            return max(0.0, float(secs))
        except ValueError:
            pass
    return float(int(os.getenv("KEEPALIVE_MINUTES", "8") or 0) * 60)


def start_keepalive():
    """Start the self-ping thread (idempotent, no-op on unsupported hosts)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    if _interval() <= 0:
        return
    if not os.getenv("RENDER_EXTERNAL_URL"):
        return  # local dev / hosts without a published URL
    threading.Thread(target=_loop, daemon=True).start()
