"""List GitLab projects accessible with the configured token."""

import json
import os

TOOL_NAME = "gitlab_list_projects"
TOOL_DESCRIPTION = "List GitLab projects (optionally by group). Uses GITLAB_URL and GITLAB_TOKEN."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "group_id": {"type": "integer", "description": "Optional group ID to list projects under"},
        "per_page": {"type": "integer", "description": "Max results (default 20)", "default": 20},
    },
    "required": [],
}


def run(group_id: int | None = None, per_page: int = 20) -> str:
    url = (os.getenv("GITLAB_URL") or "").rstrip("/")
    if not url:
        return "Error: GITLAB_URL not set"
    base = f"{url}/api/v4" if "/api/v4" not in url else url
    token = os.getenv("GITLAB_TOKEN", "")
    headers = {"PRIVATE-TOKEN": token} if token else {}
    path = f"/groups/{group_id}/projects" if group_id else "/projects"
    params = {"per_page": min(per_page, 100)}
    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{base}{path}", headers=headers, params=params)
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else []
            if r.status_code != 200:
                return f"Error {r.status_code}: {json.dumps(data, ensure_ascii=False)[:500]}"
            return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"
