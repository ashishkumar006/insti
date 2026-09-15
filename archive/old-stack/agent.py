from typing import Optional
from dataclasses import dataclass

from gateway_client import GatewayClient
from retriever import HybridRetriever


FETCH_TOOL = {
    "name": "fetch_chunks",
    "description": (
        "Search the document corpus for relevant passages. "
        "Call this when you need factual context from the uploaded documents to answer the user's question. "
        "Always pass a specific, information-rich query string."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Specific search query describing what information is needed.",
            }
        },
        "required": ["query"],
    },
}


SYSTEM_PROMPT = (
    "You are a retrieval-augmented assistant. "
    "Answer the user's question using ONLY the document chunks provided in the tool results. "
    "If the retrieved chunks do not contain enough information to answer, say so honestly rather than guessing. "
    "Synthesize information from multiple chunks when relevant, citing chunk identifiers inline like [chunk_id]. "
    "Keep answers concise and focused."
)


@dataclass
class AgentResult:
    answer: str
    tool_calls_used: int
    sources: list


def run_agent(
    query: str,
    retriever: HybridRetriever,
    gateway: GatewayClient,
    max_turns: int = 4,
    provider: Optional[str] = None,
) -> AgentResult:
    messages = [{"role": "user", "content": query}]
    tool_calls_used = 0
    gathered_chunks: list = []
    tried_providers = set()

    for _ in range(max_turns):
        chat_provider = provider if provider not in tried_providers else None
        try:
            resp = gateway.chat(
                prompt=None,
                messages=messages,
                system=SYSTEM_PROMPT,
                tools=[FETCH_TOOL],
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.3,
                provider=chat_provider,
            )
        except RuntimeError as e:
            msg = str(e)
            if provider and provider not in tried_providers:
                tried_providers.add(provider)
                continue
            if "thought_signature" in msg.lower() or "thoughtSignature" in msg:
                if provider and provider not in tried_providers:
                    tried_providers.add(provider)
                    continue
                raise
            raise

        tcs = resp.get("tool_calls", [])
        if not tcs:
            return AgentResult(
                answer=resp.get("text", ""),
                tool_calls_used=tool_calls_used,
                sources=[c["chunk_id"] for c in gathered_chunks],
            )

        for tc in tcs:
            if tc["name"] == "fetch_chunks":
                tool_calls_used += 1
                search_query = (tc.get("arguments") or {}).get("query", query)
                chunks = retriever.retrieve(search_query)
                gathered_chunks.extend(chunks)

                context_parts = []
                for c in chunks[:6]:
                    context_parts.append(
                        f"[{c['chunk_id']} | score={c['score']:.4f}]\n{c['text']}"
                    )
                context = "\n\n---\n\n".join(context_parts) if context_parts else "(no matching chunks found)"

                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": tc.get("id", ""),
                                "name": "fetch_chunks",
                                "arguments": tc.get("arguments", {}),
                                "provider_meta": tc.get("provider_meta"),
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "content": context,
                        "tool_call_id": tc.get("id", ""),
                        "tool_name": "fetch_chunks",
                    }
                )

    return AgentResult(
        answer="(agent stopped after max turns — partial answer may be incomplete)",
        tool_calls_used=tool_calls_used,
        sources=[c["chunk_id"] for c in gathered_chunks],
    )
