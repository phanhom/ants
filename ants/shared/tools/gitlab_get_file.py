"""Get file content from a GitLab repository."""

import json
import os
import urllib.parse

TOOL_NAME = "gitlab_get_file"
TOOL_DESCRIPTION = "Get raw file content from a GitLab project. project_id can be numeric or path (URL-encoded)."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string", "description": "Project ID or path (e.g. 123 or group%2Frepo)"},
        "file_path": {"type": "string", "description": "Path to file in repo (e.g. src/main.py)"},
        "ref": {"type": "string", "description": "Branch, tag, or commit (default main)", "default": "main"},
    },
    "required": ["project_id", "file_path"],
}


def run(project_id: str, file_path: str, ref: str = "main") -> str:
    url = (os.getenv("GITLAB_URL") or "").rstrip("/")
    if not url:
        return "Error: GITLAB_URL not set"
    base = f"{url}/api/v4" if "/api/v4" not in url else url
    token = os.getenv("GITLAB_TOKEN", "")
    headers = {"PRIVATE-TOKEN": token} if token else {}
    encoded_path = urllib.parse.quote(file_path, safe="")
    path = f"/projects/{project_id}/repository/files/{encoded_path}/raw"
    params = {"ref": ref}
    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{base}{path}", headers=headers, params=params)
            if r.status_code != 200:
                try:
                    err = r.json()
                    return f"Error {r.status_code}: {json.dumps(err, ensure_ascii=False)[:400]}"
                except Exception:
                    return f"Error {r.status_code}: {r.text[:400]}"
            return r.text
    except Exception as e:
        return f"Error: {e}"
