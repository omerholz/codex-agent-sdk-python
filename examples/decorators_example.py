"""Example showing decorator-based handler registration."""

import anyio

from codex_agent_sdk import (
    Agent,
    CommandApproval,
    Event,
    ExecCompleted,
    ExecStarted,
    FileChangeApproval,
    MessageDelta,
)


async def main() -> None:
    agent = Agent(model="gpt-5.2-codex", cwd=".")

    # =========================================================================
    # Register handlers using decorators
    # =========================================================================

    @agent.on_command_approval
    async def handle_command(cmd: CommandApproval) -> str:
        """Handle command execution approval requests."""
        print(f"\n📋 Command approval requested: {cmd.command}")

        # Example: only approve safe commands
        safe_commands = ["ls", "cat", "echo", "pwd", "whoami"]
        first_word = cmd.command.split()[0] if cmd.command else ""

        if first_word in safe_commands:
            print("   ✅ Approved (safe command)")
            return "accept"
        else:
            print("   ⚠️  Approved (exercise caution in production!)")
            return "accept"

    @agent.on_file_change
    async def handle_file_change(change: FileChangeApproval) -> str:
        """Handle file change approval requests."""
        print(f"\n📝 File change requested: {change.path}")
        # For demo purposes, approve all changes
        return "accept"

    @agent.on_event
    async def log_events(event: Event) -> None:
        """Log interesting events as they happen."""
        if isinstance(event, ExecStarted):
            print(f"\n🚀 Executing: {event.command}")
        elif isinstance(event, ExecCompleted):
            status = "✅" if event.exit_code == 0 else "❌"
            print(f"\n{status} Command finished (exit code: {event.exit_code})")

    # =========================================================================
    # Run the agent
    # =========================================================================

    print("Running agent with decorated handlers...\n")
    print("-" * 50)

    async for event in agent.run(
        "List the files in the current directory and tell me what you see.",
        effort="medium",
        approvalPolicy="on-request",
    ).events():
        # Stream text to console
        if isinstance(event, MessageDelta):
            print(event.delta, end="", flush=True)

    print("\n" + "-" * 50)
    print("Done!")


if __name__ == "__main__":
    anyio.run(main)
