from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader


DATA_PATH = Path("data/addenda")


def load_documents():
    """
    Reads all PDFs from data/addenda
    Returns a list of LangChain Document objects.
    """

    all_documents = []

    pdf_files = list(DATA_PATH.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDF(s)\n")

    for pdf_file in pdf_files:
        print("=" * 60)
        print(f"Loading: {pdf_file.name}")

        loader = PyPDFLoader(str(pdf_file))
        documents = loader.load()

        print(f"Pages Loaded: {len(documents)}")

        all_documents.extend(documents)

    return all_documents