#!/usr/bin/env python3
"""Local mock Arena stack for offline starter-kit testing.

Runs three services expected by the starter-kit:
- REST API on :8000
- MCP SSE server on :5001
- OpenAI-compatible proxy on :4001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from mcp.server.fastmcp import FastMCP

EXPECTED_ANSWER = "Alice, Bob, Charlie, David, Eve"
CHALLENGE_ID = "mock-challenge-001"
PUZZLE_ID = "mock-puzzle-001"
MAX_TIME_S = 120
USAGE_SCOPE = "mock-round-1"
DEFAULT_MODELS = [
    "mock-reasoner-small",
    "mock-reasoner-large",
    "mock-fast-general",
]
CLUES: dict[str, str] = {
    "clue_1": "Alice finished before Bob.",
    "clue_2": "Bob finished before Charlie.",
    "clue_3": "Charlie finished before David.",
    "clue_4": "David finished before Eve.",
}


def _normalize_answer(answer: str) -> str:
    parts = [part.strip().lower() for part in str(answer or "").split(",") if part.strip()]
    return ",".join(parts)


@dataclass
class SessionData:
    session_id: str
    agent_id: str
    agent_name: str
    status: str
    started_at: float
    thoughts: list[str] = field(default_factory=list)
    draft: str = ""
    answer: str = ""
    score: dict[str, Any] | None = None
    client_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageData:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens += max(0, int(prompt_tokens))
        self.completion_tokens += max(0, int(completion_tokens))
        self.total_tokens += max(0, int(prompt_tokens) + int(completion_tokens))

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class MockArenaState:
    def __init__(self) -> None:
        self._lock = Lock()
        self.sessions: dict[str, SessionData] = {}
        self.usage_by_agent: dict[str, UsageData] = {}
        self.usage_by_scope_agent: dict[tuple[str, str], UsageData] = {}

    def upsert_session(self, agent_id: str, agent_name: str) -> SessionData:
        with self._lock:
            existing = self.sessions.get(agent_id)
            if existing:
                existing.agent_name = agent_name or existing.agent_name
                existing.status = "registered"
                return existing
            session = SessionData(
                session_id=f"mock-{uuid.uuid4().hex[:10]}",
                agent_id=agent_id,
                agent_name=agent_name or agent_id,
                status="registered",
                started_at=time.time(),
            )
            self.sessions[agent_id] = session
            return session

    def get_session(self, agent_id: str) -> SessionData | None:
        with self._lock:
            return self.sessions.get(agent_id)

    def set_status(self, agent_id: str, status: str, client_metrics: dict[str, Any] | None = None) -> bool:
        with self._lock:
            session = self.sessions.get(agent_id)
            if not session:
                return False
            session.status = status
            if client_metrics:
                session.client_metrics = dict(client_metrics)
            return True

    def add_thought(self, agent_id: str, thought: str) -> bool:
        with self._lock:
            session = self.sessions.get(agent_id)
            if not session:
                return False
            session.thoughts.append(str(thought or "").strip())
            return True

    def set_draft(self, agent_id: str, draft: str) -> bool:
        with self._lock:
            session = self.sessions.get(agent_id)
            if not session:
                return False
            session.draft = draft
            return True

    def submit(
        self,
        agent_id: str,
        answer: str,
        client_metrics: dict[str, Any] | None = None,
    ) -> SubmitResult:
        with self._lock:
            session = self.sessions.get(agent_id)
            if not session:
                raise KeyError(agent_id)

            elapsed_ms = int(max(0, (time.time() - session.started_at) * 1000))
            normalized = _normalize_answer(answer)
            expected = _normalize_answer(EXPECTED_ANSWER)
            quality = 100 if normalized == expected else 30
            speed = max(0, 100 - int(elapsed_ms / 1500))
            tools = 70
            models = 60
            tokens = 85
            final_score = round(
                quality * 0.55 + speed * 0.15 + tools * 0.1 + models * 0.1 + tokens * 0.1,
                2,
            )

            score = {
                "quality_score": quality,
                "speed_score": speed,
                "tools_score": tools,
                "models_score": models,
                "tokens_score": tokens,
                "total_tokens_used": int((client_metrics or {}).get("total_tokens", 0) or 0),
                "final_score": final_score,
                "elapsed_ms": elapsed_ms,
            }
            session.answer = answer
            session.score = score
            session.status = "submitted"
            if client_metrics:
                session.client_metrics = dict(client_metrics)

            return SubmitResult(
                accepted=True,
                agent_id=agent_id,
                answer=answer,
                score=score,
                status="submitted",
            )

    def leaderboard(self) -> list[dict[str, Any]]:
        with self._lock:
            entries = []
            for session in self.sessions.values():
                if not session.score:
                    continue
                entries.append(
                    {
                        "agent_id": session.agent_id,
                        "agent_name": session.agent_name,
                        "status": session.status,
                        "score": session.score,
                    }
                )
            entries.sort(key=lambda item: item["score"].get("final_score", 0), reverse=True)
            return entries

    def session_payload(self, agent_id: str) -> dict[str, Any]:
        with self._lock:
            session = self.sessions.get(agent_id)
            if not session:
                raise KeyError(agent_id)
            return {
                "session_id": session.session_id,
                "agent_id": session.agent_id,
                "agent_name": session.agent_name,
                "status": session.status,
                "started_at": session.started_at,
                "draft": session.draft,
                "answer": session.answer,
                "score": session.score,
                "thought_count": len(session.thoughts),
                "client_metrics": session.client_metrics,
            }

    def eligible_agent_ids(self) -> list[str]:
        with self._lock:
            return sorted(self.sessions.keys())

    def remaining_time(self, agent_id: str) -> tuple[float, float]:
        with self._lock:
            session = self.sessions.get(agent_id)
            if not session:
                return float(MAX_TIME_S), 0.0
            elapsed_s = max(0.0, time.time() - session.started_at)
            remaining_s = max(0.0, float(MAX_TIME_S) - elapsed_s)
            return remaining_s, elapsed_s

    def record_usage(self, agent_id: str, scope: str, prompt_tokens: int, completion_tokens: int) -> None:
        with self._lock:
            per_agent = self.usage_by_agent.setdefault(agent_id, UsageData())
            per_agent.add(prompt_tokens, completion_tokens)
            per_scope = self.usage_by_scope_agent.setdefault((scope, agent_id), UsageData())
            per_scope.add(prompt_tokens, completion_tokens)

    def usage_for_agent(self, agent_id: str) -> UsageData:
        with self._lock:
            return self.usage_by_agent.get(agent_id, UsageData())

    def usage_for_scope_agent(self, scope: str, agent_id: str) -> UsageData:
        with self._lock:
            return self.usage_by_scope_agent.get((scope, agent_id), UsageData())


@dataclass
class SubmitResult:
    accepted: bool
    agent_id: str
    answer: str
    score: dict[str, Any]
    status: str


STATE = MockArenaState()


def build_api_app() -> FastAPI:
    app = FastAPI(title="Mock Arena API")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/keys/validate")
    async def validate_key(key: str = Query(default="")) -> dict[str, bool]:
        return {"valid": bool(str(key or "").strip())}

    @app.post("/api/session/register")
    async def register(payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or "").strip()
        if not agent_id:
            raise HTTPException(status_code=400, detail="agent_id is required")
        agent_name = str(payload.get("agent_name") or agent_id).strip()
        session = STATE.upsert_session(agent_id, agent_name)
        return {
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "agent_name": session.agent_name,
            "status": session.status,
            "started_at": session.started_at,
        }

    @app.post("/api/status")
    async def status(payload: dict[str, Any]) -> dict[str, bool]:
        agent_id = str(payload.get("agent_id") or "").strip()
        session_status = str(payload.get("status") or "").strip()
        if not agent_id or not session_status:
            raise HTTPException(status_code=400, detail="agent_id and status are required")
        updated = STATE.set_status(agent_id, session_status, payload.get("client_metrics"))
        return {"updated": updated}

    @app.post("/api/thought")
    async def thought(payload: dict[str, Any]) -> dict[str, bool]:
        agent_id = str(payload.get("agent_id") or "").strip()
        accepted = STATE.add_thought(agent_id, str(payload.get("thought") or ""))
        return {"accepted": accepted}

    @app.post("/api/draft")
    async def draft(payload: dict[str, Any]) -> dict[str, bool]:
        agent_id = str(payload.get("agent_id") or "").strip()
        saved = STATE.set_draft(agent_id, str(payload.get("draft") or ""))
        return {"saved": saved}

    @app.post("/api/submit")
    async def submit(payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(payload.get("agent_id") or "").strip()
        answer = str(payload.get("answer") or "").strip()
        if not agent_id:
            raise HTTPException(status_code=400, detail="agent_id is required")
        if not answer:
            raise HTTPException(status_code=400, detail="answer is required")
        try:
            result = STATE.submit(agent_id, answer, payload.get("client_metrics"))
        except KeyError:
            raise HTTPException(status_code=404, detail="session not found") from None
        return {
            "accepted": result.accepted,
            "agent_id": result.agent_id,
            "answer": result.answer,
            "score": result.score,
            "status": result.status,
        }

    @app.get("/api/session/{agent_id}")
    async def session(agent_id: str) -> dict[str, Any]:
        try:
            return STATE.session_payload(agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="session not found") from None

    @app.get("/api/leaderboard")
    async def leaderboard() -> list[dict[str, Any]]:
        return STATE.leaderboard()

    @app.get("/api/competition")
    async def competition() -> dict[str, Any]:
        return {
            "phase": "running",
            "countdown_value": "GO",
            "challenge_type": "text",
            "usage_scope": USAGE_SCOPE,
            "eligible_agent_ids": STATE.eligible_agent_ids(),
        }

    return app


def _proxy_reply_text(messages: list[dict[str, Any]]) -> str:
    combined = " ".join(str(msg.get("content") or "") for msg in messages if isinstance(msg, dict)).lower()
    if "model-selection advisor" in combined or "pick the single best model" in combined:
        return "mock-reasoner-large"
    return f"ANSWER: {EXPECTED_ANSWER}"


def _estimate_prompt_tokens(messages: list[dict[str, Any]]) -> int:
    text = " ".join(str(msg.get("content") or "") for msg in messages if isinstance(msg, dict))
    return max(1, int(len(text) / 4))


def build_proxy_app() -> FastAPI:
    app = FastAPI(title="Mock Arena Proxy")

    @app.get("/models")
    async def models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [{"id": model_id, "object": "model"} for model_id in DEFAULT_MODELS],
        }

    @app.get("/usage/{agent_id}")
    async def usage_agent(agent_id: str) -> dict[str, Any]:
        return {"usage": STATE.usage_for_agent(agent_id).to_dict()}

    @app.get("/usage/{scope}/{agent_id}")
    async def usage_scope(scope: str, agent_id: str) -> dict[str, Any]:
        return {"usage": STATE.usage_for_scope_agent(scope, agent_id).to_dict()}

    @app.post("/chat/completions")
    async def chat_completions(request: Request) -> Any:
        payload = await request.json()
        messages = payload.get("messages") if isinstance(payload, dict) else []
        if not isinstance(messages, list):
            messages = []
        model = str(payload.get("model") or DEFAULT_MODELS[0])
        stream = bool(payload.get("stream", False))
        created = int(time.time())
        completion_text = _proxy_reply_text(messages)
        prompt_tokens = _estimate_prompt_tokens(messages)
        completion_tokens = max(1, int(len(completion_text) / 4))
        total_tokens = prompt_tokens + completion_tokens

        agent_id = str(request.headers.get("x-agent-id") or "unknown")
        scope = str(request.headers.get("x-round-id") or USAGE_SCOPE)
        STATE.record_usage(agent_id, scope, prompt_tokens, completion_tokens)

        completion_id = f"chatcmpl-mock-{uuid.uuid4().hex[:10]}"

        if stream:
            async def generate() -> Any:
                first_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(first_chunk)}\n\n"

                content_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": completion_text}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(content_chunk)}\n\n"

                final_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": completion_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }

    return app


def build_mcp_server(host: str, port: int) -> FastMCP:
    mcp = FastMCP(
        name="Mock Arena MCP",
        host=host,
        port=port,
        sse_path="/sse",
        message_path="/messages/",
    )

    @mcp.tool(name="arena.get_challenge", structured_output=True)
    def arena_get_challenge(agent_id: str = "default") -> dict[str, Any]:
        remaining_s, _ = STATE.remaining_time(agent_id)
        return {
            "challenge_type": "logic-ordering",
            "challenge_id": CHALLENGE_ID,
            "puzzle_id": PUZZLE_ID,
            "description": "Determine the correct finish order of five runners.",
            "rules": "Return exactly one line in this format: ANSWER: Alice, Bob, Charlie, David, Eve",
            "max_time_s": MAX_TIME_S,
            "clues": list(CLUES.values()),
            "time_remaining_s": round(remaining_s, 2),
        }

    @mcp.tool(name="arena.clues.list", structured_output=True)
    def arena_clues_list(agent_id: str = "default") -> dict[str, Any]:
        remaining_s, _ = STATE.remaining_time(agent_id)
        return {
            "clue_ids": list(CLUES.keys()),
            "time_remaining_s": round(remaining_s, 2),
        }

    @mcp.tool(name="arena.clues.get", structured_output=True)
    def arena_clues_get(clue_id: str, agent_id: str = "default") -> dict[str, Any]:
        remaining_s, _ = STATE.remaining_time(agent_id)
        clue_text = CLUES.get(clue_id)
        if clue_text is None:
            return {"error": f"Unknown clue_id '{clue_id}'"}
        return {
            "clue_id": clue_id,
            "text": clue_text,
            "time_remaining_s": round(remaining_s, 2),
        }

    @mcp.tool(name="arena.time_remaining", structured_output=True)
    def arena_time_remaining(agent_id: str = "default") -> dict[str, Any]:
        remaining_s, elapsed_s = STATE.remaining_time(agent_id)
        return {
            "time_remaining_s": round(remaining_s, 2),
            "elapsed_s": round(elapsed_s, 2),
            "max_time_s": MAX_TIME_S,
            "expired": remaining_s <= 0,
        }

    return mcp


async def _serve_uvicorn(app: FastAPI, host: str, port: int, stop_event: asyncio.Event) -> None:
    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    async def _watch_stop() -> None:
        await stop_event.wait()
        server.should_exit = True

    watcher = asyncio.create_task(_watch_stop())
    try:
        await server.serve()
    finally:
        watcher.cancel()


async def run_all(host: str, api_port: int, mcp_port: int, proxy_port: int) -> None:
    api_app = build_api_app()
    proxy_app = build_proxy_app()
    mcp_server = build_mcp_server(host, mcp_port)

    print("Mock Arena started with:")
    print(f"  REST API  : http://{host}:{api_port}")
    print(f"  MCP SSE   : http://{host}:{mcp_port}/sse")
    print(f"  LLM Proxy : http://{host}:{proxy_port}")
    print("Press Ctrl+C to stop.")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    tasks = [
        asyncio.create_task(_serve_uvicorn(api_app, host, api_port, stop_event)),
        asyncio.create_task(_serve_uvicorn(proxy_app, host, proxy_port, stop_event)),
        asyncio.create_task(mcp_server.run_sse_async()),
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    stop_event.set()
    for task in pending:
        task.cancel()
    for task in done:
        exc = task.exception()
        if exc:
            raise exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local mock Arena services.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for all services.")
    parser.add_argument("--api-port", type=int, default=8000, help="REST API port.")
    parser.add_argument("--mcp-port", type=int, default=5001, help="MCP SSE port.")
    parser.add_argument("--proxy-port", type=int, default=4001, help="LLM proxy port.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_all(args.host, args.api_port, args.mcp_port, args.proxy_port))


if __name__ == "__main__":
    main()
