import httpx
import pytest
import respx

from orche.server import build_server

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture
def server(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text(
        '[models.foo]\nid = "acme/foo"\ndescription = "A test model."\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return build_server()


def test_build_server_exits_without_api_key(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text(
        '[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8"
    )
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(models_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit):
        build_server()


def test_build_server_exits_on_invalid_max_cost(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text('[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8")
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ORCHE_MAX_COST_USD", "not-a-number")

    with pytest.raises(SystemExit):
        build_server()


def test_build_server_exits_on_invalid_timeout(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text('[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8")
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ORCHE_TIMEOUT_S", "soon")

    with pytest.raises(SystemExit):
        build_server()


async def test_registers_one_tool_per_model_plus_list_models(server):
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "ask_foo",
        "list_models",
        "spend_status",
        "save_profile",
        "list_profiles",
        "ask_profile",
        "agent_profile",
    }


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
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(models_path))
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
    assert "no ORCHE_MAX_COST_USD" in result[0].text


@respx.mock
async def test_ask_tool_records_cost_and_spend_status_reflects_it(monkeypatch, tmp_path):
    models_path = tmp_path / "models.toml"
    models_path.write_text('[models.foo]\nid = "acme/foo"\ndescription = "d"\n', encoding="utf-8")
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(models_path))
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
    monkeypatch.setenv("ORCHE_MODELS_PATH", str(models_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ORCHE_MAX_COST_USD", "0.001")
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


@pytest.fixture
def profiles_path(monkeypatch, tmp_path):
    path = tmp_path / "profiles.toml"
    monkeypatch.setenv("ORCHE_PROFILES_PATH", str(path))
    return path


async def test_save_profile_rejects_unknown_base_alias(server, profiles_path):
    result = await server.call_tool(
        "save_profile",
        {"name": "reviewer", "base_alias": "nonexistent", "system_prompt": "Be strict."},
    )
    assert "unknown base_alias" in result[0].text


async def test_save_profile_rejects_bad_reasoning_effort(server, profiles_path):
    result = await server.call_tool(
        "save_profile",
        {
            "name": "reviewer",
            "base_alias": "foo",
            "system_prompt": "Be strict.",
            "reasoning_effort": "ultra",
        },
    )
    assert "reasoning_effort must be one of" in result[0].text


async def test_save_profile_rejects_bad_agent_tools(server, profiles_path):
    result = await server.call_tool(
        "save_profile",
        {
            "name": "reviewer",
            "base_alias": "foo",
            "system_prompt": "Be strict.",
            "agent_tools": "godmode",
        },
    )
    assert "agent_tools must be one of" in result[0].text


async def test_save_profile_succeeds_and_list_profiles_reports_it(server, profiles_path):
    save_result = await server.call_tool(
        "save_profile",
        {"name": "reviewer", "base_alias": "foo", "system_prompt": "Be strict."},
    )
    assert "saved profile 'reviewer'" in save_result[0].text

    list_result = await server.call_tool("list_profiles", {})
    assert "reviewer" in list_result[0].text
    assert "foo" in list_result[0].text


async def test_list_profiles_reports_none_saved_yet(server, profiles_path):
    result = await server.call_tool("list_profiles", {})
    assert "No profiles saved yet" in result[0].text


async def test_ask_profile_rejects_unknown_profile(server, profiles_path):
    result = await server.call_tool("ask_profile", {"name": "ghost", "prompt": "hi"})
    assert "unknown profile" in result[0].text


@respx.mock
async def test_ask_profile_uses_saved_persona(server, profiles_path):
    await server.call_tool(
        "save_profile",
        {"name": "reviewer", "base_alias": "foo", "system_prompt": "Be strict."},
    )
    route = respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "reviewed"}}]}
        )
    )

    result = await server.call_tool("ask_profile", {"name": "reviewer", "prompt": "check this"})

    assert "reviewed" in result[0].text
    sent = route.calls[0].request.content.decode()
    assert "Be strict." in sent


async def test_agent_profile_errors_without_any_tier(server, profiles_path, tmp_path):
    await server.call_tool(
        "save_profile",
        {"name": "reviewer", "base_alias": "foo", "system_prompt": "Be strict."},
    )

    result = await server.call_tool(
        "agent_profile", {"name": "reviewer", "prompt": "hi", "workspace": str(tmp_path)}
    )

    assert "has no agent_tools tier" in result[0].text


@respx.mock
async def test_agent_profile_uses_own_tier_override(server, profiles_path, tmp_path):
    await server.call_tool(
        "save_profile",
        {
            "name": "reviewer",
            "base_alias": "foo",
            "system_prompt": "Be strict.",
            "agent_tools": "read",
        },
    )
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "reviewed"}}]}
        )
    )

    result = await server.call_tool(
        "agent_profile", {"name": "reviewer", "prompt": "hi", "workspace": str(tmp_path)}
    )

    assert "reviewed" in result[0].text
