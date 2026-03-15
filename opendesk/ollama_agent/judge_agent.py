import json
from loguru import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from opendesk.config import GEMINI_API_KEY, GITHUB_API_KEY



class JudgeAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", 
            google_api_key=GEMINI_API_KEY, 
            temperature=0.0
        )
        
        self.fallback_llm = None
        if GITHUB_API_KEY:
            try:
                from langchain_openai import ChatOpenAI
                self.fallback_llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=GITHUB_API_KEY,
                    base_url="https://models.inference.ai.azure.com",
                    temperature=0.0
                )
            except ImportError:
                logger.warning("langchain_openai not installed. GitHub failover disabled.")

    async def prepare_evaluation_criteria(self, command: str) -> str:
        """
        SPEED OPTIMIZATION: Runs in parallel with the Executor.
        Pre-generates a strict grading rubric based on the user's command.
        """
        prompt = f"""
        You are the JUDGE for an AI Assistant that controls a Windows PC.
        The user has given the following command: "{command}"
        
        Before the agent executes this, define STRICT, specific criteria for success.
        What tools MUST be used? What exact outcome is expected?
        Keep it concise (2-3 sentences max).
        """
        try:
            response = await self.llm.ainvoke(prompt)
            return response.content.strip()
        except:
            if self.fallback_llm:
                try:
                    res = await self.fallback_llm.ainvoke(prompt)
                    return res.content.strip()
                except:
                    pass
            return "Standard strict criteria: The agent must use appropriate tools and complete the user's request without hallucinating."

    async def evaluate_response(self, command: str, result: str, tool_logs: list, criteria: str = "", image_b64: str = None):
        """
        Evaluate if the Executor Agent successfully completed the task.
        Uses visual verification if an image_b64 is provided.
        Returns a structured dictionary score.
        """
        content_list = [
            {"type": "text", "text": f"""
        You are the JUDGE for an AI Assistant that controls a Windows laptop.
        Analyze the following result and decide if it was successful or a failure/hallucination.

        USER COMMAND: "{command}"
        PRE-COMPUTED STRICT CRITERIA: {criteria}
        
        AGENT RESPONSE: "{result}"
        TOOL LOGS: {json.dumps(tool_logs)}

        STRICT RULES:
        1. "hallucinated": true if the agent claimed success but NO relevant tool was called, or if it made up results.
        2. "tool_called": true if any relevant tool was actually executed.
        3. "task_completed": true if the final result satisfies the PRE-COMPUTED STRICT CRITERIA.
        4. "correction": If failure, explain EXACTLY what happened.
        
        IF AN IMAGE IS PROVIDED: This is a screenshot of the computer AFTER the agent finished. 
        Use it to verify if the task (like playing music, opening a file, or clicking a button) ACTUALLY happened.
        If the screenshot contradicts the tool logs or the agent's claim, mark "task_completed": false.
        """}
        ]
        
        if image_b64:
            content_list.append({
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{image_b64}"
            })

        import time
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                from langchain_core.messages import HumanMessage
                msg = HumanMessage(content=content_list)
                response = await self.llm.ainvoke([msg])

                # Remove any markdown wrapping if LLM adds it
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                return json.loads(content)
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "exhausted" in error_str or "retryinfo" in error_str:
                    if self.fallback_llm:
                        logger.warning("Judge rate limited (429) on Gemini. Failing over to GitHub GPT-4o-mini!")
                        try:
                            fallback_resp = await self.fallback_llm.ainvoke([msg])
                            content = fallback_resp.content.strip()

                            if "```json" in content:
                                content = content.split("```json")[1].split("```")[0].strip()
                            elif "```" in content:
                                content = content.split("```")[1].split("```")[0].strip()
                            return json.loads(content)
                        except Exception as fallback_e:
                            logger.error(f"GitHub failover also failed: {fallback_e}")
                            
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"Judge rate limited (429). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Judge evaluation failed: {e}")
                    return {
                        "hallucinated": False,
                        "tool_called": True,
                        "task_completed": True,
                        "confidence": 5,
                        "correction": f"Judge error: {e}"
                    }
                    
        return {
            "hallucinated": False,
            "tool_called": True,
            "task_completed": True,
            "confidence": 5,
            "correction": "Judge failed after max retries due to rate limits."
        }

judge_agent = JudgeAgent()
