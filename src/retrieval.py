from langchain_chroma import Chroma

from sentence_transformers import CrossEncoder

def search(vectorstore, query, k=5):
    """
    Search vectorstore using similarity search and re-rank with CrossEncoder.
    """
    # Fetch more candidates initially for re-ranking
    candidates = vectorstore.similarity_search(query, k=k*3)
    
    # Initialize CrossEncoder
    cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    
    # Create pairs for scoring
    pairs = [[query, doc.page_content] for doc in candidates]
    scores = cross_encoder.predict(pairs)
    
    # Attach scores and sort
    for score, doc in zip(scores, candidates):
        doc.metadata['cross_encoder_score'] = score
        
    reranked_candidates = sorted(candidates, key=lambda x: x.metadata['cross_encoder_score'], reverse=True)
    
    return reranked_candidates[:k]