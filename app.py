import http.server
import socketserver
import json
import urllib.parse
import os
from src.embedding import get_embedding_model
from src.retrieval import search
from src.llm import get_llm
from langchain_chroma import Chroma

PORT = 8080

print("Loading models (this might take a moment)...")
embedding = get_embedding_model()
llm = get_llm()
vectorstore = Chroma(persist_directory="vectorstore/current", embedding_function=embedding)
print("Models loaded successfully.")

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/query' and self.command == 'POST':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            question = data.get('question', '')
            
            # WEEK 5 IMPROVEMENT: Retrieve top 5 instead of 3 to fix "Retriever Complete Miss"
            try:
                docs = search(vectorstore, question, k=5)
                context = "\n\n".join(doc.page_content for doc in docs)
            except Exception as search_err:
                # Fallback if search fails
                docs = []
                context = "Search failed."
                print(f"Search error: {search_err}")
            
            # WEEK 5 IMPROVEMENT: Added instruction to keep answers concise to fix "Verbosity"
            prompt = f"""
You are an HR Policy Assistant.

Answer ONLY using the context below. Keep your answers concise and directly to the point.

If the answer is not present, reply:

'I cannot answer this because the uploaded documents do not contain the required information.'

Context:
{context}

Question:
{question}
"""
            try:
                response = llm.invoke(prompt)
                answer = response.content
            except Exception as e:
                answer = str(e)
                
            sources = []
            for doc in docs:
                sources.append({
                    "file": doc.metadata.get('source_file') or os.path.basename(doc.metadata.get('source', '')),
                    "page": doc.metadata.get('page'),
                    "chunk": doc.metadata.get('chunk_id')
                })
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"answer": answer, "sources": sources}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('index.html', 'rb') as f:
                self.wfile.write(f.read())
        else:
            super().do_GET()

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Server starting on http://localhost:{PORT}")
        httpd.serve_forever()
