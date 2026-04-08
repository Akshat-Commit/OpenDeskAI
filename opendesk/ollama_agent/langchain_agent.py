from loguru import logger
from typing import List, Dict, Any, Tuple
import os
import re
import json
import time
import asyncio
from typing import Optional, Callable

from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_core.tools import StructuredTool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from opendesk.config import OLLAMA_HOST, OLLAMA_MODEL_NAME, OLLAMA_VISION_MODEL_NAME, GROQ_API_KEY_1, GROQ_API_KEY_2, GITHUB_API_KEY  # type: ignore
from opendesk.tools.registry import _TOOLS  # type: ignore
from opendesk.tools.schemas import TOOL_SCHEMAS

from opendesk.ollama_agent.judge_agent import judge_agent


# Dynamically wrap all existing OpenDesk tools into LangChain tools
lc_tools = []
for name, func in _TOOLS.items():
    # If a strict Pydantic schema is defined for this tool, use it.
    schema = TOOL_SCHEMAS.get(name)

    t = StructuredTool.from_function(
        func=func,
        name=name,
        description=func.__doc__ or f"Executes the {name} command.",
        args_schema=schema
    )
    lc_tools.append(t)

# Categorize Tools for Dynamic Loading
ADVANCED_TOOL_NAMES = ["create_word_doc", "create_excel_file", "create_powerpoint"]
basic_lc_tools = [t for t in lc_tools if t.name not in ADVANCED_TOOL_NAMES]
advanced_lc_tools = [t for t in lc_tools if t.name in ADVANCED_TOOL_NAMES]

# Speed Optimization: Tools that do not require Judge Agent verification
SIMPLE_TOOLS = [
    "set_volume", "mute_volume", "unmute_volume", "get_current_volume",
    "get_battery_level", "get_current_time", "get_system_info", 
    "open_application"
]


TOOL_CALLING_PROMPT = """You are OpenDesk, a professional AI assistant created by Akshat Jain to control a Windows PC.

CORE RULES:
1. TOOL CALLING: You have native tools. Call them directly using your internal tool-use capability. 
   - NEVER output tags like <function=...> or XML-style calls. 
   - NEVER explain your tool usage. Just call the tool.
2. PERSONA: Be professional, friendly, and helpful. 
    - If it's a completely new conversation, you may greet warmly. Otherwise, just converse naturally without saying "Hey! OpenDesk here!" every time.
    - Do NOT mention system stats (CPU/RAM) unless specifically asked.
    - ENCOURAGEMENT: After successfully fulfilling a specific task or answering a non-trivial query, append a varied, friendly follow-up question (e.g., "Is there anything else you want to ask?", "What's next?", "How else can I help?"). 
    - AVOID the encouragement suffix for simple greetings, introductions, or casual chit-chat. Keep those natural.
3. FILE OPERATIONS RULES:
   - When user asks where is a file: Use find_file_location tool
   - When user asks to share/send file: Use share_file tool. It automatically searches everywhere including OneDrive Japanese folders
   - When user asks to summarize file: Use read_and_summarize tool DIRECTLY. Do NOT use share_file first.
   - NEVER say file not found without trying file_indexer first!
   - File indexer has 19000+ files indexed. Always use it before saying not found
   - For banner1.png, document.pdf etc: Just call find_file_location tool. Do not manually search paths!
4. WHATSAPP RULES:
   - For text messages: Use `send_whatsapp_message` tool.
   - For file sharing via WhatsApp: Use `send_whatsapp_file` tool.
   - NEVER use `search_and_confirm_whatsapp_share` (DELETED).
   - NEVER use `share_file` for WhatsApp tasks.
   Example: 'Send hi to Aditya' -> send_whatsapp_message(contact_name='Aditya', message='hi')
5. CONFIRMATION GATE: For Gmail or other non-WhatsApp apps, call `request_confirmation` before sending. Stop and wait for user reply.
   - If command starts with [USER CONFIRMED] -> proceed.
6. MACROS: Tools like `play_spotify_music` and `send_whatsapp_message` are macro-based. 
   - Ensure the app is focused before calling.
   - If a macro fails, do NOT claim success. Describe what you saw on the screen.
7. ARCHITECTURE: Use native tools (Wait, Spotify, Volume) first. Use `open_app` for settings/apps. Use `take_screenshot` before clicking UI elements.
8. CONVERSATIONAL RECOVERY: If the user's intent is unclear, the file is not found, or you do not have a tool to fulfill the request, DO NOT pretend to execute a tool and DO NOT silently fail. Instead, act authentically as humans do. Ask 1 short, intelligent clarifying question to figure out exactly what the user wants.

DOCUMENT SUMMARIZATION RULES:

When user asks to summarize:

1. Use the read_and_summarize tool directly on the filename. DO NOT use share_file tool during summarization operations!

2. Read the content completely

3. Detect summary style from message:
   - short/brief = 3-4 lines
   - points/bullets = bullet list
   - detail/full = with headings
   - default = professional format

4. Format response like this:

   DEFAULT FORMAT:
   📄 *[Filename]*
   
   *📋 Overview*
   [2 line overview]
   
   *🔑 Key Points*
   • [point 1]
   • [point 2]
   • [point 3]
   
   *💡 Conclusion*
   [1 line conclusion]

   SHORT FORMAT:
   📄 *[Filename]*
   [3-4 lines summary]

   POINTS FORMAT:
   📄 *[Filename]*
   _[1-line brief overview]_
   
   🎯 *[Brief Topic 1]:* [point 1]
   📈 *[Brief Topic 2]:* [point 2]
   💡 *[Brief Topic 3]:* [point 3]

   DETAIL FORMAT:
   📄 *[Filename]*
   
   *📋 Introduction*
   [paragraph]
   
   *📌 Main Content*
   [detailed sections]
   
   *💡 Key Takeaways*
   • [points]
   
   *✅ Conclusion*
   [paragraph]

5. NEVER send raw file content
   Always send formatted summary only
   
6. Use Telegram Markdown formatting:
   *bold* for headings
   _italic_ for emphasis
   • for bullet points"""



