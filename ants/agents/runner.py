"""Worker task runner: load context from files, call LLM with tools, persist conversation and status."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from ants.runtime.config import load_agent_config
from ants.runtime.runtime_config import load_runtime_config
from ants.runtime.traces import (
    ensure_trace_dirs,
    get_agent_base_dir,
    list_recent_jsonl,
    utc_now_iso,
    write_trace_dual,
)

try:
    from ants.runtime.db import write_trace
except Exception:
    def write_trace(agent_id: str, trace_type: str, payload: dict[str, Any]) -> bool:
        return False

# Skill id -> short description for system prompt (aligned with configs/agents and tools)
SKILL_DESCRIPTIONS: dict[str, str] = {
    "api_design": "Design and document REST/API contracts and schemas",
    "python_fastapi": "Implement backends in Python with FastAPI",
    "db_migrations": "Design and apply database migrations",
    "integration_contracts": "Define and verify service integration contracts",
    "ui_critique": "Review UI/UX for accessibility and consistency",
    "frontend_react": "Build UIs with React and modern frontend tooling",
    "test_planning": "Design test plans and regression coverage",
    "exploration": "Research and summarize options and context",
    "commercialization": "Package and communicate value for stakeholders",
    "git_reader": "Read repo structure and file contents",
    "openapi_checker": "Validate OpenAPI specs and drift",
    "schema_diff": "Compare and diff schema versions",
    "code_editing": "Edit and refactor code in the codebase (read_file, write_file, edit_file)",
    "bash_ops": "Run shell commands and scripts in a controlled workspace (run_bash)",
    "web_access": "Fetch web pages and retrieve information from URLs (fetch_url)",
    "codebase_search": "Search the repository for code and config (search_codebase)",
    "research": "Web search and retrieve docs for research (web_search, fetch_url)",
    "delegation": "Assign work and coordinate via AIP (send_aip, spawn_subordinate)",
    "container_ops": "Run Docker or container commands via shell (run_bash)",
    "problem_framing": "Frame problems and define scope and success criteria",
    "architecture_design": "Design system and component architecture",
    "decision_making": "Make and document decisions with trade-offs",
    "review_synthesis": "Synthesize reports and reviews from subordinates",
    "design_system": "Maintain design systems and UI consistency",
    "interaction_design": "Design interactions and user flows",
    "accessibility_review": "Review and improve accessibility",
    "frontend_delivery": "Deliver frontend features and components",
    "regression_testing": "Plan and run regression tests",
    "quality_risk_assessment": "Assess quality and release risks",
    "release_checklist": "Manage release checklists and gates",
}


def _get_llm_config() -> dict[str, Any]:
    conf = load_runtime_config()
    llm = conf.get("llm") or {}
    return {
        "base_url": llm.get("base_url", "https://api.openai.com/v1"),
        "model": llm.get("model_name", "gpt-4"),
        "api_key": llm.get("api_key", os.getenv("LLM_API_KEY", "")),
    }


def load_context(agent_id: str, limit: int = 30) -> list[dict[str, Any]]:
    """Load recent conversation and AIP context from file store for LLM messages."""
    base = get_agent_base_dir(agent_id)
    messages: list[dict[str, Any]] = []
    conv = list_recent_jsonl(base / "conversations" / "messages.jsonl", limit=limit)
    for row in conv:
        role = row.get("role", "user")
        content = row.get("content", "")
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        messages.append({"role": role, "content": content})
    aip = list_recent_jsonl(base / "aip" / "messages.jsonl", limit=10)
    if aip:
        summary = "Recent AIP: " + json.dumps([r.get("action") for r in aip[-5:]], ensure_ascii=False)
        messages.append({"role": "system", "content": summary})
    return messages


def build_system_prompt(config) -> str:
    """Build system prompt from agent config (persona, skills, tools, environment policy)."""
    parts = [
        f"You are {config.display_name} ({config.role}).",
        config.prompt_profile.persona,
        "",
        "Rules:",
    ]
    for r in config.prompt_profile.system_rules:
        parts.append(f"- {r}")
    parts.append("")
    parts.append("Skills: " + ", ".join(config.skills))
    for s in config.skills:
        if s in SKILL_DESCRIPTIONS:
            parts.append(f"  - {s}: {SKILL_DESCRIPTIONS[s]}")
    parts.append("")
    parts.append("Allowed tools: " + ", ".join(config.tools_allowed or []))
    ep = config.environment_policy
    parts.append("")
    parts.append(f"Environment: default_target={ep.default_target}; production_requires_human_approval={ep.production_requires_human_approval}.")
    return "\n".join(parts)


MAX_CONTEXT_TOKENS = 28000
CHARS_PER_TOKEN_EST = 4


def _approx_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token count from serialized message list."""
    return len(json.dumps(messages, ensure_ascii=False)) // CHARS_PER_TOKEN_EST


