"""Query a PureStrata corpus from Grok (or any OpenAI-compatible API) with tool calling.

The PureStrata tool schemas are passed to the chat completions endpoint;
tool calls are executed locally against your corpus, and results are sent
back with provenance. Your data never leaves your machine except through
the API you configure.

    export PURESTRATA_BASE_URL=https://api.x.ai/v1      # or https://api.openai.com/v1
    export PURESTRATA_API_KEY=your-key
    export PURESTRATA_MODEL=grok-4                     # model id of your provider
    uv run python examples/api_tool_use.py "The lathe is vibrating during cutting. What should we check?"
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

from purestrata import Corpus, ToolError, ToolExecutor, openai_tools

HERE = Path(__file__).resolve().parent


def call_llm(base_url: str, api_key: str, model: str, messages: list[dict], tools: list[dict]) -> dict:
    payload = {"model": model, "messages": messages, "tools": tools}
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def main() -> None:
    base_url = os.environ.get("PURESTRATA_BASE_URL", "https://api.x.ai/v1")
    api_key = os.environ.get("PURESTRATA_API_KEY", "")
    model = os.environ.get("PURESTRATA_MODEL", "grok-4")
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "The lathe is vibrating during cutting. What should we check?"
    )
    corpus_dir = os.environ.get("PURESTRATA_CORPUS", str(HERE / "corpus"))
    if not api_key:
        print("Set PURESTRATA_API_KEY to run this example.", file=sys.stderr)
        sys.exit(1)

    executor = ToolExecutor(Corpus.load(corpus_dir))
    tools = openai_tools()
    messages: list[dict] = [{"role": "user", "content": question}]

    for _round in range(5):
        data = call_llm(base_url, api_key, model, messages, tools)
        message = data["choices"][0]["message"]
        messages.append(message)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            print(message.get("content") or "(no content returned)")
            return
        for call in tool_calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"-> {name}({args})")
            try:
                result = executor.execute(name, args)
            except ToolError as exc:
                result = {"error": str(exc)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )


if __name__ == "__main__":
    main()
