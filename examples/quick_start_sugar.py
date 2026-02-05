"""Quick start example using the new Pythonic Agent API."""

import anyio

from codex_agent_sdk import Agent, run


async def example_one_liner() -> None:
    """Simplest possible usage - one-liner with module-level run()."""
    print("=== One-liner example ===")
    async for chunk in run("What is 2+2? Answer with just the number."):
        print(chunk, end="", flush=True)
    print("\n")


async def example_agent_basic() -> None:
    """Basic Agent usage with streaming."""
    print("=== Basic Agent example ===")
    agent = Agent(model="gpt-5.2-codex")

    async for chunk in agent.run("Hello! Say hi back in one sentence."):
        print(chunk, end="", flush=True)
    print("\n")


async def example_get_full_text() -> None:
    """Get full text instead of streaming."""
    print("=== Full text example ===")
    agent = Agent()

    # Await the text directly
    text = await agent.run("What is the capital of France? One word answer.").text()
    print(f"Answer: {text}\n")


async def example_builder_pattern() -> None:
    """Configure agent with builder pattern."""
    print("=== Builder pattern example ===")
    agent = (
        Agent()
        .model("gpt-5.2-codex")
        .cwd("/tmp")
        .effort("medium")
        .auto_approve_commands()
    )

    async for chunk in agent.run("Say 'Builder pattern works!'"):
        print(chunk, end="", flush=True)
    print("\n")


async def example_conversation() -> None:
    """Multi-turn conversation using context manager."""
    print("=== Conversation example ===")
    agent = Agent(auto_approve=True)

    async with agent.conversation() as conv:
        # First message
        response = await conv.send("Hi! My name is Alice.")
        print(f"Response 1: {response.text}")

        # Follow-up (agent remembers context)
        response = await conv.send("What's my name?")
        print(f"Response 2: {response.text}")
    print()


async def main() -> None:
    await example_one_liner()
    await example_agent_basic()
    await example_get_full_text()
    await example_builder_pattern()
    await example_conversation()


if __name__ == "__main__":
    anyio.run(main)
