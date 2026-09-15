# AI RAG HR Policy Assistant

This project implements a Retrieval-Augmented Generation (RAG) assistant for company HR Policies.

## Week 5 Updates: Evals & Error Analysis

Based on the [Week 5 Error Analysis Report](Week5_Error_Analysis_Report.md), the following critical improvements have been made to the system:

1. **Fixed "Retriever Complete Miss"**: Upgraded the retriever in `inspect_rag.py` and the main `app.py` UI to retrieve the top 5 (`k=5`) documents instead of 3. This significantly improves recall.
2. **Fixed "Verbosity / Poor Formatting"**: Added strict conciseness constraints to the LLM system prompt to prevent hallucination and long-winded answers.
3. **Web UI Added**: Created a beautiful, dark-mode Vanilla web interface to interact with the RAG assistant easily instead of relying on CLI scripts.

## How to Run the Web UI

To chat with the HR Assistant using the new web interface:

1. Start the backend server:
   ```bash
   venv\Scripts\python.exe app.py
   ```
2. Open the `index.html` file in your browser to access the chat UI!
