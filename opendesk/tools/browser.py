import re
from loguru import logger
from opendesk.tools.registry import register_tool
from bs4 import BeautifulSoup

import urllib.parse

@register_tool("search_web")
def search_web(query: str, max_results: int = 5) -> str:
    """Searches the internet for the given query and returns top results with URLs and snippets."""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            search_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as nav_e:
                logger.warning(f"Playwright navigation interrupted, but parsing loaded DOM: {nav_e}")
            
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        results = []
        for li in soup.find_all('li', class_='b_algo', limit=max_results):
            title_node = li.find('h2')
            if not title_node: continue
            
            a_node = title_node.find('a')
            if not a_node: continue
            
            title = a_node.text.strip()
            link = a_node.get('href', '')
            
            snippet_node = li.find('p')
            snippet = snippet_node.text.strip() if snippet_node else "No snippet"
            
            results.append(f"[{title}]({link})\n   Snippet: {snippet}")
            
        if not results:
            return f"No results found for '{query}'. The search engine might be blocking automated requests."
            
        output = f"Top {len(results)} search results for '{query}':\n\n"
        for i, res in enumerate(results, 1):
            output += f"{i}. {res}\n\n"
        return output
    except Exception as e:
        logger.error(f"Error searching web: {e}")
        return f"Error searching the web: {e}"

@register_tool("read_webpage")
def read_webpage(url: str) -> str:
    """Navigates to a webpage, renders JavaScript, and extracts the visible text content."""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # We use an invisible headless browser to avoid annoying the user
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Wait until the basic DOM is loaded (timeout 30s to not block the bot forever)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as nav_e:
                logger.warning(f"Playwright navigation interrupted, but continuing to scrape what landed: {nav_e}")
            
            html_content = page.content()
            browser.close()
            
        # Parse the raw HTML into beautiful, clean text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Brutally scrub out all useless visual layout junk (menus, scripts, ads)
        for junk in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe", "aside"]):
            junk.decompose()
            
        # Get only the text that a human would actually read
        text = soup.get_text(separator=' ', strip=True)
        
        # Collapse massive white spaces into single spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Safety Lock: We must truncate giant webpages so we don't crash the LLM's context window
        if len(text) > 8000:
            text = text[:8000] + "\n\n...[Content truncated to save AI memory]"
            
        return text if text else "Page loaded successfully, but no readable text was found."
        
    except Exception as e:
        logger.error(f"Error reading webpage {url}: {e}")
        return f"Failed to successfully render and read webpage: {e}"
