# Skills and tools

Skills are abstract capabilities per role; tools are concrete callables (e.g. from `/shared/tools`). The runner injects skill descriptions into the system prompt and only allows tools listed in `tools_allowed`.

## Built-in skill descriptions (runner)

| Skill id | Description |
|----------|-------------|
| api_design | Design and document REST/API contracts and schemas |
| python_fastapi | Implement backends in Python with FastAPI |
| db_migrations | Design and apply database migrations |
| integration_contracts | Define and verify service integration contracts |
| ui_critique | Review UI/UX for accessibility and consistency |
| frontend_react | Build UIs with React and modern frontend tooling |
| test_planning | Design test plans and regression coverage |
| exploration | Research and summarize options and context |
| commercialization | Package and communicate value for stakeholders |
| code_editing | Edit and refactor code in the codebase (read_file, write_file, edit_file) |
| bash_ops | Run shell commands and scripts in a controlled workspace (run_bash) |
| web_access | Fetch web pages and retrieve information from URLs (fetch_url) |
| codebase_search | Search the repository for code and config (search_codebase) |
| research | Web search and retrieve docs for research (web_search, fetch_url) |
| delegation | Assign work and coordinate via AIP (send_aip, spawn_subordinate) |
| container_ops | Run Docker or container commands via shell (run_bash) |
| problem_framing | Frame problems and define scope and success criteria |
| architecture_design | Design system and component architecture |
| decision_making | Make and document decisions with trade-offs |
| review_synthesis | Synthesize reports and reviews from subordinates |

## Shared tools (repo)

| Tool | Description |
|------|-------------|
| read_file | Read file under workspace (path relative to `/workspace`) |
| write_file | Write content to a file under workspace |
| edit_file | Replace old_string with new_string in a file (for code/config edits) |
| append_todo | Append a todo item to this ant's `todos/items.jsonl` |
| run_bash | Execute a shell command in the workspace (scripts, tests, docker); timeout 60s |
| fetch_url | Fetch a URL and return body as text (primary web access); timeout 15s, ~2MB |
| search_codebase | Search for a string in workspace files; optional path_glob (e.g. `*.py`) |
| web_search | Run a web search and return snippets/links (research); optional duckduckgo-search |
| send_aip | Send an AIP message to another ant via the queen (delegation); needs ANT_QUEEN_URL |
| spawn_subordinate | Create or ensure subordinate worker containers (root/creator only) |

Tool modules in `/shared/tools` must define: `TOOL_NAME`, `TOOL_DESCRIPTION`, `TOOL_PARAMS` (JSON schema), and `run(**kwargs) -> str`. Hot-load is done by the bootstrap loop; the runner discovers them and passes only `tools_allowed` to the LLM.

## Skill–tool mapping (suggested)

| Skill | Typical tools |
|-------|----------------|
| code_editing | read_file, write_file, edit_file |
| bash_ops | run_bash |
| web_access | fetch_url |
| codebase_search | search_codebase |
| research | web_search, fetch_url |
| delegation | send_aip, spawn_subordinate |
| container_ops | run_bash (e.g. docker commands) |

Creator (root) is typically given **research**, **delegation**, **web_access**, and **codebase_search** so it can do web research, search the repo, and assign work or spawn subordinates.

## Extending with open-source tools

You can add tools that follow the same convention (TOOL_NAME, TOOL_DESCRIPTION, TOOL_PARAMS, run) and drop them into `/shared/tools`. Many open-source agent toolkits (e.g. MCP servers, LangChain tools) can be wrapped to this interface. Prefer community-maintained, well-documented projects (e.g. FastMCP, mcp-use) when integrating external capabilities.

Optional dependency for web_search: `pip install ants[search]` (duckduckgo-search).
