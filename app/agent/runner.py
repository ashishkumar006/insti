"""Agent runner. Depends on LLM protocol only."""
from dataclasses import dataclass
from typing import List


FETCH_TOOL = {
    "name": "fetch_chunks",
    "description": "Search official campus documents. Call when factual context is needed.",
    "input_schema": {"type": "object", "properties": {
        "query": {"type": "string"}}, "required": ["query"]},
}

SYSTEM_PROMPT = (
    "You are a helpful IIT Madras campus assistant. "
    "Answer ONLY from document chunks in tool results. "
    "If chunks lack the answer, say so honestly. "
    "Cite chunk ids inline like [chunk_id]. Keep answers concise and warm."
)


@dataclass
class AgentResult:
    answer: str
    tool_calls_used: int
    sources: List[str]


def run_agent(query: str, retriever, llm, max_turns: int = 4) -> AgentResult:
    from typing import List as _L
    messages = [{"role": "user", "content": query}]
    gathered: _L[dict] = []
    calls = 0
    for _ in range(max_turns):
        resp = llm.chat(messages=messages, system=SYSTEM_PROMPT,
                        tools=[FETCH_TOOL], tool_choice="auto",
                        max_tokens=1024, temperature=0.3)
        tcs = resp.get("tool_calls", []) or []
        if not tcs:
            return AgentResult(resp.get("text", ""), calls, [c["chunk_id"] for c in gathered])
        for tc in tcs:
            if tc.get("name") != "fetch_chunks":
                continue
            calls += 1
            q = (tc.get("arguments") or {}).get("query", query)
            chunks = retriever.retrieve(q)
            gathered.extend(chunks)
            parts = ["[{} | {:.4f}]\n{}".format(c["chunk_id"], c["score"], c["text"])
                     for c in chunks[:6]]
            ctx = "\n\n---\n\n".join(parts) if parts else "(no matching chunks)"
            messages.append({"role": "assistant", "content": "",
                             "tool_calls": [{"id": tc.get("id", ""), "name": "fetch_chunks",
                                             "arguments": tc.get("arguments", {})}]})
            messages.append({"role": "tool", "content": ctx,
                             "tool_call_id": tc.get("id", ""), "tool_name": "fetch_chunks"})
    return AgentResult("(stopped after max turns)", calls, [c["chunk_id"] for c in gathered])
