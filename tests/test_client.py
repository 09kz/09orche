import httpx
import pytest
import respx

from conclave.client import OpenRouterError, ask
from conclave.config import ModelSpec

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def ok_response(text: str, tokens: int = 42) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": {"total_tokens": tokens},
        },
    )


@respx.mock
async def test_ask_returns_content_with_footer():
    respx.post(CHAT_URL).mock(return_value=ok_response("hello there"))
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    result = await ask("key", spec, {"foo": spec}, "hi", "sys")

    assert "hello there" in result
    assert "acme/foo" in result
    assert "42 tokens" in result


@respx.mock
async def test_ask_uses_reasoning_field_when_content_empty():
    message = {"role": "assistant", "content": "", "reasoning": "the answer"}
    resp = httpx.Response(
        200,
        json={"choices": [{"message": message}], "usage": {}},
    )
    respx.post(CHAT_URL).mock(return_value=resp)
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    result = await ask("key", spec, {"foo": spec}, "hi", "sys")

    assert "the answer" in result


@respx.mock
async def test_ask_retries_on_429_then_succeeds():
    route = respx.post(CHAT_URL).mock(
        side_effect=[httpx.Response(429), ok_response("recovered")]
    )
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    result = await ask("key", spec, {"foo": spec}, "hi", "sys")

    assert "recovered" in result
    assert route.call_count == 2


@respx.mock
async def test_ask_falls_back_after_exhausted_retries():
    respx.post(CHAT_URL).mock(
        side_effect=lambda req: (
            httpx.Response(429)
            if b"acme/primary" in req.content
            else ok_response("from fallback")
        )
    )
    primary = ModelSpec(alias="primary", id="acme/primary", description="d", fallback="backup")
    backup = ModelSpec(alias="backup", id="acme/backup", description="d")
    catalogue = {"primary": primary, "backup": backup}

    result = await ask("key", primary, catalogue, "hi", "sys")

    assert "from fallback" in result
    assert "falling back to backup" in result


@respx.mock
async def test_ask_raises_without_fallback():
    respx.post(CHAT_URL).mock(return_value=httpx.Response(500))
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    with pytest.raises(OpenRouterError):
        await ask("key", spec, {"foo": spec}, "hi", "sys")


@respx.mock
async def test_ask_does_not_retry_on_400():
    route = respx.post(CHAT_URL).mock(return_value=httpx.Response(400, text="bad request"))
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    with pytest.raises(OpenRouterError, match="400"):
        await ask("key", spec, {"foo": spec}, "hi", "sys")

    assert route.call_count == 1


@respx.mock
async def test_ask_sends_reasoning_effort_when_given():
    route = respx.post(CHAT_URL).mock(return_value=ok_response("ok"))
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    await ask("key", spec, {"foo": spec}, "hi", "sys", reasoning_effort="high")

    import json

    sent = json.loads(route.calls[0].request.content)
    assert sent["reasoning"] == {"effort": "high"}


@respx.mock
async def test_ask_omits_reasoning_when_not_given():
    route = respx.post(CHAT_URL).mock(return_value=ok_response("ok"))
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    await ask("key", spec, {"foo": spec}, "hi", "sys")

    import json

    sent = json.loads(route.calls[0].request.content)
    assert "reasoning" not in sent


async def test_ask_rejects_invalid_reasoning_effort():
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")

    with pytest.raises(OpenRouterError, match="reasoning_effort must be one of"):
        await ask("key", spec, {"foo": spec}, "hi", "sys", reasoning_effort="nonsense")


@respx.mock
async def test_ask_redacts_secret_in_prompt():
    route = respx.post(CHAT_URL).mock(return_value=ok_response("ok"))
    spec = ModelSpec(alias="foo", id="acme/foo", description="d")
    secret_prompt = "here is my key sk-or-v1-" + "a" * 60

    await ask("key", spec, {"foo": spec}, secret_prompt, "sys")

    sent_body = route.calls[0].request.content.decode()
    assert "sk-or-v1-" not in sent_body
    assert "[REDACTED]" in sent_body
