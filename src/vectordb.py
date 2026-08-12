from langchain_chroma import Chroma


def create_vectorstore(chunks, embedding_model, persist_directory):
    """
    Create and persist a Chroma vector database.
    """

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=persist_directory
    )

    return vectorstore