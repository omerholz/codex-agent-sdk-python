import os

import pytest

from codex_agent_sdk import CodexClient, CodexClientOptions

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_app_server_initialize_and_thread_list() -> None:
    if os.getenv("CODEX_INTEGRATION") != "1":
        pytest.skip("Set CODEX_INTEGRATION=1 to run app-server integration test")

    options = CodexClientOptions(
        codex_path=os.getenv("CODEX_CLI", "codex"),
        client_name="codex_sdk_py_tests",
        client_version="0.1.0",
    )

    async with CodexClient(options=options) as client:
        result = await client.request("thread/loaded/list")
        assert isinstance(result, dict)
        assert "data" in result
        assert isinstance(result["data"], list)
