from langchain_chroma import Chroma
from sentence_transformers import CrossEncoder

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker

def search(vectorstore, query, k=5):
    """
    Search vectorstore and rerank results using a Cross-Encoder.
    """
    # 1. Retrieve a larger candidate pool (5x k, minimum 15)
    candidate_k = max(k * 5, 15)
    candidates = vectorstore.similarity_search(query, k=candidate_k)
    
    if not candidates:
        return []
        
    # 2. Score candidate chunks using the Cross-Encoder
    reranker = get_reranker()
    pairs = [[query, doc.page_content] for doc in candidates]
    scores = reranker.predict(pairs)
    
    # 3. Sort candidates by score and return the top k
    scored_docs = list(zip(candidates, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    return [doc for doc, score in scored_docs[:k]]