import re
import urllib.parse
from loguru import logger
from opendesk.tools.registry import register_tool
from bs4 import BeautifulSoup


@register_tool("search_web")
def search_web(query: str, max_results: int = 5, open_in_browser: bool = False, platform: str = "google") -> str:
    """Searches the internet for the given query and returns top results with URLs and snippets. 
    IMPORTANT RULES: 
    1. If 'open_in_browser' is True, the browser opens physically but YOU DO NOT GET THE RESULTS BACK to answer the user. 
    2. ONLY use 'open_in_browser=True' if the user explicitly asks to just OPEN the page. 
    3. If the user asks to 'tell me', 'find', or 'summarize' the information here in chat, 'open_in_browser' MUST BE FALSE.
    4. You CANNOT close standard browser tabs once opened. If the user asks to close it, apologize and explain you can't."""
    if open_in_browser:
        try:
            if platform.lower() == 'youtube':
                import webbrowser
                search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                webbrowser.open(search_url)
                return f"✅ Opened YouTube search for: {query} (click to play)"
            else:
                import webbrowser
                search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(search_url)
                return f"✅ Opened Google search for: {query}"
        except Exception as e:
            return f"Failed to open browser directly: {e}"


    try:
        import urllib.request
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(
            search_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        html_content = urllib.request.urlopen(req, timeout=10).read()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        ad_pattern = re.compile(r'\b(ad|ads|sponsored|advertisement)\b', re.IGNORECASE)
        results = []
        for result_div in soup.find_all('div', class_='result__body', limit=max_results + 3):
            title_node = result_div.find('h2', class_='result__title')
            if not title_node: continue
            
            link_node = result_div.find('a', class_='result__url')
            if not link_node: continue
            
            title = title_node.text.strip()
            raw_link = link_node.get('href', '')
            
            # DuckDuckGo wraps actual links in a redirect url. Extract it.
            link = raw_link
            if 'uddg=' in raw_link:
                try:
                    link = urllib.parse.unquote(raw_link.split('uddg=')[1].split('&')[0])
                except:
                    pass
                
            snippet_node = result_div.find('a', class_='result__snippet')
            snippet = snippet_node.text.strip() if snippet_node else "No snippet"
            
            full_text = f"{title} {snippet} {link}"
            if ad_pattern.search(full_text):
                continue
                
            results.append({
                "title": title,
                "body": snippet,
                "href": link
            })
            if len(results) >= max_results:
                break
            
        if not results:
            return f"No results found for '{query}'. The search engine might be blocking automated requests."
            
        clean_results = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "")
            snippet = result.get("body", "")
            url = result.get("href", "")
            
            if title and snippet:
                clean_results.append(
                    f"Source {i}: {title}\n"
                    f"Info: {snippet}\n"
                    f"URL: {url}"
                )
        
        if clean_results:
            return (
                f"Web search results for: {query}\n\n"
                + "\n\n".join(clean_results)
            )
        return "No results found"
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
            
        # Convert structure to basic markdown before stripping tags
        for b in soup.find_all(['b', 'strong']): b.replace_with(f"**{b.text}**")
        for i in soup.find_all(['i', 'em']): i.replace_with(f"*{i.text}*")
        for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']): 
            level = int(h.name[1])
            h.replace_with(f"\n\n{'#' * level} {h.text}\n\n")
        for li in soup.find_all('li'): li.replace_with(f"\n* {li.text}")
        for p in soup.find_all('p'): p.replace_with(f"\n{p.text}\n")
            
        # Get the formatted text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up weird spacing but preserve our newline structure
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text).strip()
        
        # Safety Lock: We must truncate giant webpages so we don't crash the LLM's context window
        if len(text) > 8000:
            text = text[:8000] + "\n\n...[Content truncated to save AI memory]"
            
        return text if text else "Page loaded successfully, but no readable text was found."
        
    except Exception as e:
        logger.error(f"Error reading webpage {url}: {e}")
        return f"Failed to successfully render and read webpage: {e}"
