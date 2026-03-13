"""Get GitLab pipeline status."""

import json
import os

TOOL_NAME = "gitlab_pipeline_status"
TOOL_DESCRIPTION = "Get status of a GitLab CI/CD pipeline. Uses GITLAB_URL and GITLAB_TOKEN."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string", "description": "Project ID or path (URL-encoded)"},
        "pipeline_id": {"type": "integer", "description": "Pipeline ID"},
    },
    "required": ["project_id", "pipeline_id"],
}


def run(project_id: str, pipeline_id: int) -> str:
    url = (os.getenv("GITLAB_URL") or "").rstrip("/")
    if not url:
        return "Error: GITLAB_URL not set"
    base = f"{url}/api/v4" if "/api/v4" not in url else url
    token = os.getenv("GITLAB_TOKEN", "")
    headers = {"PRIVATE-TOKEN": token} if token else {}
    path = f"/projects/{project_id}/pipelines/{pipeline_id}"
    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{base}{path}", headers=headers)
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code != 200:
                return f"Error {r.status_code}: {json.dumps(data, ensure_ascii=False)[:500]}"
            return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"
