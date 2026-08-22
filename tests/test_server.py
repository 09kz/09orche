import httpx
import pytest
import respx

from conclave.server import build_server

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture
def server(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text(
        '[models.foo]\nid = "acme/foo"\ndescription = "A test model."\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CONCLAVE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return build_server()


def test_build_server_exits_without_api_key(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text(
        '[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8"
    )
    monkeypatch.setenv("CONCLAVE_MODELS_PATH", str(models_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit):
        build_server()


async def test_registers_one_tool_per_model_plus_list_models(server):
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert names == {"ask_foo", "list_models"}


async def test_list_models_reports_catalogue(server):
    result = await server.call_tool("list_models", {})
    text = result[0].text
    assert "ask_foo" in text
    assert "acme/foo" in text


@respx.mock
async def test_ask_tool_calls_openrouter_and_returns_text(server):
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "42"}}],
                "usage": {"total_tokens": 7},
            },
        )
    )

    result = await server.call_tool("ask_foo", {"prompt": "what is the answer?"})
    text = result[0].text
    assert "42" in text