def _check_ollama_available() -> bool:
    """Quick check if Ollama is reachable."""
    import requests
    try:
        resp = requests.get(OLLAMA_HOST, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def build_fallback_chain() -> list:
    """
    Builds the LLM fallback chain based on USER_MODE.
    
    - developer: Full 6-model chain (Groq → GitHub → Gemini → Mixtral)
    - local: Ollama only
    - cloud: Groq + optional Ollama fallback
    """
    import opendesk.config as cfg
    
    # Force reload config
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    mode = os.getenv("USER_MODE", "local").strip().lower()
    
    # Debug print
    logger.debug(f"Building chain for mode: {mode}")
    
    chain = []


    if mode == "developer":
        if getattr(cfg, "OPENDESK_ENV", "production") == "testing":
            # ── TESTING MODE (No Gemini per User Request) ──
            # 1. Groq Key 1 - llama-3.3-70b-versatile
            chain.append({"name": "Groq Llama 70B (Key 1)", "llm": ChatGroq(model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY_1, temperature=0.0)})
            
            # 2. Groq Key 2 - llama-3.3-70b-versatile
            chain.append({"name": "Groq Llama 70B (Key 2)", "llm": ChatGroq(model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY_2, temperature=0.0)})
            
            # 3. GitHub - gpt-4o-mini
            if GITHUB_API_KEY:
                try:
                    from langchain_openai import ChatOpenAI  # type: ignore
                    llm_gpt = ChatOpenAI(model="gpt-4o-mini", api_key=GITHUB_API_KEY, base_url="https://models.inference.ai.azure.com", temperature=0.0)
                    chain.append({"name": "GitHub GPT-4o-mini", "llm": llm_gpt})
                except ImportError:
                    logger.warning("langchain_openai not installed. GPT-4o-mini disabled.")
                    
            # 4. Local - Gemma fallback
            if _check_ollama_available():
                llm_gemma = ChatOllama(model="gemma3:12b", base_url=OLLAMA_HOST, temperature=0.0)
                chain.append({"name": "Local Gemma Fallback", "llm": llm_gemma})
        else:
            # ── PRODUCTION MODE (No Gemini per User Request) ──
            # 1. Groq Key 1 - llama-3.3-70b-versatile
            chain.append({"name": "Groq Llama 70B (Key 1)", "llm": ChatGroq(model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY_1, temperature=0.0)})
            
            # 2. Groq Key 2 - llama-3.3-70b-versatile
            chain.append({"name": "Groq Llama 70B (Key 2)", "llm": ChatGroq(model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY_2, temperature=0.0)})

            # 3. GitHub - gpt-4o-mini
            if GITHUB_API_KEY:
                try:
                    from langchain_openai import ChatOpenAI  # type: ignore
                    llm_gpt = ChatOpenAI(model="gpt-4o-mini", api_key=GITHUB_API_KEY, base_url="https://models.inference.ai.azure.com", temperature=0.0)
                    chain.append({"name": "GitHub GPT-4o-mini", "llm": llm_gpt})
                except ImportError:
                    logger.warning("langchain_openai not installed. GPT-4o-mini disabled.")

            # 4. Local - Gemma fallback
            if _check_ollama_available():
                llm_gemma = ChatOllama(model="gemma3:12b", base_url=OLLAMA_HOST, temperature=0.0)
                chain.append({"name": "Local Gemma Fallback", "llm": llm_gemma})

        # No logging here to keep terminal clean

    elif mode == "local":
        # ── Local: Ollama only ──
        llm_local = ChatOllama(model=OLLAMA_MODEL_NAME, base_url=OLLAMA_HOST, temperature=0.0)
        chain.append({"name": f"Ollama {OLLAMA_MODEL_NAME}", "llm": llm_local})
        logger.info(f"Local mode: Using Ollama {OLLAMA_MODEL_NAME}")

    elif mode == "cloud":
        # ── Cloud: Groq + optional Ollama fallback ──
        chain.append({"name": "Groq Llama 70B", "llm": ChatGroq(model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_API_KEY_1, temperature=0.0)})
        # Silent Ollama fallback if installed
        if _check_ollama_available():
            llm_local_backup = ChatOllama(model=OLLAMA_MODEL_NAME, base_url=OLLAMA_HOST, temperature=0.0)
            chain.append({"name": f"Local Fallback ({OLLAMA_MODEL_NAME})", "llm": llm_local_backup})
            logger.info("Cloud mode: Groq + local Ollama fallback ready.")
        else:
            logger.info("Cloud mode: Groq only (no Ollama detected).")

    return chain


# Build the chain at module load
fallback_chain = build_fallback_chain()

# Vision Model (Local Ollama for screenshots)
llm_vision = ChatOllama(model=OLLAMA_VISION_MODEL_NAME, base_url=OLLAMA_HOST, temperature=0.0)


from opendesk.utils.context_monitor import monitor_instance
import base64

def _encode_image(image_path: str) -> str:
    """Encodes an image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def _parse_hallucinated_tool_call(text: str):
    """Catches hallucinated tool calls from weaker models or alternative providers.
    E.g.: <function=share_file>{"filename": "ak.jpg", "search_dir": "Downloads"}
          ```json { "name": "share_file", ... } ```
          share_file(filename="ak.jpg")
    Returns (tool_name, tool_args_dict) or (None, None) if no match.
    """
    # Pattern 0: PRIORITY — Groq 400 failed_generation format (most common hallucination)
    # e.g. 'failed_generation': '<function=control_media>{"action": "mute"}'
    match = re.search(r'<function=(\w+)>\s*(\{[^}]+\})', text)
    if match:
        tool_name = match.group(1)
        try:
            # Clean up any escaped quotes from Python repr
            json_str = match.group(2).replace('\\"', '"').replace("\\'", "'")
            tool_args = json.loads(json_str)
            return tool_name, tool_args
        except json.JSONDecodeError:
            pass

    # Pattern 1: JSON Markdown Block
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            data = json.loads(match.group(1))
            name = data.get("name") or data.get("tool")
            args = data.get("arguments") or data.get("parameters") or {}
            if name:
                return name, args
        except json.JSONDecodeError:
            pass

    # Pattern 2: Python-style function call e.g., share_file(filename="ak.jpg")
    match = re.search(r'(\w+)\s*\((.*?)\)', text, re.DOTALL)
    if match:
        tool_name = match.group(1)
        args_str = match.group(2).strip()
        
        tool_args = {}
        if args_str:
            try:
                # Naive kwargs extraction: key="value" or key='value'
                kwargs = re.findall(r'(\w+)\s*=\s*(["\'])(.*?)\2', args_str)
                for k, _, v in kwargs:
                    tool_args[k] = v
                    
                if tool_args: # Only return if we actually found kwargs
                    return tool_name, tool_args
            except Exception as e:
                logger.debug(f"Kwargs extraction failed: {e}")


    # Pattern 3: XML style <function=tool_name>{"arg": "val"}</function> (backup)
    match = re.search(r'<function=([\w]+)>\s*(\{.*\})', text, re.DOTALL)
    if match:
        tool_name = match.group(1)
        try:
            json_str = match.group(2).replace('\\"', '"').replace("\\'", "'")
            tool_args = json.loads(json_str)
            return tool_name, tool_args
        except json.JSONDecodeError:
            pass
            
    # Pattern 4: Relaxed JSON matching
    match = re.search(r'\{\s*"name"\s*:\s*"([\w]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}', text, re.DOTALL)
    if match:
        tool_name = match.group(1)
        try:
            tool_args = json.loads(match.group(2))
            return tool_name, tool_args
        except json.JSONDecodeError:
            pass

    # Pattern 5: Action / Action Input text format
    action_match = re.search(r'Action:\s*(\w+)', text, re.IGNORECASE)
    input_match = re.search(r'Action Input:\s*(\{.*?\})', text, re.IGNORECASE | re.DOTALL)
    
    if action_match and input_match:
        tool_name = action_match.group(1)
        try:
            tool_args = json.loads(input_match.group(1))
            return tool_name, tool_args
        except json.JSONDecodeError:
            pass

    return None, None

def format_summary(
    content: str,
    style: str = "default"
) -> str:
    
    if style == "short":
        # 3-4 lines maximum
        # Key points only
        prompt = (
            f"Summarize in 3-4 lines only:\n"
            f"{content}"
        )
    
    elif style == "brief":
        # One paragraph
        prompt = (
            f"Write one paragraph summary:\n"
            f"{content}"
        )
    
    elif style == "points":
        # Bullet points
        prompt = (
            f"Summarize as bullet points:\n"
            f"{content}"
        )
    
    elif style == "detail":
        # Full detailed summary
        prompt = (
            f"Write detailed summary with "
            f"headings and subheadings:\n"
            f"{content}"
        )
    
    else:
        # Default professional summary
        prompt = (
            f"Write a professional summary "
            f"with these sections:\n"
            f"• Overview (2 lines)\n"
            f"• Key Points (3-5 bullets)\n"
            f"• Conclusion (1 line)\n\n"
            f"Content:\n{content}"
        )
    
    return prompt

def detect_summary_style(
    message: str
) -> str:
    msg = message.lower()
    
    if any(w in msg for w in [
        "short", "brief", "quick",
        "small", "chhota", "thoda"
    ]):
        return "short"
    
    elif any(w in msg for w in [
        "points", "bullets", "list",
        "point by point"
    ]):
        return "points"
    
    elif any(w in msg for w in [
        "detail", "detailed", "full",
        "complete", "poora", "depth"
    ]):
        return "detail"
    
    elif any(w in msg for w in [
        "brief", "one para",
        "paragraph"
    ]):
        return "brief"
    
    else:
        return "default"

async def run(user_message: str, memory_history: str = "", status_callback: Optional[Callable] = None, routing_info: Optional[dict] = None) -> Tuple[str, List[str]]:
    """
    SUPERVISOR ENTRY POINT: Orchestrates Executor and Judge.
    Uses routing_info passed from Semantic Router to bypass complex logic.
    """
    routing_info = routing_info or {}
    
    if routing_info.get("skip_judge", False):
        logger.info(f"SEMANTIC ROUTER OPTIMIZATION: '{routing_info.get('level')}' intent detected. Bypassing Judge.")
        result, attachments, _ = await _execute(user_message, memory_history, status_callback=status_callback)
        return result, attachments

    memory_context = ""

    max_supervisor_retries = 2
    current_correction = ""
    tool_logs = []
    import asyncio
    for attempt in range(max_supervisor_retries):
        logger.info(f"Supervisor Attempt {attempt + 1}/{max_supervisor_retries}")
        # 2. PARALLEL EXECUTION: Run Executor and Judge Preparation simultaneously
        # We pass the memory context and any current correction to the executor
        executor_input = user_message
        if memory_context or current_correction:
            executor_input = f"{user_message}\n{memory_context}\n{current_correction}".strip()
            
        executor_task = asyncio.create_task(_execute(executor_input, memory_history, status_callback=status_callback))
        judge_prep_task = asyncio.create_task(judge_agent.prepare_evaluation_criteria(user_message))
        
        # Wait for both to finish simultaneously
        (result, attachments, attempt_logs), criteria = await asyncio.gather(executor_task, judge_prep_task)
        
        tool_logs.extend(attempt_logs)
        
        # SPEED OPTIMIZATION A: Simple Command Bypassing
        # If the Executor ONLY used simple tools (or didn't use any tools but gave a response), skip the Judge.
        used_tools = [log["name"] for log in attempt_logs] if attempt_logs else []
        is_simple_task = all(t in SIMPLE_TOOLS for t in used_tools)
        
        if is_simple_task and not current_correction:
            logger.info("SPEED OPTIMIZATION: Bypassing Judge Agent for simple command.")
            return result, attachments

        # 3. JUDGE AGENT: Evaluate using the pre-computed criteria
        # For non-simple tasks, take a verification screenshot to provide visual proof to the judge
        image_b64 = None
        if not is_simple_task:
            logger.info("Taking verification screenshot for Judge Agent...")
            try:
                from opendesk.tools.system import take_screenshot
                temp_scr = "verification_screenshot.png"
                take_screenshot(temp_scr)
                if os.path.exists(temp_scr):
                    image_b64 = _encode_image(temp_scr)
                    # Optional: attachments.append(os.path.abspath(temp_scr))
            except Exception as e:
                logger.error(f"Failed to take verification screenshot: {e}")

        evaluation = await judge_agent.evaluate_response(user_message, result, attempt_logs, criteria, image_b64=image_b64)
        logger.info(f"Judge Evaluation: {evaluation}")
        
        if evaluation["task_completed"] and not evaluation["hallucinated"]:
            return result, attachments

        else:
            # FAILURE: Record mismatch and retry
            logger.warning(f"Judge rejected response: {evaluation['correction']}")
            current_correction = f"\n[PREVIOUS ATTEMPT FAILED]: {evaluation['correction']}. Please try again and ensure you call the correct tools."
            
    return f"I tried {max_supervisor_retries} times but could not complete this task. Final issue: {current_correction}", []

async def _execute(user_message: str, memory_history: str = "", status_callback: Optional[Callable] = None) -> Tuple[str, List[str], List[Dict]]:
    """
    Internal execution step (The Agent Loop).
    Returns (response_text, attachments, tool_logs)
    """
    tool_logs = []
    ctx_summary = monitor_instance.get_current_context_summary()
    
    # Hide system context in a way that the model knows it's background data
    system_ctx = f"[BACKGROUND SYSTEM STATE - DO NOT REPEAT UNLESS ASKED]\n{ctx_summary}\n"
    
    input_text = f"{system_ctx}\nUser Request: {user_message}"
    if memory_history:
        input_text = f"Recent Conversation History:\n{memory_history}\n\n{input_text}"
        
    messages: List[Any] = [
        SystemMessage(content=TOOL_CALLING_PROMPT),
        HumanMessage(content=input_text)
    ]
    
    # DYNAMIC TOOL LOADING
    active_tools = list(basic_lc_tools)
    
    # Check if the user is asking for advanced office tasks
    advanced_keywords = ["word", "excel", "powerpoint", "presentation", "spreadsheet", "document", "docx", "xlsx", "pptx", "sheet", "ppt"]
    if any(keyword in user_message.lower() for keyword in advanced_keywords):
        logger.info("Advanced keyword detected. Appending advanced Office tools to the schema.")
        active_tools.extend(advanced_lc_tools)
    else:
        logger.info("Running in Core mode. Advanced tools are stripped to prevent schema failures.")
        
    # Dynamically build the fallback chain for the current mode
    current_fallback_base = build_fallback_chain()
    active_fallback_chain = []
    for option in current_fallback_base:
        llm_with_tools = option["llm"].bind_tools(active_tools)
        active_fallback_chain.append({"name": option["name"], "llm": llm_with_tools})
    
    attachments = []
    max_iterations = 3
    
    for i in range(max_iterations):
        logger.info(f"Agent Loop Iteration {i+1}/{max_iterations}")
        
        # Determine current model context
        is_vision_mode = i > 0 and any(kw in str(messages[-1].content).lower() for kw in ["screen", "click", "find", "button", "see"])
        
        # OPTIMIZATION: If we just called a tool and have its output, we don't necessarily need vision unless asked
        if i > 0 and isinstance(messages[-1], ToolMessage):
             is_vision_mode = False 
             
        # Add vision instruction if needed
        messages_to_send = list(messages)
        if is_vision_mode:
            messages_to_send.append(HumanMessage(content="You are in vision mode. Please use the 'take_screenshot' tool to see the screen if you haven't already."))
        
        try:
            # SANITIZE MESSAGES FOR TEXT MODEL
            # Text models (Llama 3) will throw a 400 error if they encounter `image_url` dicts.
            if not is_vision_mode:
                sanitized_messages = []
                for msg in messages_to_send: # Use messages_to_send here, not original messages
                    if isinstance(msg, HumanMessage) and isinstance(msg.content, list):
                        # Extract only the text parts from multimodal messages
                        text_only_parts = [part["text"] for part in msg.content if isinstance(part, dict) and part.get("type") == "text"]
                        sanitized_content = "\n".join(text_only_parts) if text_only_parts else "Image provided (hidden from text model)."
                        sanitized_messages.append(HumanMessage(content=sanitized_content))
                    else:
                        sanitized_messages.append(msg)
                messages_to_send = sanitized_messages
            
            # MULTI-PROVIDER FALLBACK INVOCATION
            ai_msg = None
            if is_vision_mode:
                # Vision model has no fallback chain currently
                ai_msg = llm_vision.invoke(messages_to_send)
            else:
                last_error = None
                import opendesk.config as cfg
                current_mode = cfg.USER_MODE or "developer"
                
                for idx, fallback_option in enumerate(active_fallback_chain):
                    model_name = fallback_option["name"]
                    llm = fallback_option["llm"]
                    try:
                        logger.info(f"Attempting invocation with {model_name}...")
                        ai_msg = llm.invoke(messages_to_send)
                        break # Success! Break out of the fallback loop
                    except Exception as e:
                        error_text = str(e).lower()
                        last_error = e
                        
                        # ── MODE-SPECIFIC ERROR HANDLING ──
                        
                        # LOCAL MODE: Ollama crash
                        if current_mode == "local":
                            print("\n⚠️  Local AI crashed. Restarting...")
                            logger.error(f"Local AI crash: {e}")
                            # Auto-retry once silently (the fallback loop only has 1 item, so we force a retry)
                            if idx == 0:
                                time.sleep(2)
                                try:
                                    logger.info("Local mode: Silent retry 1...")
                                    ai_msg = llm.invoke(messages_to_send)
                                    break
                                except Exception as retry_err:
                                    print("\n❌ Local AI unavailable.")
                                    print("   Restart OpenDesk or switch to CLOUD mode in config.")
                                    raise RuntimeError(f"Local AI failed after retry: {retry_err}")

                        # CLOUD MODE: Groq Rate Limit
                        elif current_mode == "cloud":
                            if "429" in error_text or "rate limit" in error_text:
                                if len(active_fallback_chain) > idx + 1:
                                    # Fallback exists (Ollama)
                                    print("\n⚡ Switched to local mode temporarily")
                                    logger.warning("Groq rate limited. Switching to local fallback.")
                                    continue # Try next model (Ollama)
                                else:
                                    # No fallback
                                    print("\n⚠️  Cloud limit reached.")
                                    print("   Try again in 1 hour or install Ollama for local backup")
                                    raise RuntimeError("Cloud limit reached and no local fallback available.")


                        # INLINE HALLUCINATION RECOVERY (Shared)
                        if "tool_use_failed" in error_text or "failed_generation" in error_text:
                            logger.warning(f"{model_name} hallucinated a tool call (400). Attempting inline parse...")
                            h_name, h_args = _parse_hallucinated_tool_call(str(e))
                            if h_name and h_args:
                                func = _TOOLS.get(h_name)
                                if func:
                                    try:
                                        obs = func(**h_args)
                                        logger.info(f"INLINE FALLBACK SUCCESS: {h_name} returned: {obs}")
                                        tool_logs.append({"name": h_name, "args": h_args, "output": str(obs)})
                                        # Handle attachments ...
                                        return str(obs), attachments, tool_logs
                                    except Exception as e:
                                        logger.debug(f"Inline fallback tool execution failed: {e}")
                        
                        logger.warning(f"Model {model_name} failed with error: {error_text[:200]}. Falling back to next model...")
                        
                if not ai_msg:
                     raise RuntimeError(f"All fallback models failed. Last error: {last_error}")

            
            # If we used the vision model, it CANNOT return tool_calls.
            if is_vision_mode:
                text_content = ai_msg.content.strip()
                logger.info(f"Vision Model Output: {text_content}")
                vision_obs = SystemMessage(content=f"VISION ANALYSIS RESULT: {text_content}\nBased on this analysis, use your tools (like click_mouse or type_text) to interact with the UI.")
                messages.append(vision_obs)
                continue
            
            messages.append(ai_msg)
            
            # ===== TOOL CALL RESOLUTION =====
            tool_calls_to_execute = []
            
            # Path A: Native tool calls (ideal case)
            if ai_msg.tool_calls:
                for tc in ai_msg.tool_calls:
                    tool_calls_to_execute.append({
                        "name": tc["name"],
                        "args": tc["args"],
                        "id": tc.get("id", f"fallback_{i}")
                    })
            
            # Path B: No native tool calls — check for hallucinated XML calls in text
            if not tool_calls_to_execute and ai_msg.content:
                h_name, h_args = _parse_hallucinated_tool_call(ai_msg.content)
                if h_name and h_args:
                    logger.warning(f"FALLBACK PARSER: Caught hallucinated tool call: {h_name}({h_args})")
                    tool_calls_to_execute.append({
                        "name": h_name,
                        "args": h_args,
                        "id": f"fallback_{i}"
                    })
            
            # Path C: No tool calls at all — return final text answer
            if not tool_calls_to_execute:
                final_answer = ai_msg.content or "Task completed."
                return final_answer, attachments, tool_logs
                
            # ===== EXECUTE TOOLS =====
            for tool_call in tool_calls_to_execute:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
                
                func = _TOOLS.get(tool_name)
                if not func:
                    obs = f"Error: Tool '{tool_name}' not found. Available: {list(_TOOLS.keys())}"
                else:
                    try:
                        if status_callback:
                            await status_callback(f"⚙️ Executing: {tool_name}...")
                        
                        # BLOCKING TOOL: Run in thread to keep event loop free
                        obs = await asyncio.to_thread(func, **tool_args)
                        
                        if tool_name == "read_and_summarize" and isinstance(obs, str):
                            style = detect_summary_style(user_message)
                            obs = format_summary(obs, style)
                        
                        tool_logs.append({"name": tool_name, "args": tool_args, "output": str(obs)})
                        
                        # Log command usage in thread too
                        from opendesk.db.crud import log_command
                        await asyncio.to_thread(log_command, f"{tool_name}({tool_args})", status="success", output=str(obs))
                        
                        # Handle attachments
                        if isinstance(obs, str) and ("saved successfully at" in obs or "shared successfully at" in obs):
                            try:
                                marker = "shared successfully at " if "shared successfully at" in obs else "saved successfully at "
                                path_str = obs.split(marker)[1].split("\n")[0].strip().strip('"').strip("'")
                                if os.path.exists(path_str):
                                    if path_str not in attachments:
                                        attachments.append(path_str)
                                        
                                    if tool_name == "take_screenshot":
                                        base64_image = _encode_image(path_str)
                                        
                                        # 1. Satisfy the LLM's required ToolMessage contract first
                                        messages.append(ToolMessage(content=str(obs), tool_call_id=tool_id))
                                        
                                        # 2. Inject the actual image back into the context as a HumanMessage
                                        image_message = HumanMessage(
                                            content=[
                                                {"type": "text", "text": f"Here is the screenshot from the screen:"},
                                                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                                            ]
                                        )
                                        messages.append(image_message)
                                        continue 
                            except Exception as e:
                                logger.error(f"Error processing attachment: {e}")
                                
                    except Exception as e:
                        obs = f"Error executing {tool_name}: {str(e)}"
                        logger.error(obs)

                # Append tool result back to context
                messages.append(ToolMessage(content=str(obs), tool_call_id=tool_id))
                
                # HALT LOOP if human-in-the-loop action is requested
                if isinstance(obs, str) and "AWAITING_CONFIRMATION" in obs:
                    logger.info("Tool returned AWAITING_CONFIRMATION. Halting agent loop to wait for user.")
                    return str(obs), attachments, tool_logs
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in LLM invocation: {error_msg}")
            
            # ===== FALLBACK ERROR RECOVERY =====
            if "tool_use_failed" in error_msg or "failed_generation" in error_msg or "All fallback models failed" in error_msg:
                logger.warning("400 / Exhausted fallback detected. Attempting fallback parse from error message...")
                h_name, h_args = _parse_hallucinated_tool_call(error_msg)
                if h_name and h_args:
                    func = _TOOLS.get(h_name)
                    if func:
                        try:
                            obs = func(**h_args)
                            logger.info(f"FALLBACK SUCCESS: {h_name} returned: {obs}")
                            tool_logs.append({"name": h_name, "args": h_args, "output": str(obs)})
                            
                            if isinstance(obs, str) and ("saved successfully at" in obs or "shared successfully at" in obs):
                                marker = "shared successfully at " if "shared successfully at" in obs else "saved successfully at "
                                path_str = obs.split(marker)[1].split("\n")[0].strip().strip('"').strip("'")
                                if os.path.exists(path_str) and path_str not in attachments:
                                    attachments.append(path_str)
                            
                            return str(obs), attachments, tool_logs
                        except Exception as fallback_err:
                            logger.error(f"Fallback execution failed: {fallback_err}")
                            return f"Found the request but failed to execute: {fallback_err}", attachments, tool_logs
            
            time.sleep(1)
            if i == max_iterations - 1:
                return f"Agent stopped due to internal error: {error_msg}", attachments, tool_logs
                
    return "Agent stopped due to max iterations.", attachments, tool_logs
