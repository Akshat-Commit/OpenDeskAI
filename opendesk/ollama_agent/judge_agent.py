import json
from loguru import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from opendesk.config import GEMINI_API_KEY, GITHUB_API_KEY



class JudgeAgent:
    def __init__(self):
        self.llm = None
        if GEMINI_API_KEY:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", 
                google_api_key=GEMINI_API_KEY, 
                temperature=0.0
            )
        else:
            logger.warning("GEMINI_API_KEY missing. Judge Agent primary LLM disabled.")
        
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
        You are the JUDGE for an AI Assistant called OpenDesk that controls a Windows PC.
        The user has given the following command: "{command}"
        
        IMPORTANT CONTEXT — OpenDesk capabilities:
        - "Share", "send", or "give me" a file = the agent sends it as a Telegram attachment using the share_file tool. It does NOT use email or cloud storage.
        - "WhatsApp" tasks = if user asks to send via WhatsApp, the agent MUST use send_whatsapp_file or send_whatsapp_message.
        - "Find" a file = the agent uses find_user_file tool to search the local PC.
        - "Summarise" or "read" a file = the agent uses read_document tool to extract text.
        - "Open" an app = the agent uses app_launcher tool.
        - File sharing SUCCESS (Telegram) means: share_file tool was called.
        - WhatsApp SUCCESS means: send_whatsapp_file or send_whatsapp_message tool was called.
        
        Before the agent executes this, define STRICT, specific criteria for success.
        What tools MUST be used? What exact outcome is expected?
        Keep it concise (2-3 sentences max).
        """
        try:
            if not self.llm:
                raise ValueError("Primary LLM (Gemini) not configured")
            response = await self.llm.ainvoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.debug(f'Primary gen failed: {e}')
            if self.fallback_llm:
                try:
                    res = await self.fallback_llm.ainvoke(prompt)
                    return res.content.strip()
                except Exception as fallback_e:
                    logger.debug(f'Fallback gen failed: {fallback_e}')
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
        
        CRITICAL OPENDESK CONTEXT — how this agent works:
        - "Share", "send", or "give me" a file (Normal) = SUCCESS means share_file tool was called and sent via Telegram. Do NOT expect email, Google Drive, OneDrive or any cloud upload.
        - "WhatsApp" commands = SUCCESS means send_whatsapp_file or send_whatsapp_message was called and returned a success message. Do NOT expect Telegram file sending for WhatsApp tasks!
        - "Find" a file = find_user_file tool must be called.
        - "Summarise"/"read" a document = read_document tool must return content.
        - "Open" an app = app_launcher must be called.
        - File sharing is COMPLETE if share_file OR send_whatsapp_file was called and returned success.

        EVALUATION RULES:
        - Be lenient with formatting differences
        - 2+2 and 2 + 2 are equivalent
        - Focus on RESULT not exact format
        - If calculator shows correct answer task is COMPLETE regardless of how input was typed
        - Never fail task for minor formatting
        
        IF AN IMAGE IS PROVIDED: This is a screenshot of the computer AFTER the agent finished. 
        Use it to verify if the task (like playing music, opening a file, or clicking a button) ACTUALLY happened.
        If the screenshot contradicts the tool logs or the agent's claim, mark "task_completed": false.
        
        OUTPUT FORMAT: You MUST return ONLY a valid JSON object with the exact keys:
        "hallucinated" (boolean), "tool_called" (boolean), "task_completed" (boolean), "correction" (string), "confidence" (integer 1-10).
        DO NOT include any markdown code blocks, backticks, or other text outside the JSON object.
        """}
        ]
        
        if image_b64:
            content_list.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
            })

        import time
        max_retries = 3
        
        def extract_json(text: str) -> dict:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Fallback to finding the first { and last }
                start = text.find('{')
                end = text.rfind('}')
                if start != -1 and end != -1:
                    return json.loads(text[start:end+1])
                raise
        
        for attempt in range(max_retries):
            try:
                from langchain_core.messages import HumanMessage
                msg = HumanMessage(content=content_list)
                if not self.llm:
                    raise ValueError("Primary LLM (Gemini) not configured")
                response = await self.llm.ainvoke([msg])
                return extract_json(response.content)
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "exhausted" in error_str or "retryinfo" in error_str:
                    if self.fallback_llm:
                        logger.warning("Judge rate limited (429) on Gemini. Failing over to GitHub GPT-4o-mini!")
                        try:
                            fallback_resp = await self.fallback_llm.ainvoke([msg])
                            try:
                                return extract_json(fallback_resp.content)
                            except Exception as json_err:
                                logger.error(f"GitHub failover returned invalid JSON: {fallback_resp.content}")
                                raise json_err
                        except Exception as fallback_e:
                            logger.error(f"GitHub failover failed: {fallback_e}")
                            
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"Judge rate limited (429). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    # Check if this is a JSON parse error — fail closed
                    if isinstance(e, (json.JSONDecodeError, ValueError)):
                        logger.error(f"Judge returned malformed JSON (fail-closed): {e}")
                        return {
                            "hallucinated": True,
                            "tool_called": False,
                            "task_completed": False,
                            "confidence": 1,
                            "correction": f"Judge returned unparseable response: {e}"
                        }
                    logger.error(f"Judge evaluation failed: {e}")
                    return {
                        "hallucinated": False,
                        "tool_called": True,
                        "task_completed": False,
                        "confidence": 3,
                        "correction": f"Judge error (fail-closed): {e}"
                    }
                    
        # All retries exhausted due to rate limits — fail closed
        return {
            "hallucinated": False,
            "tool_called": True,
            "task_completed": False,
            "confidence": 2,
            "correction": "Judge failed after max retries due to rate limits. Treating as unverified."
        }

judge_agent = JudgeAgent()
