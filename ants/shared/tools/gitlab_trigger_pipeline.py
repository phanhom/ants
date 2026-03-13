"""Trigger a GitLab CI/CD pipeline."""

import json
import os

TOOL_NAME = "gitlab_trigger_pipeline"
TOOL_DESCRIPTION = "Trigger a pipeline for a ref (branch/tag). Uses GITLAB_URL and GITLAB_TOKEN."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string", "description": "Project ID or path (URL-encoded)"},
        "ref": {"type": "string", "description": "Branch or tag to run pipeline (e.g. main)"},
    },
    "required": ["project_id", "ref"],
}


def run(project_id: str, ref: str) -> str:
    url = (os.getenv("GITLAB_URL") or "").rstrip("/")
    if not url:
        return "Error: GITLAB_URL not set"
    base = f"{url}/api/v4" if "/api/v4" not in url else url
    token = os.getenv("GITLAB_TOKEN", "")
    headers = {"PRIVATE-TOKEN": token} if token else {}
    path = f"/projects/{project_id}/pipeline"
    body = {"ref": ref}
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
