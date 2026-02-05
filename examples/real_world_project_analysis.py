"""Use Codex SDK to analyze a real project with the app-server."""

import argparse
import os
import sys
import textwrap
from pathlib import Path

import anyio

from codex_agent_sdk import Agent, CommandApproval, FileChangeApproval, ToolInput

MODEL = os.getenv("CODEX_MODEL", "gpt-5.2-codex")
EFFORT = os.getenv("CODEX_EFFORT", "medium")


def _resolve_project_path(arg_path: str | None) -> Path:
    env_path = os.getenv("CODEX_PROJECT") or os.getenv("CCODEX_PROJECT")
    raw = arg_path or env_path
    path = (Path(raw) if raw else Path.cwd()).expanduser().resolve()
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

    # Create agent with builder pattern
    agent = (
        Agent()
        .model(MODEL)
        .cwd(project_path)
        .effort(EFFORT)
    )

    # Register handlers with decorators
    @agent.on_command_approval
    async def approve_commands(cmd: CommandApproval) -> str:
        """Accept command execution requests."""
        return "accept"

    @agent.on_file_change
    async def approve_file_changes(change: FileChangeApproval) -> str:
        """Accept file change approvals if they occur."""
        return "accept"

    @agent.on_tool_input
    async def tool_user_input(tool_input: ToolInput) -> dict:
        """Provide empty answers for request_user_input prompts."""
        answers = {}
        for question in tool_input.questions:
            qid = question.get("id")
            if qid:
                answers[qid] = {"answers": [""]}
        return {"answers": answers}

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

    # Stream the response
    async for chunk in agent.run(prompt, approvalPolicy="on-request"):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
