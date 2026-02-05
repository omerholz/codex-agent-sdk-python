"""Example showing typed event handling."""

import anyio

from codex_agent_sdk import (
    Agent,
    Event,
    ItemCompleted,
    ItemStarted,
    McpStartupComplete,
    MessageCompleted,
    MessageDelta,
    TaskCompleted,
    TaskStarted,
    ThreadStarted,
    TurnCompleted,
    TurnStarted,
)


async def main() -> None:
    agent = Agent(model="gpt-5.2-codex", auto_approve=True)

    print("Streaming events with type checking...\n")

    async for event in agent.run("Say hello in exactly 5 words.").events():
        # Pattern match on event types for clean handling
        match event:
            case ThreadStarted(thread=thread) if thread:
                print(f"🧵 Thread started: {thread.id}")

            case TurnStarted(turn_id=turn_id):
                print(f"🔄 Turn started: {turn_id}")

            case MessageDelta(delta=delta):
                # Stream text as it arrives
                print(delta, end="", flush=True)

            case MessageCompleted(item_id=item_id):
                print(f"\n📨 Message completed: {item_id}")

            case TaskStarted(task_id=task_id):
                print(f"📋 Task started: {task_id}")

            case TaskCompleted(task_id=task_id):
                print(f"✅ Task completed: {task_id}")

            case ItemStarted(item_id=item_id, item_type=item_type):
                print(f"▶️  Item started: {item_id} ({item_type})")

            case ItemCompleted(item_id=item_id):
                print(f"⏹️  Item completed: {item_id}")

            case TurnCompleted(turn_id=turn_id, status=status):
                print(f"🏁 Turn completed: {turn_id} (status: {status})")

            case McpStartupComplete():
                print("🔌 MCP startup complete")

            case Event(method=method):
                # Fallback for unknown events
                print(f"📡 Event: {method}")

    print("\nDone!")


if __name__ == "__main__":
    anyio.run(main)
