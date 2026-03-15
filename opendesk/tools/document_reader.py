import os
from loguru import logger
from .registry import register_tool
try:
    import pandas as pd # type: ignore
except ImportError:
    pd = None
try:
    from PyPDF2 import PdfReader # type: ignore
except ImportError:
    PdfReader = None
try:
    from docx import Document # type: ignore
except ImportError:
    Document = None



HOME_DIR = os.path.expanduser("~")

def _is_safe_path(filepath: str) -> bool:
    """Check if the given path is within the user's home directory."""
    abs_path = os.path.abspath(os.path.expanduser(filepath))
    return abs_path.startswith(HOME_DIR)

@register_tool("read_document")
def read_document(filepath: str) -> str:
    """Reads and extracts text from various document formats (.pdf, .docx, .xlsx, .csv, .txt).
    Only allows paths within the user's home directory.
    This is highly useful for answering questions about local files."""
    
    if not _is_safe_path(filepath):
        return f"Access denied: '{filepath}' is outside your home directory ({HOME_DIR})."
    
    abs_path = os.path.abspath(os.path.expanduser(filepath))
    
    if not os.path.exists(abs_path):
        return f"Error: File '{abs_path}' does not exist."
        
    ext = os.path.splitext(abs_path)[1].lower()
    content = ""
    
    try:
        if ext == '.pdf':
            if not PdfReader:
                return "Error: PyPDF2 is not installed."
            reader = PdfReader(abs_path)
            text_lines = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_lines.append(text)
            content = "\n".join(text_lines)
            
        elif ext == '.docx':
            if not Document:
                return "Error: python-docx is not installed."
            doc = Document(abs_path)
            content = "\n".join([p.text for p in doc.paragraphs])
            
        elif ext in ['.xlsx', '.xls']:
            if not pd:
                return "Error: pandas is not installed."
            df = pd.read_excel(abs_path)
            content = df.to_markdown(index=False)
            
        elif ext == '.csv':
            if not pd:
                return "Error: pandas is not installed."
            df = pd.read_csv(abs_path)
            content = df.to_markdown(index=False)
            
        elif ext in ['.txt', '.md', '.json', '.log', '.ini', '.yaml', '.yml']:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
                
        else:
            return f"Error: Unsupported file extension '{ext}'. Try using the appropriate specific tool or opening it natively."

        # Enforce limits to prevent LLM context explosion
        MAX_CHARS = 20000 
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + f"\n\n... [Document truncated at {MAX_CHARS} characters to save context.]"
            
        return f"--- DOCUMENT CONTENTS ({os.path.basename(abs_path)}) ---\n{content}\n--- END DOCUMENT ---"
        
    except Exception as e:
        logger.error(f"Error reading document: {e}")
        return f"Error reading document '{filepath}': {e}"
