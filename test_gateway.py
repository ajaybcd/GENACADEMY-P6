import pytest
from fastapi.testclient import TestClient
import gateway


class StubSanitizer:
    def sanitize(self, text):
        return {"sanitized_text": text.replace("alex@example.com", "<EMAIL_ADDRESS>"),
                "detections": {"EMAIL_ADDRESS": 1}, "language": "en", "threshold": .35}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(gateway, "get_sanitizer", lambda: StubSanitizer())
    return TestClient(gateway.app)


@pytest.mark.parametrize("route,setting", [("/chat", "LLM_RECEIVER_URL"), ("/documents", "VECTOR_RECEIVER_URL")])
def test_forward_only_sanitized(client, monkeypatch, route, setting):
    captured = []
    class Receiver:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json):
            captured.append(json)
            return gateway.httpx.Response(200, request=gateway.httpx.Request("POST", url))
    monkeypatch.setenv(setting, "http://127.0.0.1:9010/receive")
    monkeypatch.setattr(gateway.httpx, "Client", Receiver)
    response = client.post(route, json={"text": "Email alex@example.com"})
    assert response.status_code == 200
    assert captured == [{"text": "Email <EMAIL_ADDRESS>"}]
    assert "alex@example.com" not in response.text


def test_closed_on_sanitizer_failure(client, monkeypatch):
    def fail(): raise RuntimeError("alex@example.com")
    monkeypatch.setattr(gateway, "get_sanitizer", fail)
    for route in ["/sanitize", "/chat", "/documents"]:
        response = client.post(route, json={"text": "alex@example.com"})
        assert response.status_code == 503
        assert "alex@example.com" not in response.text


def test_validation_never_echoes_input(client):
    for body in [{"text": "alex@example.com", "api_key": "secret"}, {"text": "x" * 20001}, {"text": ""}]:
        response = client.post("/sanitize", json=body)
        assert response.status_code == 422
        assert "secret" not in response.text
        assert "alex@example.com" not in response.text


def test_unconfigured_receiver_blocks(client, monkeypatch):
    monkeypatch.delenv("LLM_RECEIVER_URL", raising=False)
    assert client.post("/chat", json={"text": "alex@example.com"}).status_code == 503


def test_receiver_error_does_not_leak(client, monkeypatch):
    class Receiver:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): raise RuntimeError("sensitive receiver trace")
    monkeypatch.setenv("LLM_RECEIVER_URL", "http://127.0.0.1:9010")
    monkeypatch.setattr(gateway.httpx, "Client", Receiver)
    response = client.post("/chat", json={"text": "alex@example.com"})
    assert response.status_code == 502
    assert "sensitive" not in response.text
