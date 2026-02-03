"""Use Codex SDK to analyze a real project with the app-server."""

import argparse
import os
import sys
import textwrap
from pathlib import Path

import anyio

from codex_agent_sdk import CodexClient, CodexClientOptions

MODEL = os.getenv("CODEX_MODEL", "gpt-5.1-codex")
CODEX_CLI = os.getenv("CODEX_CLI", "codex")
EFFORT = os.getenv("CODEX_EFFORT", "high")


async def approve_commands(_params: dict) -> str:
    # Accept command execution requests. Adjust for your policy.
    return "accept"


async def approve_file_changes(_params: dict) -> str:
    # Accept file change approvals if they occur (rare for analysis tasks).
    return "accept"


async def tool_user_input(params: dict) -> dict:
    # Provide empty answers for request_user_input prompts.
    answers = {}
    for question in params.get("questions", []):
        qid = question.get("id")
        if qid:
            answers[qid] = {"answers": [""]}
    return {"answers": answers}


async def dynamic_tool_call(_params: dict) -> dict:
    # If the agent tries to call a client-side dynamic tool, fail clearly.
    return {"output": "dynamic tools are not implemented in this script", "success": False}

def _resolve_project_path(arg_path: str | None) -> Path:
    env_path = os.getenv("CODEX_PROJECT") or os.getenv("CCODEX_PROJECT")
    path_str = arg_path or env_path or os.getcwd()
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Project path does not exist: {path}")
    return path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a local project with Codex app-server."
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Project path to analyze (defaults to CODEX_PROJECT or current directory).",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    project_path = _resolve_project_path(args.project)

    options = CodexClientOptions(
        codex_path=CODEX_CLI,
        client_name="codex_sdk_py_example",
        client_version="0.1.0",
    )

    prompt = textwrap.dedent(
        f"""
        You are analyzing a real codebase at: {project_path}

        Task:
        1) Summarize the purpose of this project.
        2) Explain the high-level architecture (major modules/components and how they interact).
        3) Call out key entry points (CLI, APIs, main modules).
        4) Provide a short "how it works" flow.

        Use concrete file references when possible.
        Avoid modifying files. Focus on reading and analysis.
        """
    ).strip()

    async with CodexClient(
        options=options,
        command_approval_handler=approve_commands,
        file_change_approval_handler=approve_file_changes,
        tool_input_handler=tool_user_input,
        dynamic_tool_handler=dynamic_tool_call,
    ) as client:
        thread = await client.thread_start({"model": MODEL, "cwd": str(project_path)})
        thread_id = thread["thread"]["id"]

        async for delta in client.stream_prompt_text(
            thread_id,
            prompt,
            cwd=str(project_path),
            approvalPolicy="on-request",
            effort=EFFORT,
        ):
            print(delta, end="", flush=True)


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
