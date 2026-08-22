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


def test_build_server_exits_on_invalid_max_cost(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text('[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8")
    monkeypatch.setenv("CONCLAVE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "not-a-number")

    with pytest.raises(SystemExit):
        build_server()


def test_build_server_exits_on_invalid_timeout(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text('[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8")
    monkeypatch.setenv("CONCLAVE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("CONCLAVE_TIMEOUT_S", "soon")

    with pytest.raises(SystemExit):
        build_server()


async def test_registers_one_tool_per_model_plus_list_models(server):
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert names == {"ask_foo", "list_models", "spend_status"}


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


@pytest.fixture
def agent_server(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text(
        '[models.foo]\nid = "acme/foo"\ndescription = "A test model."\nagent_tools = "read"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CONCLAVE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return build_server()


async def test_agent_tool_registered_only_when_configured(agent_server):
    tools = await agent_server.list_tools()
    names = {t.name for t in tools}
    assert "agent_foo" in names


async def test_no_agent_tool_when_not_configured(server):
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert "agent_foo" not in names


async def test_agent_tool_rejects_missing_workspace(agent_server, tmp_path):
    result = await agent_server.call_tool(
        "agent_foo", {"prompt": "hi", "workspace": str(tmp_path / "does-not-exist")}
    )
    assert "not a directory" in result[0].text


@respx.mock
async def test_agent_tool_runs_agent_loop(agent_server, tmp_path):
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "all good"}}]}
        )
    )

    result = await agent_server.call_tool(
        "agent_foo", {"prompt": "look around", "workspace": str(tmp_path)}
    )
    assert "all good" in result[0].text


async def test_spend_status_reports_no_budget_by_default(server):
    result = await server.call_tool("spend_status", {})
    assert "no CONCLAVE_MAX_COST_USD" in result[0].text


@respx.mock
async def test_ask_tool_records_cost_and_spend_status_reflects_it(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text('[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8")
    monkeypatch.setenv("CONCLAVE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    server = build_server()

    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "hi"}}],
                "usage": {"total_tokens": 10, "cost": 0.0025},
            },
        )
    )
    await server.call_tool("ask_foo", {"prompt": "hi"})

    result = await server.call_tool("spend_status", {})
    assert "$0.0025" in result[0].text


@respx.mock
async def test_ask_tool_refuses_once_budget_exhausted(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text('[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8")
    monkeypatch.setenv("CONCLAVE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "0.001")
    server = build_server()

    route = respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "hi"}}],
                "usage": {"cost": 0.01},
            },
        )
    )
    await server.call_tool("ask_foo", {"prompt": "hi"})
    assert route.call_count == 1

    result = await server.call_tool("ask_foo", {"prompt": "again"})
    assert "budget" in result[0].text
    assert route.call_count == 1  # second call was refused before hitting the network
