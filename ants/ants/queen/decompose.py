"""LLM-based task decomposition: split a user instruction into per-worker tasks."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ants.runtime.models import AgentConfig
from ants.runtime.runtime_config import get_ants_config, load_runtime_config


def decompose_instruction(instruction: str, workers: list[AgentConfig]) -> list[dict] | None:
    """Call LLM to split instruction into per-worker tasks. Returns list of {to, summary} or None."""
    rconf = load_runtime_config()
    llm = rconf.get("llm") or {}
    base_url = (llm.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = llm.get("model_name") or "gpt-4"
    api_key = llm.get("api_key") or ""
    if not api_key:
        return None
    max_tokens = int(llm.get("max_tokens") or 4096)
    workers_json = json.dumps(
        [{"agent_id": w.agent_id, "role": w.role, "skills": w.skills[:15]} for w in workers],
        ensure_ascii=False,
    )
    user_content = (
        f"Decompose the user instruction into one or more tasks, each for a specific worker. "
        f"Output a JSON array only. Each item: {{ \"to\": \"<agent_id>\", \"summary\": \"<short task for that worker>\" }}. "
        f"Use only agent_id from the workers list. One task per worker at most.\n\n"
        f"User instruction: {instruction}\n\nWorkers: {workers_json}"
    )
    ac = get_ants_config()
    timeout = 60.0
    try:
        t = ac.get("decompose_llm_timeout") or "60"
        timeout = float(t)
    except (ValueError, TypeError):
        pass
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You output only a valid JSON array. No markdown, no explanation."},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": max_tokens,
                },
            )
            if r.status_code != 200:
                return None
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    except Exception:
        return None
    content = content.strip()
    for prefix in ("```json", "```"):
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
    try:
        tasks = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(tasks, list) or not tasks:
        return None
    valid_ids = {w.agent_id for w in workers}
    out = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        to_id = t.get("to")
        summary = t.get("summary") or ""
        if to_id in valid_ids and summary:
            out.append({"to": to_id, "summary": summary})
    return out if out else None
