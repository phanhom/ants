"""Create a branch in a GitLab project."""

import json
import os

TOOL_NAME = "gitlab_create_branch"
TOOL_DESCRIPTION = "Create a new branch in a GitLab project. Uses GITLAB_URL and GITLAB_TOKEN."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string", "description": "Project ID or path (URL-encoded)"},
        "branch": {"type": "string", "description": "New branch name"},
        "ref": {"type": "string", "description": "Source branch/tag/commit (default main)", "default": "main"},
    },
    "required": ["project_id", "branch"],
}


def run(project_id: str, branch: str, ref: str = "main") -> str:
    url = (os.getenv("GITLAB_URL") or "").rstrip("/")
    if not url:
        return "Error: GITLAB_URL not set"
    base = f"{url}/api/v4" if "/api/v4" not in url else url
    token = os.getenv("GITLAB_TOKEN", "")
    headers = {"PRIVATE-TOKEN": token} if token else {}
    path = f"/projects/{project_id}/repository/branches"
    body = {"branch": branch, "ref": ref}
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
