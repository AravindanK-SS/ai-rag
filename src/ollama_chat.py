"""
Minimal Ollama chat client (stdlib only) with native tool-calling.
This is where the model runs: on the host side, never inside an MCP server.
"""
import json
import os
import urllib.request
from typing import Any, Dict, List


class OllamaUnavailable(RuntimeError):
    """Ollama is unreachable or the requested model is not pulled."""


class OllamaChat:
    def __init__(self, model: str = None, host: str = None, timeout: int = 120):
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Returns the assistant message dict ({'content': str, 'tool_calls': [...]})."""
        payload = {"model": self.model, "messages": messages, "tools": tools,
                   "stream": False, "options": {"temperature": 0}}
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8")).get("message", {})
        except Exception as e:
            raise OllamaUnavailable(f"Ollama chat failed ({self.model} @ {self.host}): {e}") from e
