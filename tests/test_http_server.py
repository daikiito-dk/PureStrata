"""Remote MCP (Streamable HTTP) tests. Skipped when the mcp extra is missing."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import urllib.error
import urllib.request

import pytest

pytest.importorskip("mcp")

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "purestrata-test", "version": "0"},
    },
}


def _post(url: str, payload: dict, headers: dict) -> tuple[int, dict, str]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            lowered = {key.lower(): value for key, value in response.headers.items()}
            return response.status, lowered, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        lowered = {key.lower(): value for key, value in exc.headers.items()}
        return exc.code, lowered, exc.read().decode("utf-8")


@pytest.fixture
def http_server(tmp_path, step_path, failures_csv):
    """Run the authenticated remote MCP server on an ephemeral local port."""
    from purestrata.cli import main

    corpus_dir = tmp_path / "corpus"
    assert main(["ingest-step", str(step_path), "--out", str(corpus_dir)]) == 0
    assert main(["ingest-failures", str(failures_csv), "--out", str(corpus_dir)]) == 0

    from purestrata.corpus import Corpus
    from purestrata.mcp_server import StaticTokenVerifier, _resource_server_auth, build_mcp_server

    token = "scene-test-token"
    # The advertised resource URL uses the placeholder port; the real bind
    # port is chosen by uvicorn below and does not depend on the settings.
    auth = _resource_server_auth(host="127.0.0.1", port=8000)
    mcp = build_mcp_server(
        Corpus.load(corpus_dir),
        token_verifier=StaticTokenVerifier(token),
        auth=auth,
    )

    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(mcp.streamable_http_app(), host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if server.started and server.servers:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("uvicorn did not start")

    port = server.servers[0].sockets[0].getsockname()[1]
    yield port, token
    server.should_exit = True
    thread.join(timeout=5)


def test_static_token_verifier_accepts_only_the_configured_token():
    from purestrata.mcp_server import StaticTokenVerifier

    verifier = StaticTokenVerifier("secret-token")

    access = asyncio.run(verifier.verify_token("secret-token"))
    assert access is not None
    assert access.client_id == "purestrata-static"
    assert access.scopes == ["mcp"]

    assert asyncio.run(verifier.verify_token("secret-tokens")) is None
    assert asyncio.run(verifier.verify_token("wrong-token")) is None
    assert asyncio.run(verifier.verify_token("")) is None
    with pytest.raises(ValueError, match="must not be empty"):
        StaticTokenVerifier("")


def test_stdio_rejects_http_only_flags(capsys):
    from purestrata.cli import main

    rc = main(["serve", "--corpus", "corpus", "--token", "x"])
    assert rc == 1
    assert "require --transport http" in capsys.readouterr().err


def test_http_transport_requires_a_token(capsys, monkeypatch):
    from purestrata.cli import main

    monkeypatch.delenv("PURESTRATA_TOKEN", raising=False)
    rc = main(["serve", "--corpus", "corpus", "--transport", "http"])
    assert rc == 1
    assert "PURESTRATA_TOKEN" in capsys.readouterr().err


def test_failed_token_verification_is_logged_without_token_material(caplog):
    from purestrata.mcp_server import StaticTokenVerifier

    verifier = StaticTokenVerifier("secret-token")
    with caplog.at_level(logging.WARNING, logger="purestrata.mcp_server"):
        assert asyncio.run(verifier.verify_token("attacker-candidate")) is None
    assert "verification failed" in caplog.text
    assert "attacker-candidate" not in caplog.text


def test_remote_posture_warnings():
    import warnings as stdlib_warnings

    from purestrata.mcp_server import _check_remote_posture

    with pytest.warns(UserWarning, match="plaintext HTTP"):
        _check_remote_posture("0.0.0.0", "x" * 32)
    with pytest.warns(UserWarning, match="shorter than"):
        _check_remote_posture("127.0.0.1", "short")
    with stdlib_warnings.catch_warnings():
        stdlib_warnings.simplefilter("error")
        _check_remote_posture("127.0.0.1", "x" * 32)


def test_serve_token_flag_warns_about_process_list(capsys, monkeypatch, tmp_path):
    import purestrata.mcp_server as mcp_server
    from purestrata.cli import main

    monkeypatch.delenv("PURESTRATA_TOKEN", raising=False)
    monkeypatch.setattr(mcp_server, "serve", lambda *args, **kwargs: None)
    rc = main(["serve", "--transport", "http", "--token", "x" * 32, "--corpus", str(tmp_path)])
    assert rc == 0
    assert "process list" in capsys.readouterr().err


def test_remote_mcp_rejects_requests_without_valid_token(http_server):
    port, token = http_server
    url = f"http://127.0.0.1:{port}/mcp"

    status, headers, _ = _post(url, INITIALIZE, {})
    assert status == 401
    assert headers.get("www-authenticate")

    status, _, _ = _post(url, INITIALIZE, {"Authorization": "Bearer wrong-token"})
    assert status == 401


def test_remote_mcp_serves_initialize_with_valid_token(http_server):
    port, token = http_server

    status, headers, body = _post(
        f"http://127.0.0.1:{port}/mcp",
        INITIALIZE,
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
        },
    )

    assert status == 200
    assert "purestrata" in body
