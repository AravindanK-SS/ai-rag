import json
import os
import sys
from langchain_chroma import Chroma
from src.embedding import get_embedding_model
from src.retrieval import search
from src.llm import get_llm

# Reconfigure stdout to use utf-8 to avoid encoding errors on Windows
sys.stdout.reconfigure(encoding='utf-8')

def run_inspection():
    embedding = get_embedding_model()
    llm = get_llm()
    
    with open("results/questions.json", "r") as f:
        questions = json.load(f)
        
    stores = {
        "Current": Chroma(
            persist_directory="vectorstore/current",
            embedding_function=embedding,
        ),
        "Structure": Chroma(
            persist_directory="vectorstore/structure",
        ),
    }
    
    for name, db in stores.items():
        print("=" * 100)
        print(f"VECTOR STORE: {name} (Evaluating k=3)")
        print("=" * 100)
        
        hit_count = 0
        
        for q in questions:
            qid = q["id"]
            question = q["question"]
            expected = q["expected_document"]
            
            # Retrieve top 3
            docs = search(db, question, k=3)
            
            # Check if expected document is in retrieved docs
            retrieved_sources = [d.metadata.get("source_file", "") for d in docs]
            # fallback to source path parsing if source_file not in metadata
            if not retrieved_sources or all(s == "" for s in retrieved_sources):
                retrieved_sources = [os.path.basename(d.metadata.get("source", "")) for d in docs]
                
            hit = any(expected in src for src in retrieved_sources)
            if hit:
                hit_count += 1
                
            context = "\n\n".join(d.page_content for d in docs)
            
            prompt = f"""
You are an HR Policy Assistant.

Answer ONLY using the context below.

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
                answer = f"Error calling LLM: {str(e)}"
                
            print(f"\nQID: {qid} | Question: {question}")
            print(f"Expected Doc: {expected}")
            print(f"Retrieved Top 3: {retrieved_sources}")
            print(f"Hit @ 3: {'PASS' if hit else 'FAIL'}")
            print(f"LLM Answer:\n{answer}")
            print("-" * 50)
            
        print(f"\n{name} Hit-rate@3: {hit_count}/{len(questions)} ({hit_count/len(questions)*100:.1f}%)\n")

if __name__ == "__main__":
    run_inspection()
