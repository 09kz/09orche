import httpx
import pytest
import respx

from conclave._http import post_with_retry

URL = "https://example.test/chat"


@respx.mock
async def test_returns_200_immediately():
    respx.post(URL).mock(return_value=httpx.Response(200, json={"ok": True}))

    async with httpx.AsyncClient() as client:
        r = await post_with_retry(client, URL, {}, {})

    assert r.status_code == 200


@respx.mock
async def test_retries_retryable_status_then_succeeds():
    route = respx.post(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )

    async with httpx.AsyncClient() as client:
        r = await post_with_retry(client, URL, {}, {})

    assert r.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_does_not_retry_non_retryable_status():
    route = respx.post(URL).mock(return_value=httpx.Response(400))

    async with httpx.AsyncClient() as client:
        r = await post_with_retry(client, URL, {}, {})

    assert r.status_code == 400
    assert route.call_count == 1


@respx.mock
async def test_returns_final_response_after_exhausting_retries():
    route = respx.post(URL).mock(return_value=httpx.Response(429))

    async with httpx.AsyncClient() as client:
        r = await post_with_retry(client, URL, {}, {})

    assert r.status_code == 429
    assert route.call_count == 4  # 1 initial + 3 retries


@respx.mock
async def test_recovers_from_transport_error():
    route = respx.post(URL).mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"ok": True})]
    )

    async with httpx.AsyncClient() as client:
        r = await post_with_retry(client, URL, {}, {})

    assert r.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_raises_after_exhausting_transport_error_retries():
    respx.post(URL).mock(side_effect=httpx.ConnectError("boom"))

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.TransportError):
            await post_with_retry(client, URL, {}, {})
