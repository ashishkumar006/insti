"""Minimal gateway-compatible shim on :8109 (the real llm_gatewayV9 sources were lost).

Implements just what the old stack (gateway_client.py) needs:
  POST /v1/embed {text, task_type} -> {provider,model,embedding,dim,latency_ms,attempted}
  POST /v1/chat  {messages,system,tools,...} -> {text,tool_calls,...}
Backed by local Ollama (nomic-embed-text + phi4-mini tools). No keys, no gateway.
"""
import time
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="GatewayShim")


class EmbedReq(BaseModel):
    text: str
    task_type: str = "retrieval_document"
    provider: Optional[str] = None


class ChatReq(BaseModel):
    messages: Optional[List[dict]] = None
    prompt: Optional[str] = None
    system: Optional[str] = None
    tools: Optional[list] = None
    tool_choice: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.3
    provider: Optional[str] = None


def _ollama():
    from app.llm.ollama_adapter import OllamaAdapter
    return OllamaAdapter()


@app.post("/v1/embed")
def embed(req: EmbedReq):
    t0 = time.time()
    llm = _ollama()
    vec = llm.embed_query(req.text)["embedding"] if req.task_type == "retrieval_query" else llm.embed(req.text)["embedding"]
    return {"provider": "ollama", "model": "nomic-embed-text", "embedding": vec,
            "dim": len(vec), "latency_ms": int((time.time() - t0) * 1000), "attempted": []}


@app.post("/v1/chat")
def chat(req: ChatReq):
    import httpx
    from app.config import cfg
    t0 = time.time()
    msgs = list(req.messages or [])
    if req.prompt is not None:
        msgs.append({"role": "user", "content": req.prompt})
    if req.system:
        msgs = [{"role": "system", "content": req.system}] + msgs
    otools = []
    for t in (req.tools or []):
        otools.append({"type": "function", "function": {
            "name": t.get("name", ""), "description": t.get("description", ""),
            "parameters": t.get("input_schema") or {"type": "object", "properties": {}}}})
    body = {"model": cfg.ollama_chat_model, "messages": msgs, "stream": False,
            "options": {"temperature": req.temperature, "num_predict": req.max_tokens}}
    if otools:
        body["tools"] = otools
    def _call(msgs):
        with httpx.Client(timeout=180.0) as c:
            r = c.post(cfg.ollama_url.rstrip("/") + "/api/chat", json={
                "model": cfg.ollama_chat_model, "messages": msgs, "stream": False,
                "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
                **({"tools": otools} if otools else {})})
            r.raise_for_status()
            return r.json().get("message") or {}
    msg = _call(msgs)
    if otools and not (msg.get("tool_calls") or []) and not any(
            m.get("role") == "tool" for m in msgs):
        # First turn and the model ignored the tools (small local models do
        # this when a separate system role is present); retry once with the
        # system text folded into the user turn. Later turns (with tool
        # results) are returned as-is.
        flat = list(msgs)
        sys_txt = ""
        rest = []
        for m in flat:
            if m.get("role") == "system":
                sys_txt += str(m.get("content", "")) + "\n"
            else:
                rest.append(m)
        if rest and sys_txt:
            first = dict(rest[0])
            first["content"] = "System instructions:\n" + sys_txt + "\n" + str(first.get("content", ""))
            msg = _call([first] + rest[1:])
    tcs = []
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        tcs.append({"id": tc.get("id", ""), "name": fn.get("name", ""),
                    "arguments": fn.get("arguments") or {}})
    return {"provider": "ollama", "model": cfg.ollama_chat_model,
            "text": msg.get("content") or "", "tool_calls": tcs,
            "stop_reason": "tool_use" if tcs else "end_turn",
            "input_tokens": 0, "output_tokens": 0,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
            "latency_ms": int((time.time() - t0) * 1000),
            "tool_call_dialect": "native" if tcs else "none",
            "reasoning_applied": False, "parsed": None, "attempted": []}


@app.get("/v1/embedders")
def embedders():
    return {"order": ["ollama"], "models": {"ollama": "nomic-embed-text"},
            "fixed_dim": 768, "live": {}, "today": {}}


@app.get("/v1/status")
def status():
    return {"order": ["ollama"], "live": {}, "today": {}}


@app.get("/")
def root():
    return {"service": "GatewayShim", "backend": "local-ollama"}
