import time
from typing import List, Dict, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from src.tools import TOOLS
from src.llm import get_llm

class BudgetExceededException(Exception):
    pass

class HRAgent:
    def __init__(self, max_iterations=5, max_tokens=2000, max_cost=0.05, timeout_seconds=15.0):
        self.llm = get_llm().bind_tools(TOOLS)
        self.summarizer_llm = get_llm()
        self.tools_map = {t.name: t for t in TOOLS}
        
        # Budgets
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.max_cost = max_cost
        self.timeout_seconds = timeout_seconds
        
        # State & Memory
        self.messages: List[Any] = []
        self.system_prompt = SystemMessage(content="You are an HR Assistant. You must use tools to look up employee details and compute answers.")
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.persistent_state: Dict[str, Any] = {}
        
    def _estimate_tokens(self, message_list: List[Any]) -> int:
        # A rough heuristic for local models since Ollama doesn't always return prompt_eval_count easily in stream
        return sum(len(str(m.content).split()) * 1.3 for m in message_list)

    def _simulate_cost(self, tokens: int) -> float:
        # Simulate cost at $0.01 per 1000 tokens
        return (tokens / 1000.0) * 0.01

    def _summarize_old_messages(self, messages_to_summarize: List[Any]) -> str:
        if not messages_to_summarize:
            return ""
        text = "\n".join([f"{type(m).__name__}: {m.content}" for m in messages_to_summarize])
        prompt = f"Summarize the following conversation history briefly, keeping key facts like employee jurisdiction or IDs:\n\n{text}"
        from langfuse.langchain import CallbackHandler
        langfuse_handler = CallbackHandler()
        res = self.summarizer_llm.invoke(prompt, config={"callbacks": [langfuse_handler]})
        return res.content

    def _manage_memory(self):
        # Sliding window + summarization
        # Keep system prompt + summary + last 4 messages
        if len(self.messages) > 6:
            messages_to_summarize = self.messages[:-4]
            self.messages = self.messages[-4:]
            summary = self._summarize_old_messages(messages_to_summarize)
            if summary:
                self.persistent_state["history_summary"] = summary

    def run(self, user_input: str) -> str:
        start_time = time.time()
        iterations = 0
        
        # Add context from persistent state if available
        context = ""
        if "history_summary" in self.persistent_state:
            context = f"\nPrevious Context: {self.persistent_state['history_summary']}\n"
            
        self.messages.append(HumanMessage(content=context + user_input))
        
        while True:
            # 1. Budget Checks
            if iterations >= self.max_iterations:
                raise BudgetExceededException("BUDGET EXCEEDED: Max Iterations reached.")
            if time.time() - start_time > self.timeout_seconds:
                raise BudgetExceededException("BUDGET EXCEEDED: Timeout reached.")
            if self.total_tokens_used >= self.max_tokens:
                raise BudgetExceededException("BUDGET EXCEEDED: Max Tokens reached.")
            if self.total_cost >= self.max_cost:
                raise BudgetExceededException("BUDGET EXCEEDED: Max Cost reached.")
                
            self._manage_memory()
            
            # Send to LLM
            full_prompt = [self.system_prompt] + self.messages
            
            # Token counting for THIS lap
            lap_tokens = int(self._estimate_tokens(full_prompt))
            self.total_tokens_used += lap_tokens
            self.total_cost += self._simulate_cost(lap_tokens)
            
            # Langfuse callback
            from langfuse.langchain import CallbackHandler
            langfuse_handler = CallbackHandler()
            
            response = self.llm.invoke(full_prompt, config={"callbacks": [langfuse_handler]})
            
            # Add output tokens to budgets
            output_tokens = int(self._estimate_tokens([response]))
            self.total_tokens_used += output_tokens
            self.total_cost += self._simulate_cost(output_tokens)
            
            self.messages.append(response)
            
            if not response.tool_calls:
                # LLM provided a final answer
                return response.content
                
            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_instance = self.tools_map.get(tool_name)
                
                if tool_instance:
                    try:
                        tool_result = tool_instance.invoke(tool_args)
                    except Exception as e:
                        tool_result = f"Error: {str(e)}"
                else:
                    tool_result = f"Tool {tool_name} not found."
                    
                self.messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))
                
            iterations += 1
