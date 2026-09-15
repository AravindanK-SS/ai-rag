import json
import os
import pytest
from langchain_chroma import Chroma
from src.embedding import get_embedding_model
from src.retrieval import search
from src.llm import get_llm

# Load the 20 test cases
with open("results/test_cases_week6.json", "r") as f:
    test_cases = json.load(f)

retrieval_cases = [tc for tc in test_cases if tc["type"] == "retrieval"]
generation_cases = [tc for tc in test_cases if tc["type"] == "generation"]

@pytest.fixture(scope="module")
def vector_db():
    embedding = get_embedding_model()
    return Chroma(
        persist_directory="vectorstore/current",
        embedding_function=embedding,
    )

@pytest.fixture(scope="module")
def llm():
    return get_llm()

@pytest.mark.parametrize("test_case", retrieval_cases, ids=[f"Q{tc['id']}" for tc in retrieval_cases])
def test_retrieval_accuracy(test_case, vector_db):
    """Assert that the expected document is retrieved within the top 5 results."""
    question = test_case["question"]
    expected_doc = test_case["expected_document"]
    
    docs = search(vector_db, question, k=5)
    
    # Extract source files from metadata
    retrieved_sources = [d.metadata.get("source_file", "") for d in docs]
    if not retrieved_sources or all(s == "" for s in retrieved_sources):
        retrieved_sources = [os.path.basename(d.metadata.get("source", "")) for d in docs]
        
    hit = any(expected_doc in src for src in retrieved_sources)
    assert hit, f"Expected {expected_doc} to be in retrieved sources: {retrieved_sources}"

@pytest.mark.parametrize("test_case", generation_cases, ids=[f"Q{tc['id']}" for tc in generation_cases])
def test_llm_generation_fallback(test_case, vector_db, llm):
    """Assert that the LLM falls back correctly when there is no matching context."""
    question = test_case["question"]
    
    docs = search(vector_db, question, k=5)
    context = "\n\n".join(d.page_content for d in docs)
    
    prompt = f"""
You are an HR Policy Assistant.

Answer ONLY using the context below. Keep your answers concise and directly to the point.

If the answer is not present, reply:

'I cannot answer this because the uploaded documents do not contain the required information.'

Context:
{context}

Question:
{question}
"""
    response = llm.invoke(prompt)
    answer = response.content.strip()
    
    expected_fallback_phrase = "I cannot answer this because the uploaded documents do not contain the required information."
    
    if test_case.get("expected_llm_fallback"):
        # We assert that the LLM correctly refuses to hallucinate
        assert expected_fallback_phrase in answer, f"LLM was expected to fallback but answered: {answer}"
