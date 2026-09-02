# Week 5 Error Analysis: Reading Traces Like a Pro

This week, I stopped trying to fix bugs as I noticed them and instead took a systematic approach. I ran a batch of 20 random HR policy queries through my RAG assistant, read the full trace (query, retrieved chunks, and the final LLM answer) for every single one, and wrote down honest notes on why it failed. 

Here is the raw analysis of those 20 traces, followed by the problem taxonomy and my plan for next week.

---

## Part 1: Raw Trace Notes (20 Samples)

**Trace 1: "What is the policy for annual leave?"**
* **What happened:** The LLM gave a super generic dictionary definition of annual leave instead of citing our actual company policy.
* **My note:** Classic hallucination. The retriever fetched chunks about "sick leave" instead of "annual leave", so the LLM just made up an answer using its pre-trained knowledge because the prompt didn't tell it to stop.

**Trace 2: "What are the core work hours?"**
* **What happened:** The LLM confidently stated "I cannot answer this."
* **My note:** The retriever totally missed the "Attendance HR Policies" PDF. Complete retriever miss. 

**Trace 3: "Who is eligible for internet reimbursement?"**
* **What happened:** The LLM said all full-time employees are eligible. But it missed the part where probationary employees are excluded.
* **My note:** The chunk it retrieved literally cut off mid-sentence right before the word "except". Chunking truncation issue.

**Trace 4: "How many vacation days do faculty members get?"**
* **What happened:** It gave the vacation allowance for administrative staff, not faculty.
* **My note:** The retriever pulled the right document, but the staff section ranked higher than the faculty section, so it only retrieved the wrong half of the policy.

**Trace 5: "Can I take educational leave?"**
* **What happened:** It answered correctly, but then rambled on for three paragraphs about unpaid leave and sabbatical policies.
* **My note:** The answer is right, but the formatting is terrible. The LLM is way too verbose. Needs a constraint in the system prompt.

**Trace 6: "What happens if I am late to work 3 times?"**
* **What happened:** The LLM said you get fired immediately. 
* **My note:** Yikes. The actual policy says you get a verbal warning. The retriever fetched the "Termination" chunk because the word "fired" might be semantically close to "late" in the vector space? Bad retrieval.

**Trace 7: "Is maternity leave paid?"**
* **What happened:** It said "Maternity leave is paid for 12 weeks."
* **My note:** This is actually true in the document, but it didn't cite which document it found it in. Not a failure, but a missing feature (citations).

**Trace 8: "How do I apply for a promotion?"**
* **What happened:** LLM responded with "I cannot answer this because the uploaded documents do not contain the required information."
* **My note:** This is actually the correct behavior! We don't have a promotion policy document loaded. Good job LLM.

**Trace 9: "What is the dress code for casual Fridays?"**
* **What happened:** It said we don't have casual Fridays.
* **My note:** We DO have casual Fridays. The retriever just completely missed the single paragraph in the 159-page Service Rules PDF that mentions it. Another retriever complete miss.

**Trace 10: "Can I bring my dog to the office?"**
* **What happened:** It started hallucinating a fake pet policy saying dogs under 20lbs are allowed.
* **My note:** We have no pet policy. Because the retriever found nothing, the LLM just tried to be helpful and invented a policy. Huge hallucination problem.

**Trace 11: "Explain the bereavement leave policy."**
* **What happened:** The LLM gave a giant, unformatted wall of text directly copied from the PDF.
* **My note:** It’s accurate, but impossible to read. Verbosity/formatting issue.

**Trace 12: "Are contractors eligible for health insurance?"**
* **What happened:** It said "Yes, all employees get health insurance."
* **My note:** Contractors aren't employees. The LLM didn't understand the semantic difference between "contractor" and "employee" based on the retrieved context.

**Trace 13: "What is the penalty for breaching confidentiality?"**
* **What happened:** The LLM answered with the penalty for breaching IT security.
* **My note:** Retriever fetched the wrong policy section because the words "breach" and "penalty" overpowered the word "confidentiality" in the vector search.

**Trace 14: "How much is the travel allowance?"**
* **What happened:** "The travel allowance is $50 per day for domestic."
* **My note:** It missed the international allowance because the chunk cut off right at the word "International". Another chunk truncation issue.

**Trace 15: "Who do I contact for payroll issues?"**
* **What happened:** "Please contact HR."
* **My note:** The document specifically says to contact `payroll@company.com`. The LLM generalized the answer.

**Trace 16: "What are the rules for remote work?"**
* **What happened:** It answered with the rules from the 2019 policy, completely ignoring the 2023 remote work addendum.
* **My note:** Retriever pulled the old document because they had similar keywords, and the LLM didn't know which one superseded the other.

**Trace 17: "Can I roll over my unused sick days?"**
* **What happened:** The LLM said "I cannot answer this."
* **My note:** The policy exists, but it's called "Medical Leave Carry-Forward". The vector search completely failed to match "sick days" to "medical leave". Retriever miss due to vocabulary mismatch.

**Trace 18: "What is the maximum consecutive days I can take off?"**
* **What happened:** It hallucinated a limit of 14 days.
* **My note:** The context retrieved was irrelevant, so the LLM made up a number. Hallucination.

**Trace 19: "Does the company match 401k?"**
* **What happened:** It explained what a 401k is, but didn't answer the question about company matching.
* **My note:** Verbose and unhelpful. It skirted the question because the chunk only had background info on retirement plans.

**Trace 20: "How do I report harassment?"**
* **What happened:** It gave the correct steps but missed step 3 (Fill out form HR-104).
* **My note:** The retrieved chunk cut off right before step 3. Chunking truncation strikes again.

---

## Part 2: Problem Taxonomy & Ranking

After open-coding the 20 traces above, I noticed clear patterns. I grouped them into 4 named problem categories and ranked them based on how often they happened (Frequency) and how badly they hurt the user experience (Severity).

| Rank | Problem Name | Frequency | Severity | Description |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Retriever Complete Miss** | High (7/20) | Critical | The vector database fails to fetch the right document at all. Often caused by vocabulary mismatch (e.g., "sick days" vs "medical leave"). If the context is wrong, the LLM is doomed from the start. |
| **2** | **Knowledge Leakage (Hallucination)** | Medium (5/20) | Critical | When the retriever fetches bad context, the LLM ignores the context entirely and makes up fake company policies to be helpful. This is incredibly dangerous for HR compliance. |
| **3** | **Chunk Truncation (Cut-offs)** | Medium (4/20) | High | The text chunk cuts off mid-sentence, causing the LLM to miss crucial caveats, exceptions, or list items. |
| **4** | **Verbosity / Formatting** | Low (4/20) | Low | The LLM answers correctly, but it's a giant wall of text or includes irrelevant extra info. Annoying, but not functionally broken. |

---

## Part 3: The Next Fix Target

**Chosen Target:** Retriever Complete Miss
**Why?** This is the highest-ranked problem. It is the root cause of almost all the other errors. If the retriever fails to get the right document, the LLM will either say "I don't know" or worse, hallucinate a fake policy. No amount of prompt engineering can fix a bad retrieval.

**My Prediction for Next Week:**
I predict that if I increase the retrieval threshold (from `k=3` to `k=5`) and add a basic Keyword Search fallback (to solve the vocabulary mismatch issues like "sick days"), the retriever will successfully fetch the correct document 50% more often. This should proportionally drop the "I cannot answer this" error rate in my next batch of traces.
