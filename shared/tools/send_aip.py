"""Send an AIP message to another ant via the queen. For delegation and communication."""

import json
import os

TOOL_NAME = "send_aip"
TOOL_DESCRIPTION = (
    "Send an AIP message to another ant. Use to assign tasks, request reports, or communicate. "
    "Requires ANT_QUEEN_URL to be set (queen base URL). Action: assign_task, submit_report, etc."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "to_agent_id": {"type": "string", "description": "Target ant agent_id"},
        "action": {"type": "string", "description": "AIP action: assign_task, submit_report, request_context, etc."},
        "payload": {"type": "object", "description": "Message payload (e.g. {\"instruction\": \"...\"})", "default": {}},
        "intent": {"type": "string", "description": "Intent label", "default": "tool_send"},
    },
    "required": ["to_agent_id", "action"],
}


def run(
    to_agent_id: str,
    action: str,
    payload: dict | None = None,
    intent: str = "tool_send",
) -> str:
    base = os.getenv("ANT_QUEEN_URL", "").rstrip("/")
    if not base:
        return "Error: ANT_QUEEN_URL not set (cannot reach queen to send AIP)"
    from_ant = os.getenv("ANT_AGENT_ID", "unknown")
    payload = payload or {}
    body = {
        "from": from_ant,
        "to": to_agent_id,
        "action": action,
        "intent": intent,
        "payload": payload,
    }
    body["aip_id"] = payload.get("message_id") or payload.get("aip_id") or ""
    log_extra = {k: payload[k] for k in ("trace_id",) if payload.get(k) is not None}
    agent_id = os.getenv("ANT_AGENT_ID")
    if agent_id:
        log_extra["agent_id"] = agent_id
    try:
        from ants.protocol.send import send_aip, SendParams
        params = SendParams(timeout=30.0, max_retries=4)
        data = send_aip(base, body, params=params, log_extra=log_extra if log_extra else None)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return f"Error sending AIP: {e}"
