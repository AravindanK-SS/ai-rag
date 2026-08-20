import json

from langchain_chroma import Chroma

from src.embedding import get_embedding_model
from src.retrieval import search

embedding = get_embedding_model()

with open("results/questions.json", "r") as f:
    questions = json.load(f)

stores = {
    "Current": Chroma(
        persist_directory="vectorstore/current",
        embedding_function=embedding,
    ),
    "Structure": Chroma(
        persist_directory="vectorstore/structure",
        embedding_function=embedding,
    ),
}

print("-" * 100)
print(f"{'Question':40} {'Current':10} {'Structure':10}")
print("-" * 100)

for q in questions:

    results = {}

    for name, db in stores.items():

        docs = search(db, q["question"], k=5)

        found = any(
            q["expected_document"] in d.metadata.get("source", "")
            for d in docs
        )

        results[name] = "PASS" if found else "FAIL"

    print(
        f"{q['question'][:40]:40} "
        f"{results['Current']:10} "
        f"{results['Structure']:10}"
    )