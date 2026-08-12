from langchain_chroma import Chroma

from src.embedding import get_embedding_model
from src.retrieval import search
from src.llm import get_llm

embedding = get_embedding_model()

store = input("Choose vector store (current/structure): ").strip().lower()

vectorstore = Chroma(
    persist_directory=f"vectorstore/{store}",
    embedding_function=embedding
)

question = input("Ask a question: ")

docs = search(vectorstore, question, k=3)

context = "\n\n".join(
    doc.page_content
    for doc in docs
)

llm = get_llm()

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

response = llm.invoke(prompt)

print("\n" + "=" * 80)
print("ANSWER\n")
print(response.content)

print("\nSources\n")

for i, doc in enumerate(docs, 1):

    print(
        f"{i}. "
        f"{doc.metadata.get('source_file')} "
        f"(Page {doc.metadata.get('page')}) "
        f"[{doc.metadata.get('chunk_id')}]"
    )