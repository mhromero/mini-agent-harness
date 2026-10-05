# Mini Harness

A minimal Python agent harness built as a two-day learning project for technical interview preparation. It uses hosted Ollama models to inspect a configured directory through two read-only tools, without an agent framework.

The focus is understanding the controller: tool schemas, argument validation, execution, conversation history, stopping conditions, and observability. File editing is not implemented.

## Requirements

- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/).
- An [Ollama API key](https://docs.ollama.com/api/authentication) and a hosted model that supports tool calling.
- A practice directory containing files you are comfortable sending to hosted Ollama.

A local Ollama server is not required. This project uses Ollama's native chat API, not OpenAI's Responses API.

## Setup

From the repository directory, install the locked dependencies:

```sh
uv sync
```

Create a local `.env` file:

```dotenv
OLLAMA_API_KEY=your-api-key
MODEL=gpt-oss:120b
ROOT_DIR=/absolute/path/to/practice-directory
```

Choose a hosted model available to your account. `python-dotenv` loads this file when the program starts; existing environment variables take precedence. Startup checks require all three settings and an existing root directory.

`.env`, `api-key.txt`, the virtual environment, and execution logs are excluded from Git. Never commit a real API key. File contents returned by tools are included in requests to the hosted model.

## Usage

```sh
uv run main.py
```

Example requests:

- "List the files without recursion."
- "Read notes.txt and summarize it."
- "List the files, then choose a small text file and explain its contents."

Enter `/reset` to clear conversation history without changing the permitted root or tool policy. Enter `exit` to leave the CLI. Commands are case-insensitive.

## Execution flow

```text
User input -> model call -> assistant message
                              |
                 +------------+------------+
                 |                         |
            tool requests             final answer
                 |                         |
       validate names and arguments     finish turn
                 |
       execute permitted read-only tools
                 |
       append JSON tool results -> next model call
```

The model proposes operations. The controller selects known functions, validates arguments, supplies the trusted root, and enforces the call budget. Filesystem tools enforce their own operation boundaries.

Each user turn allows at most five model calls. Multiple requests in one response are processed sequentially. An invalid request does not prevent other independent read-only requests from running. A tool request returned by call five is not executed or appended to history; the controller reports budget exhaustion.

## Tools and boundaries

| Tool | Model arguments | Behavior |
|---|---|---|
| `list_files` | Required boolean `r` | Lists immediate entries or recurses, returning relative paths and types. Stops at 100 returned entries and reports truncation when more exist. Does not follow symlinks. |
| `read_file` | Required string `file_path` | Reads a relative path inside the configured root as UTF-8 text. Rejects absolute paths, outside-root destinations, non-files, invalid UTF-8, null bytes, and files exceeding 65,536 bytes. |

Reads resolve paths before checking containment. Symlinks are allowed for reading only when their resolved destination is inside the root. A bounded read checks the size limit again in case the file grew after inspection. No tool writes files or executes shell commands.

Successful listings return `ok`, `entries`, `truncated`, and `error`. Reads return `ok`, `content`, `truncated`, and `error`. An empty directory or empty file is a success; an unsuccessful operation returns an error instead of fabricated contents.

Missing files, invalid arguments, and denied paths become tool results so the model can recover within the remaining budget. Unknown tools are rejected. HTTP 401/403 responses exit the CLI; other handled API errors and connection failures stop the turn but keep the CLI available. There are no automatic retries.

## Context and logs

Conversation history lives in memory for the CLI session. It preserves user messages, complete assistant messages including tool requests, and corresponding tool results. Counters and failure flags are turn state, separate from history. No persistent conversation memory or automatic summarization is implemented.

Execution events are appended to `harness.jsonl` beside `main.py`. Each line is a JSON object containing a UTC timestamp, turn ID, model step, and event-specific metadata. Tool requests are identified by turn ID, step, and request index.

Events cover turn start/finish, model-call start/finish, tool requests, rejection, and execution start/finish. Outcomes distinguish completion, API failure, and budget exhaustion. Result metadata includes content character counts, entry counts, truncation, and durations.

Logs omit credentials, prompts, requested paths, file contents, and raw error messages. Terminal diagnostics still display requested arguments and API/tool errors. Logs therefore reconstruct control flow, not the exact evidence returned by tools.

## Project layout

- `main.py`: configuration, CLI, history, argument validation, dispatch, bounded loop, and logging.
- `file_tools.py`: filesystem tools, limits, and model-facing schemas.
- `pyproject.toml` and `uv.lock`: dependencies and resolved versions.
- `AGENTS.md`: learning-mode collaboration instructions.

## Verification and remaining work

During development, temporary isolated checks exercised tool behavior, path traversal, inside/outside symlinks, invalid arguments, scripted API failures, and iteration limits. Live CLI runs exercised sequential tool calling and produced an execution trace. These checks are not yet a committed, repeatable test suite; the logging and authentication changes still need deterministic regression coverage.

Milestones 1-7 have been covered at the learning-project scope. Milestone 8 remains in progress: formal tests for successful execution, multi-step calls, recoverable errors, unauthorized operations, and iteration limits, followed by live-model evaluations.

## Limitations

- Full history grows without token-aware pruning, and disappears on restart. Previous file observations can become stale.
- Resolved-path checks are not an operating-system sandbox and do not prevent races caused by concurrent filesystem changes.
- UTF-8 decoding and null-byte rejection are limited text checks, not comprehensive binary-format detection.
- File contents are untrusted observations; this project does not comprehensively defend against prompt injection in them.
- The five-call budget does not independently limit tool count, elapsed time, or token usage.
- Timeouts and every possible transport failure are not explicitly handled. Unexpected tool exceptions are logged and re-raised.
- Logs have no rotation; logging failures can interrupt execution. Path omission limits diagnosis of repeated reads, and tool errors do not have detailed machine-readable categories.
- The CLI runs at module import time; extracting testable controller boundaries is potential later work.

## References

- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Ollama Python client and examples](https://github.com/ollama/ollama-python)
- [uv project guide](https://docs.astral.sh/uv/guides/projects/)
