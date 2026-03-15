import json
import re

def _parse_hallucinated_tool_call(text: str):
    """Catches hallucinated tool calls from weaker models."""
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
            except Exception:
                pass


    # Pattern 3: Existing XML style <function=tool_name>{"arg": "val"}</function>
    match = re.search(r'<function=([\w]+)>\s*(\{.*?\})', text, re.DOTALL)
    if match:
        tool_name = match.group(1)
        try:
            tool_args = json.loads(match.group(2))
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

def run_tests():
    tests = [
        # Test 1: Markdown JSON
        (
            '''Here is the file you requested.
```json
{
  "name": "share_file",
  "arguments": {
    "filename": "ak.jpg"
  }
}
```
            ''', 
            ("share_file", {"filename": "ak.jpg"})
        ),
        
        # Test 2: Python function call
        (
            'I will find that for you right away. share_file(filename="document.pdf", search_dir="Downloads")',
            ("share_file", {"filename": "document.pdf", "search_dir": "Downloads"})
        ),
        
        # Test 3: Action format
        (
            '''Thought: I should share the file.
Action: share_file
Action Input: {"filename": "report.docx"}''',
            ("share_file", {"filename": "report.docx"})
        ),
        
        # Test 4: Existing XML format
        (
            '<function=share_file>{"filename": "test.txt"}</function>',
            ("share_file", {"filename": "test.txt"})
        ),
        
        # Test 5: Existing JSON format
        (
            '{"name": "take_screenshot", "arguments": {}}',
            ("take_screenshot", {})
        ),
    ]

    for i, (input_text, expected) in enumerate(tests):
        result = _parse_hallucinated_tool_call(input_text)
        print(f"Test {i+1}: {'PASS' if result == expected else 'FAIL'}")
        if result != expected:
            print(f"  Got: {result}, Expected: {expected}")

if __name__ == "__main__":
    run_tests()
