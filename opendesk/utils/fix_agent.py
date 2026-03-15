"""Patch script to fix the corrupted lines in langchain_agent.py"""

path = r'c:\Users\AKSHAT JAIN\OneDrive\Desktop\OpenDeskAI\opendesk\ollama_agent\langchain_agent.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Keep lines 1 through 442 (index 0 through 441)
new_lines = lines[:442]

# The replacement block starts at what was line 443
replacement_block = [
    '                                        image_message = HumanMessage(\n',
    '                                            content=[\n',
    '                                                {"type": "text", "text": f"Tool \'{tool_name}\' result:\\n{obs}\\nHere is the screenshot:"},\n',
    '                                                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}\n',
    '                                            ]\n',
    '                                        )\n',
    '                                        messages.append(image_message)\n',
    '                                        continue \n',
    '                            except Exception as e:\n',
    '                                logger.error(f"Error processing attachment: {e}")\n',
    '                                \n',
    '                    except Exception as e:\n',
    '                        obs = f"Error executing {tool_name}: {str(e)}"\n',
    '                        logger.error(obs)\n',
    '                \n',
    '                # Append tool result back to context\n',
    '                messages.append(ToolMessage(content=str(obs), tool_call_id=tool_id))\n',
    '                \n',
    '        except Exception as e:\n',
    '            error_msg = str(e)\n',
    '            logger.error(f"Error in LLM invocation: {error_msg}")\n',
    '            \n',
    '            # ===== FALLBACK ERROR RECOVERY =====\n',
    '            if "tool_use_failed" in error_msg or "failed_generation" in error_msg or "All fallback models failed" in error_msg:\n',
    '                logger.warning("400 / Exhausted fallback detected. Attempting fallback parse from error message...")\n',
    '                h_name, h_args = _parse_hallucinated_tool_call(error_msg)\n',
    '                if h_name and h_args:\n',
    '                    func = _TOOLS.get(h_name)\n',
    '                    if func:\n',
    '                        try:\n',
    '                            obs = func(**h_args)\n',
    '                            logger.info(f"FALLBACK SUCCESS: {h_name} returned: {obs}")\n',
    '                            tool_logs.append({"name": h_name, "args": h_args, "output": str(obs)})\n',
    '                            \n',
    '                            if isinstance(obs, str) and ("saved successfully at" in obs or "shared successfully at" in obs):\n',
    '                                marker = "shared successfully at " if "shared successfully at" in obs else "saved successfully at "\n',
    '                                path_str = obs.split(marker)[1].split("\\n")[0].strip().strip(\'"\').strip("\'")\n',
    '                                if os.path.exists(path_str) and path_str not in attachments:\n',
    '                                    attachments.append(path_str)\n',
    '                            \n',
    '                            return str(obs), attachments, tool_logs\n',
    '                        except Exception as fallback_err:\n',
    '                            logger.error(f"Fallback execution failed: {fallback_err}")\n',
    '                            return f"Found the request but failed to execute: {fallback_err}", attachments, tool_logs\n',
    '            \n',
    '            time.sleep(1)\n',
    '            if i == max_iterations - 1:\n',
    '                return f"Agent stopped due to internal error: {error_msg}", attachments, tool_logs\n',
    '                \n',
    '    return "Agent stopped due to max iterations.", attachments, tool_logs\n',
]

new_lines.extend(replacement_block)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"SUCCESS: File patched. Total lines: {len(new_lines)}")
