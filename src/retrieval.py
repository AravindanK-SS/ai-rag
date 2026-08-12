from langchain_chroma import Chroma


def search(vectorstore, query, k=5):
    return vectorstore.similarity_search(query, k=k)