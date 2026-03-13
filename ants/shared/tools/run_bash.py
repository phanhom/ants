"""Run a shell command in the ant workspace. Use for scripts, tests, docker, etc."""

import os
import subprocess
from pathlib import Path

WORKSPACE = Path(os.getenv("ANT_WORKSPACE", "/workspace"))

TOOL_NAME = "run_bash"
TOOL_DESCRIPTION = (
    "Execute a shell command with cwd in the workspace. Use for running scripts, "
    "tests, or docker commands. Returns stdout and stderr. Timeout 60s."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Shell command to run (e.g. 'python -m pytest' or 'ls -la')"},
        "cwd": {
            "type": "string",
            "description": "Optional subdir under workspace as cwd; default is workspace root",
        },
    },
    "required": ["command"],
}

DEFAULT_TIMEOUT = 60


def run(command: str, cwd: str | None = None) -> str:
    base = WORKSPACE
    if cwd:
        base = (WORKSPACE / cwd).resolve()
        if not str(base).startswith(str(WORKSPACE.resolve())):
            return "Error: cwd must be inside workspace"
    if not base.exists():
        base = WORKSPACE
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
            env={**os.environ},
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        lines = []
        if out:
            lines.append("stdout:\n" + out)
        if err:
            lines.append("stderr:\n" + err)
        lines.append(f"exit_code: {r.returncode}")
        return "\n".join(lines) if lines else f"exit_code: {r.returncode}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out (60s)"
    except Exception as e:
        return f"Error running command: {e}"
