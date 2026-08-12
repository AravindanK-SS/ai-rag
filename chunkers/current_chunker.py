from langchain_text_splitters import RecursiveCharacterTextSplitter


def current_chunker(documents):
    """
    Split documents using RecursiveCharacterTextSplitter.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(documents)

    return chunks