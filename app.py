import http.server
import socketserver
import json
import urllib.parse
import os
import sys

from src.mcp_agent import MCPAgent

PORT = 8080

print("=" * 60)
print("  Starting Week 9 Dynamic MCP Agent Server")
print("=" * 60)

# Initialize MCP Agent
try:
    agent = MCPAgent(config_path="config/mcp_servers.json")
    discovered = agent.list_discovered_tool_names()
    print(f"[✓] Dynamic MCP Tool Discovery successful!")
    print(f"[✓] Active Tools ({len(discovered)}): {discovered}")
except Exception as e:
    print(f"[!] Error initializing MCPAgent: {e}")
    agent = None

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/' or parsed.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
        elif parsed.path == '/api/tools':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            tools_info = []
            if agent:
                for t_name, t_meta in agent.tools_registry.items():
                    schema = t_meta.get("schema", {})
                    tools_info.append({
                        "name": t_name,
                        "server": t_meta.get("server_name"),
                        "description": schema.get("description", ""),
                        "inputSchema": schema.get("inputSchema", {})
                    })
            self.wfile.write(json.dumps({"tools": tools_info}).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/query':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
            except Exception:
                data = {}
                
            question = data.get('question') or data.get('query') or ''
            
            if not agent:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "answer": "MCPAgent is not initialized. Please check config/mcp_servers.json.",
                    "steps": [],
                    "discovered_tools": []
                }).encode('utf-8'))
                return

            try:
                trace = agent.run(question)
                response_payload = {
                    "query": trace.get("query", question),
                    "answer": trace.get("final_answer", ""),
                    "discovered_tools": trace.get("discovered_tools", []),
                    "steps": trace.get("steps", [])
                }
            except Exception as e:
                response_payload = {
                    "query": question,
                    "answer": f"Error running MCP Agent: {str(e)}",
                    "discovered_tools": agent.list_discovered_tool_names(),
                    "steps": []
                }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    # Allow port reuse
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n[✓] Web UI accessible at: http://localhost:{PORT}")
        print("Ready for queries. Press Ctrl+C to terminate.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server and MCP clients...")
            if agent:
                agent.shutdown()
