"""Create a merge request in GitLab."""

import json
import os

TOOL_NAME = "gitlab_create_merge_request"
TOOL_DESCRIPTION = "Create a merge request. Uses GITLAB_URL and GITLAB_TOKEN."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string", "description": "Project ID or path (URL-encoded)"},
        "source_branch": {"type": "string", "description": "Source branch"},
        "target_branch": {"type": "string", "description": "Target branch (default main)", "default": "main"},
        "title": {"type": "string", "description": "MR title"},
        "description": {"type": "string", "description": "Optional MR description", "default": ""},
    },
    "required": ["project_id", "source_branch", "title"],
}


def run(project_id: str, source_branch: str, title: str, target_branch: str = "main", description: str = "") -> str:
    url = (os.getenv("GITLAB_URL") or "").rstrip("/")
    if not url:
        return "Error: GITLAB_URL not set"
    base = f"{url}/api/v4" if "/api/v4" not in url else url
    token = os.getenv("GITLAB_TOKEN", "")
    headers = {"PRIVATE-TOKEN": token} if token else {}
    path = f"/projects/{project_id}/merge_requests"
    body = {"source_branch": source_branch, "target_branch": target_branch, "title": title}
    if description:
        body["description"] = description
    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{base}{path}", headers=headers, json=body)
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code not in (200, 201):
                return f"Error {r.status_code}: {json.dumps(data, ensure_ascii=False)[:500]}"
            return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"
