import anyio

from codex_agent_sdk import CodexClient, CodexClientOptions


async def main() -> None:
    options = CodexClientOptions(client_name="codex_sdk_py", client_version="0.1.0")
    async with CodexClient(options=options) as client:
        thread = await client.thread_start({"model": "gpt-5.1-codex"})
        async for delta in client.stream_prompt_text(
            thread["thread"]["id"], "Hello Codex"
        ):
            print(delta, end="", flush=True)


if __name__ == "__main__":
    anyio.run(main)
