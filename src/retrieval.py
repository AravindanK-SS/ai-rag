# from sentence_transformers import CrossEncoder

def search(vectorstore, query, k=5):
    """
    Search vectorstore using similarity search.
    (CrossEncoder reranking commented out as per evaluation needs)
    """
    return vectorstore.similarity_search(query, k=k)


# --- Reference: CrossEncoder Reranking ---
# def search_with_reranker(vectorstore, query, k=5):
#     candidates = vectorstore.similarity_search(query, k=k*3)
#     cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
#     pairs = [[query, doc.page_content] for doc in candidates]
#     scores = cross_encoder.predict(pairs)
#     for score, doc in zip(scores, candidates):
#         doc.metadata['cross_encoder_score'] = score
#     reranked_candidates = sorted(candidates, key=lambda x: x.metadata['cross_encoder_score'], reverse=True)
#     return reranked_candidates[:k]
