"""MCP server: expose a PureStrata corpus to any MCP client.

Run ``purestrata serve --corpus <dir>`` and register the command in any
Model Context Protocol client (Claude Desktop, IDE agents, and other MCP
hosts). The server speaks JSON over stdio; every tool result embeds
provenance so answers stay auditable.

Remote mode (``--transport http``) speaks Streamable HTTP and acts as a
pure OAuth resource server: it validates bearer tokens but never issues
them. Self-hosting uses one pre-shared token; the hosted SaaS swaps the
verifier for JWKS validation against its authorization server. See
docs/MCP.md for the deployment patterns.

Requires the optional ``mcp`` extra: ``pip install 'purestrata[mcp]'``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import warnings
from pathlib import Path

from .corpus import Corpus
from .tools.executor import ToolError, ToolExecutor

_STATIC_SCOPES = ["mcp"]

logger = logging.getLogger(__name__)


def build_mcp_server(corpus: Corpus, *, token_verifier=None, auth=None):
    """Build an MCP server bound to a corpus.

    With ``token_verifier`` and ``auth`` (mcp auth settings) the server
    becomes an OAuth resource server that demands a bearer token on every
    remote request. Both must be given together.
    """
    mcp_cls = None
    try:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as mcp_cls  # type: ignore[no-redef]
    except ImportError:
        try:  # mcp 2.x renamed FastMCP to MCPServer
            from mcp.server.mcpserver import MCPServer as mcp_cls  # type: ignore[no-redef]
        except ImportError as exc:
            raise RuntimeError(
                "The MCP server requires the 'mcp' extra. "
                "Install it with: pip install 'purestrata[mcp]'"
            ) from exc

    kwargs = {}
    if token_verifier is not None or auth is not None:
        if token_verifier is None or auth is None:
            raise ValueError("Remote MCP requires both a token_verifier and auth settings.")
        kwargs = {"token_verifier": token_verifier, "auth": auth}
    try:
        mcp = mcp_cls("purestrata", **kwargs)
    except Exception as exc:
        raise RuntimeError(
            "Remote MCP (HTTP + auth) requires a newer 'mcp' extra. "
            "Install it with: pip install -U 'purestrata[mcp]'"
        ) from exc
    executor = ToolExecutor(corpus)

    def run(name: str, **kwargs) -> str:
        clean = {key: value for key, value in kwargs.items() if value is not None}
        try:
            return json.dumps(executor.execute(name, clean), ensure_ascii=False, default=str)
        except ToolError as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    @mcp.tool()
    def list_corpus() -> str:
        """Corpus inventory: total records, counts by kind, and loaded documents."""
        return run("list_corpus")

    @mcp.tool()
    def search_documents(query: str, kind: str | None = None, top_k: int = 5) -> str:
        """Search spec sheets and manuals. Returns ranked passages with provenance."""
        return run("search_documents", query=query, kind=kind, top_k=top_k)

    @mcp.tool()
    def get_safety_notices(query: str | None = None, top_k: int = 10) -> str:
        """Safety warnings and cautions, optionally ranked by a query."""
        return run("get_safety_notices", query=query, top_k=top_k)

    @mcp.tool()
    def get_procedure(procedure_id: str) -> str:
        """Full ordered steps of a maintenance procedure by its ID."""
        return run("get_procedure", procedure_id=procedure_id)

    @mcp.tool()
    def search_parts(query: str | None = None, top_k: int = 10) -> str:
        """Parts lookup: part number, name, quantity, spec."""
        return run("search_parts", query=query, top_k=top_k)

    @mcp.tool()
    def list_drawings() -> str:
        """CAD drawings in the corpus, with identifiers and layers."""
        return run("list_drawings")

    @mcp.tool()
    def get_drawing(drawing_id: str) -> str:
        """Full metadata of one CAD drawing: title block, layers, entities, bounds."""
        return run("get_drawing", drawing_id=drawing_id)

    @mcp.tool()
    def search_drawings(
        query: str | None = None,
        layer: str | None = None,
        min_diameter: float | None = None,
        max_diameter: float | None = None,
        fit: str | None = None,
        material: str | None = None,
        cad_format: str | None = None,
        top_k: int = 10,
    ) -> str:
        """Find drawings by geometry, attributes, and exact case-insensitive DXF layer."""
        return run(
            "search_drawings",
            query=query,
            layer=layer,
            min_diameter=min_diameter,
            max_diameter=max_diameter,
            fit=fit,
            material=material,
            cad_format=cad_format,
            top_k=top_k,
        )

    @mcp.tool()
    def search_failure_cases(query: str, equipment: str | None = None, top_k: int = 5) -> str:
        """Search past failures: symptom, root cause, countermeasure. Use for troubleshooting."""
        return run("search_failure_cases", query=query, equipment=equipment, top_k=top_k)

    @mcp.tool()
    def get_failure_case(case_id: str) -> str:
        """One full failure case by its case_id."""
        return run("get_failure_case", case_id=case_id)

    return mcp


class StaticTokenVerifier:
    """Accept exactly one pre-shared bearer token.

    The comparison is constant-time over SHA-256 digests, so token length
    never leaks through timing. This verifier is the self-hosting default;
    the hosted SaaS replaces it with JWKS validation against its
    authorization server (see docs/MCP.md).
    """

    def __init__(self, token: str, *, client_id: str = "purestrata-static") -> None:
        if not token:
            raise ValueError("A remote MCP token must not be empty.")
        self._digest = hashlib.sha256(token.encode("utf-8")).digest()
        self._client_id = client_id

    async def verify_token(self, token: str):
        """Return access info for the configured token, else None."""
        if not token:
            return None
        candidate = hashlib.sha256(token.encode("utf-8")).digest()
        if not hmac.compare_digest(candidate, self._digest):
            # Log failures so online guessing is visible; never log the
            # candidate token itself.
            logger.warning("MCP bearer token verification failed.")
            return None
        from mcp.server.auth.provider import AccessToken

        return AccessToken(
            token=token,
            client_id=self._client_id,
            scopes=list(_STATIC_SCOPES),
        )


def _resource_server_auth(
    *,
    host: str,
    port: int,
    authorization_server_url: str | None = None,
):
    """Build a token verifier and auth settings for the remote transport.

    ``resource_server_url`` is this server's own URL; ``issuer_url`` is the
    authorization server that issues tokens. With static tokens both
    default to the server's own URL: clients that speak OAuth discovery
    will find no authorization server there and must send the header
    directly. Point ``authorization_server_url`` at a real AS (for example
    the SaaS control plane) in production.
    """
    try:
        from mcp.server.auth.settings import AuthSettings
    except ImportError as exc:
        raise RuntimeError(
            "Remote MCP (HTTP + auth) requires a newer 'mcp' extra. "
            "Install it with: pip install -U 'purestrata[mcp]'"
        ) from exc
    base_url = f"http://{host}:{port}"
    return AuthSettings(
        issuer_url=authorization_server_url or base_url,
        resource_server_url=base_url,
        validate_token_resource=False,
    )


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_MIN_TOKEN_CHARS = 16


def _check_remote_posture(host: str, token: str) -> None:
    """Warn about plaintext bindings and weak tokens before serving."""
    if host not in _LOOPBACK_HOSTS:
        warnings.warn(
            f"Remote MCP will bind to {host} over plaintext HTTP: the bearer token and "
            "every corpus response are visible on the network path. Terminate TLS at a "
            "reverse proxy in front of this server (see docs/MCP.md).",
            stacklevel=3,
        )
    if len(token) < _MIN_TOKEN_CHARS:
        warnings.warn(
            f"The remote MCP token is shorter than {_MIN_TOKEN_CHARS} characters; "
            "use a long random token (for example `openssl rand -hex 32`).",
            stacklevel=3,
        )


def serve(
    corpus_dir: str | Path,
    *,
    embedding_model: str | Path | None = None,
    hybrid_search: bool = False,
    transport: str = "stdio",
    host: str | None = None,
    port: int | None = None,
    token: str | None = None,
    authorization_server_url: str | None = None,
) -> None:
    """Load a corpus and run the MCP server over stdio or Streamable HTTP."""
    corpus = Corpus.load(
        corpus_dir,
        embedding_model=embedding_model,
        hybrid_search=hybrid_search,
    )
    if transport == "stdio":
        build_mcp_server(corpus).run()
        return
    if transport != "http":
        raise ValueError(f"Unsupported transport: {transport}. Use 'stdio' or 'http'.")
    if not token:
        raise ValueError(
            "Remote MCP requires a bearer token (pass --token or set PURESTRATA_TOKEN)."
        )
    bind_host = host or "127.0.0.1"
    bind_port = port or 8000
    _check_remote_posture(bind_host, token)
    auth_settings = _resource_server_auth(
        host=bind_host,
        port=bind_port,
        authorization_server_url=authorization_server_url,
    )
    mcp = build_mcp_server(
        corpus,
        token_verifier=StaticTokenVerifier(token),
        auth=auth_settings,
    )
    mcp.run(transport="streamable-http", host=bind_host, port=bind_port)