def _compress_context(
    agent_id: str,
    messages: list[dict[str, Any]],
    llm_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    If messages exceed MAX_CONTEXT_TOKENS, summarize the middle segment (keep first system and last user)
    into a single 'Previous context summary' system message and append summary to conversations/summaries.jsonl.
    """
    if _approx_tokens(messages) <= MAX_CONTEXT_TOKENS:
        return messages
    if len(messages) <= 2:
        return messages
    # Keep first (system) and last (current user); summarize the rest
    first, last = messages[0], messages[-1]
    middle = messages[1:-1]
    # Build a single blob for the summarizer
    blob_parts = []
    for m in middle:
        role = m.get("role", "unknown")
        content = m.get("content", "")
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        blob_parts.append(f"[{role}]: {content[:2000]}" + ("..." if len(str(content)) > 2000 else ""))
    blob = "\n\n".join(blob_parts)[:30000]
    prompt = (
        "Summarize the following conversation in third person. "
        "Keep key facts, decisions, and outcomes. One short paragraph."
    )
    try:
        from openai import OpenAI
        client = OpenAI(base_url=llm_cfg["base_url"], api_key=llm_cfg["api_key"])
        r = client.chat.completions.create(
            model=llm_cfg["model"],
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": blob},
            ],
            max_tokens=500,
        )
        summary = (r.choices[0].message.content or "").strip() if r.choices else ""
    except Exception:
        summary = "(Summary unavailable)"
    summary_msg = f"Previous context summary: {summary}"
    base = get_agent_base_dir(agent_id)
    summary_path = base / "conversations" / "summaries.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": utc_now_iso(), "summary": summary}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return [first, {"role": "system", "content": summary_msg}, last]


def get_tools_for_agent(config) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (OpenAI tools list, name -> run callable). Only includes tools in config.tools_allowed."""
    from ants.agents.bootstrap import discover_tools

    discover_tools()
    tools_spec: list[dict[str, Any]] = []
    tools_impl: dict[str, Any] = {}
    allowed = set(config.tools_allowed or [])
    for name, mod in list(sys.modules.items()):
        if not name.startswith("ants_tools_"):
            continue
        tool_name = getattr(mod, "TOOL_NAME", None)
        if not tool_name or (allowed and tool_name not in allowed):
            continue
        desc = getattr(mod, "TOOL_DESCRIPTION", "")
        params = getattr(mod, "TOOL_PARAMS", {"type": "object", "properties": {}})
        run_fn = getattr(mod, "run", None)
        if not callable(run_fn):
            continue
        tools_spec.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": desc,
                "parameters": params,
            },
        })
        tools_impl[tool_name] = run_fn
    return tools_spec, tools_impl


def run_task(agent_id: str, task_payload: dict[str, Any]) -> dict[str, Any]:
    """Run one task: load context, call LLM with tools, persist conversation. Returns summary."""
    config = load_agent_config()
    if config.agent_id != agent_id:
        config = load_agent_config(Path(os.getenv("ANT_CONFIG", "")))
    llm_cfg = _get_llm_config()
    if not llm_cfg.get("api_key"):
        return {"ok": False, "error": "LLM API key not configured"}
    tools_spec, tools_impl = get_tools_for_agent(config)
    system = build_system_prompt(config)
    context = load_context(agent_id)
    instruction = task_payload.get("instruction", task_payload.get("content", ""))
    if isinstance(instruction, dict):
        instruction = json.dumps(instruction, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        *context,
        {"role": "user", "content": instruction},
    ]
    messages = _compress_context(agent_id, messages, llm_cfg)
    try:
        from openai import OpenAI
        client = OpenAI(base_url=llm_cfg["base_url"], api_key=llm_cfg["api_key"])
        max_rounds = 10
        while max_rounds > 0:
            max_rounds -= 1
            kwargs: dict[str, Any] = {"model": llm_cfg["model"], "messages": messages}
            if tools_spec:
                kwargs["tools"] = tools_spec
                kwargs["tool_choice"] = "auto"
            resp = client.chat.completions.create(**kwargs)
            choice = resp.choices[0] if resp.choices else None
            if not choice:
                break
            msg = choice.message
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if getattr(msg, "tool_calls", None):
                assistant_msg["tool_calls"] = [
                    {"id": getattr(tc, "id", ""), "type": "function", "function": {"name": getattr(tc.function, "name", ""), "arguments": getattr(tc.function, "arguments", "{}")}}
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)
            if not getattr(msg, "tool_calls", None):
                break
            for tc in msg.tool_calls:
                name = tc.function.name if hasattr(tc.function, "name") else tc.function.get("name")
                args_str = tc.function.arguments if hasattr(tc.function, "arguments") else tc.function.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}
                fn = tools_impl.get(name)
                result = f"Error: unknown tool {name}" if not fn else str(fn(**args))
                messages.append({
                    "role": "tool",
                    "tool_call_id": getattr(tc, "id", ""),
                    "name": name,
                    "content": result,
                })
        # Persist conversation (file + DB)
        base = ensure_trace_dirs(agent_id)
        conv_path = base / "conversations" / "messages.jsonl"
        conv_path.parent.mkdir(parents=True, exist_ok=True)
        for m in messages:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                row = {"ts": utc_now_iso(), "role": m["role"], "content": m["content"]}
                with conv_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                try:
                    write_trace(agent_id, "conversation", row)
                except Exception:
                    pass
        last_content = messages[-1].get("content", "") if messages else ""
        return {"ok": True, "last_response": last_content[:500]}
    except Exception as e:
        write_trace_dual(agent_id, "log", "runner.jsonl", {"event": "error", "error": str(e)})
        return {"ok": False, "error": str(e)}
