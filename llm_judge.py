import json
import sys
from pydantic import BaseModel, Field
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.embedding import get_embedding_model
from src.retrieval import search
from src.llm import get_llm

# Ensure proper encoding
sys.stdout.reconfigure(encoding='utf-8')

# Define the structured output schema
class EvaluationScore(BaseModel):
    faithfulness: int = Field(description="Score from 1 to 5 indicating how faithful the answer is to the provided context.")
    relevance: int = Field(description="Score from 1 to 5 indicating how relevant the answer is to the question.")
    reasoning: str = Field(description="A brief explanation for the given scores.")

def run_evaluation():
    # Initialize components
    embedding = get_embedding_model()
    llm = get_llm()
    vectorstore = Chroma(
        persist_directory="vectorstore/structure",
        embedding_function=embedding,
    )
    
    # Setup Output Parser
    parser = JsonOutputParser(pydantic_object=EvaluationScore)
    
    # Load Questions
    with open("results/eval_questions.json", "r") as f:
        questions = json.load(f)
        
    judge_prompt = PromptTemplate(
        template="""You are an impartial judge evaluating a RAG (Retrieval-Augmented Generation) system.
You will be provided with a Question, the Retrieved Context, and the Generated Answer.

Your task is to evaluate the Generated Answer on two metrics:
1. Faithfulness (1-5): Is the answer entirely based on the provided context? (1 = Completely Hallucinated, 5 = Entirely Faithful)
2. Relevance (1-5): Does the answer directly address the question? (1 = Irrelevant/Off-topic, 5 = Directly answers the question)

Question: {question}
Context: {context}
Generated Answer: {answer}

{format_instructions}
""",
        input_variables=["question", "context", "answer"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    judge_chain = judge_prompt | llm | parser

    total_faithfulness = 0
    total_relevance = 0
    evaluated_count = 0

    print("=" * 60)
    print("STARTING LLM-AS-A-JUDGE EVALUATION")
    print("=" * 60)

    for q in questions:
        question = q["question"]
        
        # 1. Retrieve Context
        try:
            docs = search(vectorstore, question, k=5)
            context = "\n\n".join(d.page_content for d in docs)
        except Exception as e:
            print(f"Error retrieving for '{question}': {e}")
            continue

        # 2. Generate Answer (Standard RAG)
        rag_prompt = f"""
You are an HR Policy Assistant.
Answer ONLY using the context below. Keep your answers concise and directly to the point.
If the answer is not present, reply:
'I cannot answer this because the uploaded documents do not contain the required information.'

Context:
{context}

Question:
{question}
"""
        try:
            response = llm.invoke(rag_prompt)
            answer = response.content
        except Exception as e:
            print(f"Error generating answer for '{question}': {e}")
            continue
            
        # 3. Judge the Output
        try:
            eval_result = judge_chain.invoke({
                "question": question,
                "context": context,
                "answer": answer
            })
            
            f_score = eval_result.get("faithfulness", 0)
            r_score = eval_result.get("relevance", 0)
            reasoning = eval_result.get("reasoning", "No reasoning provided.")
            
            total_faithfulness += f_score
            total_relevance += r_score
            evaluated_count += 1
            
            print(f"\nQ: {question}")
            print(f"Faithfulness: {f_score}/5 | Relevance: {r_score}/5")
            print(f"Reasoning: {reasoning}")
            print("-" * 60)
            
        except Exception as e:
            print(f"Error parsing judge output for '{question}': {e}")
            print("-" * 60)

    if evaluated_count > 0:
        avg_f = total_faithfulness / evaluated_count
        avg_r = total_relevance / evaluated_count
        print("=" * 60)
        print("FINAL RESULTS")
        print(f"Average Faithfulness: {avg_f:.2f} / 5.0")
        print(f"Average Relevance:    {avg_r:.2f} / 5.0")
        print("=" * 60)
    else:
        print("No questions were evaluated.")

if __name__ == "__main__":
    run_evaluation()
