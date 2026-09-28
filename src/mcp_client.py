"""
MCP Client Module
Manages stdio connection and JSON-RPC protocol to an MCP server subprocess.
"""
import subprocess
import json
import sys
import os
from typing import Dict, Any, List, Optional

class MCPClient:
    def __init__(self, name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = {**os.environ, **(env or {})}
        self.process: Optional[subprocess.Popen] = None
        self._msg_id = 0
        self.server_info: Dict[str, Any] = {}
        self.capabilities: Dict[str, Any] = {}
        self.tools: List[Dict[str, Any]] = []

    def start(self):
        full_cmd = [self.command] + self.args
        self.process = subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=self.env
        )
        self._initialize()

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.process or self.process.poll() is not None:
            raise RuntimeError(f"MCP server '{self.name}' is not running.")

        req_id = self._next_id()
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method
        }
        if params is not None:
            msg["params"] = params

        wire_line = json.dumps(msg) + "\n"
        self.process.stdin.write(wire_line)
        self.process.stdin.flush()

        # Read response line
        line = self.process.stdout.readline()
        if not line:
            stderr_out = self.process.stderr.read()
            raise RuntimeError(f"Server '{self.name}' closed stdout. Stderr: {stderr_out}")

        res = json.loads(line)
        if "error" in res:
            raise RuntimeError(f"MCP Error from '{self.name}': {res['error']}")
        return res

    def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        if not self.process or self.process.poll() is not None:
            raise RuntimeError(f"MCP server '{self.name}' is not running.")
        msg = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params is not None:
            msg["params"] = params
        wire_line = json.dumps(msg) + "\n"
        self.process.stdin.write(wire_line)
        self.process.stdin.flush()

    def _initialize(self):
        # 1. Initialize
        res = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "ai-rag-agent-host",
                "version": "1.0.0"
            }
        })
        init_result = res.get("result", {})
        self.server_info = init_result.get("serverInfo", {})
        self.capabilities = init_result.get("capabilities", {})

        # 2. Initialized Notification
        self.send_notification("notifications/initialized")

    def list_tools(self) -> List[Dict[str, Any]]:
        res = self.send_request("tools/list")
        self.tools = res.get("result", {}).get("tools", [])
        return self.tools

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        res = self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return res.get("result", {})

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
