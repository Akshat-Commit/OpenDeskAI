import json
import hashlib
from loguru import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from opendesk.config import GEMINI_API_KEY, GITHUB_API_KEY

# In-process criteria cache: avoids re-calling Gemini for the same command on retry.
# Key: MD5 of the lowercased command. Value: criteria string.
_criteria_cache: dict = {}

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
        Pre-generates a strict grading rubric based on the user's command.
        Result is cached in-process by command hash so retries are free.
        """
        cache_key = hashlib.md5(command.strip().lower().encode(), usedforsecurity=False).hexdigest()
        if cache_key in _criteria_cache:
            logger.info("JUDGE CACHE HIT: Reusing criteria (no LLM call needed).")
            return _criteria_cache[cache_key]

        prompt = f"""
        You are the JUDGE for an AI Assistant called OpenDesk that controls a Windows PC.
        The user has given the following command: "{command}"
        
        IMPORTANT CONTEXT — OpenDesk tool names (use EXACTLY these names):
        - "Share", "send", or "give me" a file = share_file tool. Do NOT expect email or cloud uploads.
        - "WhatsApp" tasks = send_whatsapp_file (for files) or send_whatsapp_message (for text).
        - "Find the most recent/latest file" = find_latest_file tool (NOT find_user_file — that tool does NOT exist).
        - "Find a file by name" = find_file_location tool (NOT find_user_file — that tool does NOT exist).
        - "Find files by type + time" = find_files_by_filter tool.
        - "Summarise" or "read" a file = read_and_summarize tool (NOT read_document — that tool does NOT exist).
        - "Open" a file or app = open_path or open_application tool.
        - "Take a screenshot" = take_screenshot tool.
        - "Open browser/YouTube/Google" = search_web tool with open_in_browser=True.
        
        MULTI-STEP TASK LOGIC:
        - If the command is "find the most recent file, open it, take a screenshot, share it":
          SUCCESS = find_latest_file was called AND take_screenshot was called AND share_file was called.
          You do NOT need read_and_summarize — the user asked to open and screenshot, not summarize.
        - Judge the task by what the user ACTUALLY asked for, not by a fixed list of tools.
        
        Before the agent executes this, define STRICT, specific criteria for success.
        What tools MUST be used? What exact outcome is expected?
        Keep it concise (2-3 sentences max).
        """
        criteria = None
        try:
            if not self.llm:
                raise ValueError("Primary LLM (Gemini) not configured")
            response = await self.llm.ainvoke(prompt)
            criteria = response.content.strip()
        except Exception as e:
            logger.debug(f'Primary gen failed: {e}')
            if self.fallback_llm:
                try:
                    res = await self.fallback_llm.ainvoke(prompt)
                    criteria = res.content.strip()
                except Exception as fallback_e:
                    logger.debug(f'Fallback gen failed: {fallback_e}')

        if not criteria:
            criteria = "Standard strict criteria: The agent must use appropriate tools and complete the user's request without hallucinating."

        _criteria_cache[cache_key] = criteria
        return criteria

    def _rule_based_fast_approve(self, command: str, tool_logs: list) -> dict | None:
        """
        Rule-based fast-approve: if tool_logs clearly show success, skip LLM judge entirely.
        Returns a verdict dict on confident approval, or None to fall through to LLM judge.
        Saves Gemini/GitHub quota on straightforward completions.
        """
        if not tool_logs:
            return None

        msg = command.lower()
        executed = {log["name"] for log in tool_logs}
        outputs = " ".join(str(log.get("output", "")) for log in tool_logs).lower()

        # Require at least one tool ran without error
        any_error = any(str(log.get("output", "")).strip().lower().startswith("error") for log in tool_logs)
        success_signal = "successfully" in outputs or "success" in outputs or "saved at" in outputs or "shared successfully" in outputs

        if any_error or not success_signal:
            return None  # Can't fast-approve if there are errors or no success markers

        # Rule 1: file-share tasks — share_file was called and succeeded
        if any(kw in msg for kw in ["share", "send me", "give me"]) and "whatsapp" not in msg:
            if "share_file" in executed and "shared successfully" in outputs:
                logger.info("JUDGE FAST-APPROVE: share_file succeeded — skipping LLM judge.")
                return {"hallucinated": False, "tool_called": True, "task_completed": True,
                        "correction": "", "confidence": 9}

        # Rule 2: WhatsApp send — send_whatsapp_* was called and succeeded
        if "whatsapp" in msg:
            if ("send_whatsapp_file" in executed or "send_whatsapp_message" in executed) and success_signal:
                logger.info("JUDGE FAST-APPROVE: WhatsApp send succeeded — skipping LLM judge.")
                return {"hallucinated": False, "tool_called": True, "task_completed": True,
                        "correction": "", "confidence": 9}

        # Rule 3: screenshot + share — both take_screenshot and share_file succeeded
        if "screenshot" in msg or ("open" in msg and "share" in msg):
            if "take_screenshot" in executed and "share_file" in executed and "shared successfully" in outputs:
                logger.info("JUDGE FAST-APPROVE: screenshot + share succeeded — skipping LLM judge.")
                return {"hallucinated": False, "tool_called": True, "task_completed": True,
                        "correction": "", "confidence": 9}

        # Rule 4: simple system info / volume / battery — single tool, no error
        simple_tools = {"get_current_volume", "get_battery_level", "get_current_time",
                        "set_volume", "mute_volume", "unmute_volume", "get_system_info"}
        if executed & simple_tools and not any_error:
            logger.info("JUDGE FAST-APPROVE: Simple system tool succeeded — skipping LLM judge.")
            return {"hallucinated": False, "tool_called": True, "task_completed": True,
                    "correction": "", "confidence": 8}

        return None  # No fast-approve rule matched — use LLM judge


    async def evaluate_response(self, command: str, result: str, tool_logs: list, criteria: str = "", image_b64: str = None):
        """
        Evaluate if the Executor Agent successfully completed the task.
        Tries rule-based fast-approve first (zero LLM cost).
        Falls back to Gemini, then GitHub GPT-4o-mini if needed.
        """
        # ── FAST-APPROVE: rule-based check (no LLM cost) ──
        fast_verdict = self._rule_based_fast_approve(command, tool_logs)
        if fast_verdict is not None:
            return fast_verdict

        content_list = [
            {"type": "text", "text": f"""
        You are the JUDGE for an AI Assistant that controls a Windows laptop.
        Analyze the following result and decide if it was successful or a failure/hallucination.

        USER COMMAND: "{command}"
        PRE-COMPUTED STRICT CRITERIA: {criteria}
        
        AGENT RESPONSE: "{result}"
        TOOL LOGS: {json.dumps([{**log, "output": str(log.get("output", ""))[:200] + "..." if len(str(log.get("output", ""))) > 200 else log.get("output", "")} for log in tool_logs])}

        STRICT RULES:
        1. "hallucinated": true if the agent claimed success but NO relevant tool was called, or if it made up results.
        2. "tool_called": true if any relevant tool was actually executed.
        3. "task_completed": true if the final result satisfies the PRE-COMPUTED STRICT CRITERIA.
        4. "correction": If failure, explain EXACTLY what happened.
        
        CRITICAL OPENDESK CONTEXT — exact tool names this agent uses:
        - "Share", "send", or "give me" a file = SUCCESS means share_file tool was called. Do NOT expect email, Google Drive, OneDrive or any cloud upload.
        - "WhatsApp" commands = SUCCESS means send_whatsapp_file or send_whatsapp_message was called. Do NOT expect share_file for WhatsApp tasks!
        - "Find the most recent/latest file" = find_latest_file tool must be called (NOT find_user_file — that does NOT exist).
        - "Find a file by name" = find_file_location tool must be called (NOT find_user_file — that does NOT exist).
        - "Find files by type + time period" = find_files_by_filter tool must be called. list_directory is NOT acceptable.
        - "Summarise"/"read" a document = read_and_summarize tool must return content (NOT read_document — that does NOT exist).
        - "Open" an app, file or folder = open_path or open_application must be called.
        - "Take a screenshot" = take_screenshot tool must be called.
        - File sharing COMPLETE if share_file was called and returned success message.
        
        MULTI-STEP TASK SUCCESS RULE:
        - For commands like "find most recent file, open it, take screenshot, share it":
          SUCCESS = find_latest_file called + take_screenshot called + share_file called.
          Do NOT require read_and_summarize — the user did NOT ask for a summary.
        - Evaluate tasks strictly on what the user ASKED for, not on assumptions about extra tools.


        EVALUATION RULES:
        - Be lenient with formatting differences
        - Focus on RESULT not exact format
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
                    
        # All retries exhausted due to rate limits — Fallback to Heuristic (Fix 3)
        logger.warning("All Judge LLMs failed. Using simple heuristic fallback.")
        tool_outputs = " ".join(str(log.get("output", "")).lower() for log in tool_logs)
        task_completed = "error" not in tool_outputs and "failed" not in tool_outputs
        
        return {
            "hallucinated": False,
            "tool_called": True,
            "task_completed": task_completed,
            "confidence": 5,
            "correction": "Judge used heuristic fallback because APIs were unavailable."
        }

judge_agent = JudgeAgent()
