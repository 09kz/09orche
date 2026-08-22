import json

import httpx
import pytest
import respx

from conclave import cost
from conclave.agent import AgentError, run_agent

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "notes.txt").write_text("the secret number is 7", encoding="utf-8")
    return tmp_path


def final_answer(text: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": text}}]}
    )


def tool_call_response(name: str, arguments: dict, call_id: str = "call_1") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(arguments)},
                            }
                        ],
                    }
                }
            ]
        },
    )


@respx.mock
async def test_agent_returns_final_answer_with_no_tool_calls(workspace):
    respx.post(CHAT_URL).mock(return_value=final_answer("done"))

    result = await run_agent("key", "acme/model", "read", workspace, "do something")

    assert result == "done"


@respx.mock
async def test_agent_executes_tool_call_then_returns_answer(workspace):
    respx.post(CHAT_URL).mock(
        side_effect=[
            tool_call_response("read_file", {"path": "notes.txt"}),
            final_answer("the number is 7"),
        ]
    )

    result = await run_agent("key", "acme/model", "read", workspace, "what's the secret number?")

    assert "7" in result


@respx.mock
async def test_agent_tool_result_is_fed_back_to_model(workspace):
    route = respx.post(CHAT_URL).mock(
        side_effect=[
            tool_call_response("read_file", {"path": "notes.txt"}),
            final_answer("ok"),
        ]
    )

    await run_agent("key", "acme/model", "read", workspace, "read the notes")

    second_call_body = json.loads(route.calls[1].request.content)
    tool_messages = [m for m in second_call_body["messages"] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "secret number is 7" in tool_messages[0]["content"]


@respx.mock
async def test_agent_appends_extra_system_prompt(workspace):
    route = respx.post(CHAT_URL).mock(return_value=final_answer("ok"))

    await run_agent(
        "key", "acme/model", "read", workspace, "hi",
        extra_system_prompt="You are a strict code reviewer.",
    )

    sent = json.loads(route.calls[0].request.content)
    system_message = sent["messages"][0]
    assert system_message["role"] == "system"
    assert "sandboxed workspace" in system_message["content"]  # base prompt kept
    assert "strict code reviewer" in system_message["content"]  # persona appended


@respx.mock
async def test_agent_stops_at_iteration_limit(workspace):
    respx.post(CHAT_URL).mock(
        return_value=tool_call_response("list_dir", {"path": "."})
    )

    result = await run_agent("key", "acme/model", "read", workspace, "loop forever")

    assert "iteration limit" in result


@respx.mock
async def test_agent_raises_on_http_error(workspace):
    respx.post(CHAT_URL).mock(return_value=httpx.Response(500, text="boom"))

    with pytest.raises(AgentError):
        await run_agent("key", "acme/model", "read", workspace, "hi")


@respx.mock
async def test_agent_retries_429_within_a_single_turn(workspace):
    route = respx.post(CHAT_URL).mock(
        side_effect=[httpx.Response(429), final_answer("recovered")]
    )

    result = await run_agent("key", "acme/model", "read", workspace, "hi")

    assert result == "recovered"
    assert route.call_count == 2


@respx.mock
async def test_agent_retries_429_on_a_later_turn(workspace):
    route = respx.post(CHAT_URL).mock(
        side_effect=[
            tool_call_response("read_file", {"path": "notes.txt"}),
            httpx.Response(429),
            final_answer("recovered after tool use"),
        ]
    )

    result = await run_agent("key", "acme/model", "read", workspace, "read then answer")

    assert result == "recovered after tool use"
    assert route.call_count == 3


@respx.mock
async def test_agent_raises_after_exhausting_retries(workspace):
    respx.post(CHAT_URL).mock(return_value=httpx.Response(429))

    with pytest.raises(AgentError, match="429"):
        await run_agent("key", "acme/model", "read", workspace, "hi")


@respx.mock
async def test_agent_refuses_when_budget_already_exhausted(workspace, monkeypatch):
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "0.001")
    cost.record(0.01)
    route = respx.post(CHAT_URL).mock(return_value=final_answer("should not be reached"))

    with pytest.raises(AgentError, match="budget"):
        await run_agent("key", "acme/model", "read", workspace, "hi")

    assert route.call_count == 0


@respx.mock
async def test_agent_sends_reasoning_effort_when_given(workspace):
    route = respx.post(CHAT_URL).mock(return_value=final_answer("ok"))

    await run_agent(
        "key", "acme/model", "read", workspace, "hi", reasoning_effort="low"
    )

    sent = json.loads(route.calls[0].request.content)
    assert sent["reasoning"] == {"effort": "low"}


async def test_agent_rejects_invalid_reasoning_effort(workspace):
    with pytest.raises(AgentError, match="reasoning_effort must be one of"):
        await run_agent(
            "key", "acme/model", "read", workspace, "hi", reasoning_effort="nonsense"
        )


@respx.mock
async def test_agent_redacts_secret_in_tool_result(workspace, tmp_path):
    secret_file = workspace / "creds.txt"
    secret_file.write_text("sk-or-v1-" + "a1b2c3" * 10, encoding="utf-8")

    route = respx.post(CHAT_URL).mock(
        side_effect=[
            tool_call_response("read_file", {"path": "creds.txt"}),
            final_answer("done"),
        ]
    )

    await run_agent("key", "acme/model", "read", workspace, "read creds.txt")

    second_call_body = json.loads(route.calls[1].request.content)
    tool_message = next(m for m in second_call_body["messages"] if m.get("role") == "tool")
    assert "sk-or-v1-" not in tool_message["content"]
    assert "[REDACTED]" in tool_message["content"]


@respx.mock
async def test_agent_write_tool_unavailable_at_read_tier(workspace):
    respx.post(CHAT_URL).mock(
        side_effect=[
            tool_call_response("write_file", {"path": "x.txt", "content": "y"}),
            final_answer("gave up"),
        ]
    )

    result = await run_agent("key", "acme/model", "read", workspace, "write a file")

    assert result == "gave up"
    assert not (workspace / "x.txt").exists()
