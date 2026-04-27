import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack

from loguru import logger
from dotenv import load_dotenv, set_key
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import aiohttp
import webbrowser
import asyncio
import uuid

BASE_DIR = Path(__file__).parent
REGISTRY_PATH = BASE_DIR / "mcp_registry.json"
ENV_PATH = BASE_DIR.parent / ".env"

# Ensure .env is loaded
load_dotenv(dotenv_path=ENV_PATH)

class Tool:
    def __init__(self, name: str, description: str, inputSchema: dict):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema

class BaseConnector:
    def __init__(self, app_id: str, broker: "ConnectorBroker"):
        self.app_id = app_id
        self.broker = broker

    def connect(self, token: str) -> bool:
        pass

    def disconnect(self) -> bool:
        pass

    def status(self) -> dict:
        pass

    async def execute_action(self, action: str, params: dict) -> str:
        pass

    async def refresh_token(self) -> bool:
        pass

class SpotifyConnector(BaseConnector):
    def __init__(self, broker: "ConnectorBroker"):
        super().__init__("spotify", broker)

    async def execute_action(self, action: str, params: dict) -> str:
        token = await self.broker._get_access_token(self.app_id)
        if not token:
            return "Error: No Spotify access token found in proxy. Please run /connect spotify first."
            
        result = await self._do_action(token, action, params)
        if result == "401":
            logger.info("Spotify token returned 401. Forcing refresh via proxy...")
            token = await self.broker._get_access_token(self.app_id, force_refresh=True)
            if not token:
                return "Error: Failed to fetch refreshed Spotify token."
            result = await self._do_action(token, action, params)
            if result == "401":
                return "Error: Spotify token is still unauthorized after refresh. Please run /connect spotify again."
        return result

    async def _do_action(self, token: str, action: str, params: dict) -> str:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        async with aiohttp.ClientSession() as session:
            if action == "play_track":
                song_name = params.get("song_name", "")
                return await self._search_and_play(session, headers, song_name)
            elif action == "now_playing":
                async with session.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers) as resp:
                    if resp.status == 401: return "401"
                    if resp.status == 200:
                        data = await resp.json()
                        if data and data.get("item"):
                            return f"🎵 Now playing: {data['item']['name']} by {data['item']['artists'][0]['name']}"
                    return "Nothing is currently playing on Spotify."
            elif action == "pause":
                async with session.put("https://api.spotify.com/v1/me/player/pause", headers=headers) as resp:
                    if resp.status == 401: return "401"
                    if resp.status in (200, 204):
                        return "⏸️ Paused Spotify."
                    return f"Error pausing Spotify: {resp.status}"
            elif action == "next_track":
                async with session.post("https://api.spotify.com/v1/me/player/next", headers=headers) as resp:
                    if resp.status == 401: return "401"
                    return "⏭️ Skipped to next track." if resp.status in (200, 204) else f"Error: {resp.status}"
            elif action == "previous_track":
                async with session.post("https://api.spotify.com/v1/me/player/previous", headers=headers) as resp:
                    if resp.status == 401: return "401"
                    return "⏮️ Went to previous track." if resp.status in (200, 204) else f"Error: {resp.status}"
            elif action == "like_song":
                async with session.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers) as resp:
                    if resp.status == 401: return "401"
                    if resp.status == 200:
                        data = await resp.json()
                        track_id = data.get("item", {}).get("id")
                        if track_id:
                            async with session.put(f"https://api.spotify.com/v1/me/tracks?ids={track_id}", headers=headers) as like_resp:
                                if like_resp.status == 401: return "401"
                                return "❤️ Liked the current song!" if like_resp.status in (200, 204) else f"Error liking: {like_resp.status}"
                    return "No song is currently playing to like."
        return f"Unknown action: {action}"

    async def _search_and_play(self, session, headers, song_name: str) -> str:
        # ── Step 1: Search Spotify for the track ────────────────────────
        async with session.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params={"q": song_name, "type": "track", "limit": 5}
        ) as resp:
            if resp.status == 401:
                return "401"
            if resp.status != 200:
                return f"Error searching Spotify: {await resp.text()}"
            search_data = await resp.json()
            
        tracks = search_data.get("tracks", {}).get("items", [])
        if not tracks:
            return f"Could not find any track matching '{song_name}' on Spotify."
        
        from difflib import SequenceMatcher
        query_lower = song_name.lower().strip()
        query_words = set(query_lower.split())
        
        best_track = tracks[0]
        best_score = -1
        
        for candidate in tracks:
            cname = candidate.get("name", "").lower()
            score = 0
            
            if query_lower == cname:
                score = 100
            else:
                cname_words = set(cname.split())
                if query_words and query_words.issubset(cname_words):
                    score = 80
                else:
                    score = SequenceMatcher(None, query_lower, cname).ratio() * 100
                    
            if score > best_score:
                best_score = score
                best_track = candidate
                
        if best_score <= 40:
            best_track = tracks[0]
        
        track = best_track
        track_name = track.get("name", song_name)
        artist_name = track.get("artists", [{}])[0].get("name", "Unknown Artist")
        uri = track.get("uri")
        
        # ── Step 2: Open Spotify desktop to ensure an active device ────
        webbrowser.open("spotify:")
        await asyncio.sleep(4)
        
        # ── Step 3: Call the REAL Playback API ────────────────────────
        play_headers = {**headers, "Content-Type": "application/json"}
        
        async with session.put(
            "https://api.spotify.com/v1/me/player/play",
            headers=play_headers,
            json={"uris": [uri]}
        ) as play_resp:
            if play_resp.status == 401:
                return "401"
            if play_resp.status == 404:
                logger.warning("No active Spotify device found. Retrying in 5s...")
                await asyncio.sleep(5)
                async with session.put(
                    "https://api.spotify.com/v1/me/player/play",
                    headers=play_headers,
                    json={"uris": [uri]}
                ) as retry_resp:
                    if retry_resp.status not in (200, 204):
                        return (
                            f"Spotify is open but not ready. Please click anywhere in Spotify once, "
                            f"then try again. (Status: {retry_resp.status})"
                        )
            elif play_resp.status not in (200, 204):
                return f"Playback API error ({play_resp.status}): {await play_resp.text()}"
        
        logger.info(f"Spotify API playback started: {track_name} by {artist_name}")
        return f"🎵 Now playing: **{track_name}** by **{artist_name}**"


class GitHubConnector(BaseConnector):
    """
    Connects to the Cloudflare Worker REST API for GitHub MCP.
    Bypasses SSE to avoid Serverless isolate termination issues.
    """
    def __init__(self, broker: "ConnectorBroker"):
        super().__init__("github", broker)

    async def get_oauth_token(self, session_id: str) -> str:
        proxy_base = os.getenv("OPENDESK_PROXY_URL", "").rstrip("/")
        if not proxy_base:
            return ""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{proxy_base}/tokens/{session_id}/github") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("access_token", "")
        except Exception as e:
            logger.error(f"Failed to fetch GitHub token: {e}")
        return ""

    def get_app_tools(self) -> List[Tool]:
        return [
            Tool(name="listRepositories", description="List repositories for the authenticated user", inputSchema={"type": "object", "properties": {"visibility": {"type": "string", "enum": ["all", "public", "private"]}, "sort": {"type": "string"}}}),
            Tool(name="searchRepositories", description="Search for GitHub repositories", inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
            Tool(name="getFileContents", description="Get the contents of a file or directory", inputSchema={"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}}, "required": ["owner", "repo", "path"]}),
            Tool(name="listIssues", description="List issues in a repository", inputSchema={"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "state": {"type": "string", "enum": ["open", "closed", "all"]}}, "required": ["owner", "repo"]}),
            Tool(name="createIssue", description="Create a new issue", inputSchema={"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}, "required": ["owner", "repo", "title", "body"]})
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        app = next((a for a in self.broker.registry if a["id"] == "github"), None)
        if not app or not app.get("connected"):
            return "GitHub is not connected."

        token = await self.get_oauth_token(app.get("session_id", ""))
        if not token:
            token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")

        url = app["mcp_url"].replace("/sse", "/call")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json={"tool": name, "args": arguments}) as resp:
                    if resp.status == 401:
                        return "GitHub authentication failed. Please re-authenticate."
                    result = await resp.json()
                    return str(result)
        except Exception as e:
            return f"Failed to execute GitHub tool: {e}"


class ConnectorBroker:
    """
    Engine for managing external MCP Client connections using an Adapter pattern.
    """

    def __init__(self):
        self.connectors: Dict[str, BaseConnector] = {}
        self._register_connector(SpotifyConnector(self))
        self._register_connector(GitHubConnector(self))
        
        self.registry: List[Dict[str, Any]] = []
        self._load_registry()
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}

    def _register_connector(self, connector: BaseConnector) -> None:
        self.connectors[connector.app_id] = connector

    def get_connector(self, app_id: str) -> Optional[BaseConnector]:
        return self.connectors.get(app_id)

    def _load_registry(self) -> None:
        """Loads apps from the registry and hydrates connection state."""
        if REGISTRY_PATH.exists():
            try:
                with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                    self.registry = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse mcp_registry.json: {e}")
                self.registry = []

        # Hydrate 'connected' status based on auth_type:
        # - oauth apps: connected if they have a session_id from the cloud proxy
        # - api_key apps: connected if the env var token is set
        for app in self.registry:
            if app.get("auth_type") == "oauth":
                app["connected"] = bool(app.get("session_id"))
            else:
                token_key = f"MCP_{app['id'].upper()}_TOKEN"
                app["connected"] = bool(os.getenv(token_key))

    def _save_registry(self) -> None:
        """Saves current registry state back to disk."""
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)

    def list_available_apps(self) -> List[Dict[str, Any]]:
        return self.registry

    def list_connected_apps(self) -> List[Dict[str, Any]]:
        return [app for app in self.registry if app.get("connected")]

    def get_session_id(self, app_id: str) -> str:
        app = next((a for a in self.registry if a["id"] == app_id), None)
        return app.get("session_id", "") if app else ""

    async def _get_access_token(self, app_id: str, force_refresh: bool = False) -> str:
        proxy_base = os.getenv("OPENDESK_PROXY_URL")
        if not proxy_base:
            return ""

        session_id = self.get_session_id(app_id)
        if not session_id:
            return ""

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{proxy_base.rstrip('/')}/tokens/{session_id}/{app_id}"
                params = {"force_refresh": "true"} if force_refresh else {}
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("access_token", "")
        except Exception as e:
            logger.error(f"Failed to fetch {app_id} tokens from proxy: {e}")
        return ""

    def connect_app(self, app_id: str, auth_token: str) -> bool:
        """Legacy api_key connection flow, still saves to .env for now."""
        for app in self.registry:
            if app["id"] == app_id:
                app["connected"] = True
                token_key = f"MCP_{app_id.upper()}_TOKEN"
                
                set_key(str(ENV_PATH), token_key, auth_token)
                os.environ[token_key] = auth_token
                
                self._save_registry()
                logger.info(f"Successfully connected to MCP app: {app_id}")
                return True
                
        return False

    def disconnect_app(self, app_id: str) -> bool:
        """Removes the connection state."""
        for app in self.registry:
            if app["id"] == app_id:
                app["connected"] = False
                
                # oauth apps store session_id; api_key apps store env var token
                if app.get("auth_type") == "oauth":
                    app.pop("session_id", None)
                else:
                    token_key = f"MCP_{app_id.upper()}_TOKEN"
                    set_key(str(ENV_PATH), token_key, "")
                    os.environ.pop(token_key, None)
                
                if app_id in self.sessions:
                    self.sessions.pop(app_id, None)

                self._save_registry()
                logger.info(f"Disconnected from MCP app: {app_id}")
                return True
                
        return False

    def is_connected(self, app_id: str) -> bool:
        app = next((a for a in self.registry if a["id"] == app_id), None)
        return bool(app and app.get("connected"))

    async def execute(self, app_id: str, action: str, params: dict) -> str:
        connector = self.get_connector(app_id)
        if connector:
            return await connector.execute_action(action, params)
        return f"Error: No connector adapter found for {app_id}"

    async def spotify_play(self, song_name: str) -> str:
        """Shim for system.py backward compatibility."""
        return await self.execute("spotify", "play_track", {"song_name": song_name})

    async def start_oauth_flow(self, app_id: str, chat_id: int, bot: Any) -> str:
        """Redirects the user to the Central Auth Proxy and starts polling for tokens."""
        proxy_base = os.getenv("OPENDESK_PROXY_URL")
        if not proxy_base:
            return "⚠️ OPENDESK_PROXY_URL is not set in .env. \n   Please deploy the cloud proxy and set the URL first."
            
        session_id = str(uuid.uuid4())
        proxy_url_clean = proxy_base.rstrip('/')
            
        auth_url = f"{proxy_url_clean}/login/{app_id}?session_id={session_id}"
        
        async def poll_for_tokens():
            logger.info(f"Started polling for {app_id} tokens with session {session_id}")
            async with aiohttp.ClientSession() as session:
                for _ in range(100): # 5 minutes max
                    await asyncio.sleep(3)
                    try:
                        url = f"{proxy_url_clean}/tokens/{session_id}/{app_id}"
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                access_token = data.get("access_token")
                                
                                if access_token:
                                    for r_app in self.registry:
                                        if r_app["id"] == app_id:
                                            r_app["connected"] = True
                                            # All oauth apps store session_id for proxy token lookup.
                                            # Only legacy api_key apps store the raw token in env.
                                            if r_app.get("auth_type") == "oauth":
                                                r_app["session_id"] = session_id
                                            else:
                                                token_key = f"MCP_{app_id.upper()}_TOKEN"
                                                set_key(str(ENV_PATH), token_key, access_token)
                                                os.environ[token_key] = access_token
                                            
                                    self._save_registry()
                                    logger.info(f"Successfully connected {app_id} via proxy.")
                                    
                                    try:
                                        await bot.send_message(chat_id=chat_id, text=f"✅ {app_id.title()} connected successfully!")
                                    except Exception as e:
                                        logger.error(f"Failed to send Telegram success message: {e}")
                                        
                                    return
                    except Exception as e:
                        logger.debug(f"Polling token error: {e}")
            logger.warning(f"Timeout waiting for OAuth tokens for {app_id}.")
            
        asyncio.create_task(poll_for_tokens())
        return auth_url

    async def _get_session(self, app_id: str) -> Optional[ClientSession]:
        """Gets or creates an active ClientSession for the given app_id via SSE."""
        if app_id in self.sessions:
            return self.sessions[app_id]

        app = next((a for a in self.registry if a["id"] == app_id), None)
        if not app or not app.get("connected"):
            logger.error(f"Cannot get session: {app_id} is not connected.")
            return None

        token = ""
        # Use the Cloud Proxy for ANY oauth app that has a session_id stored.
        # This covers both registered Connector adapters (Spotify, Gmail) and
        # pure MCP SSE apps (GitHub) without requiring a Connector class.
        session_id = app.get("session_id", "")
        if app.get("auth_type") == "oauth" and session_id:
            proxy_base = os.getenv("OPENDESK_PROXY_URL", "").rstrip('/')
            if proxy_base:
                try:
                    async with aiohttp.ClientSession() as session_req:
                        url = f"{proxy_base}/tokens/{session_id}/{app_id}"
                        async with session_req.get(url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                token = data.get("access_token", "")
                except Exception as e:
                    logger.error(f"Error fetching token from proxy for {app_id}: {e}")
        else:
            # Legacy api_key flow: token lives in env var
            token_key = f"MCP_{app_id.upper()}_TOKEN"
            token = os.getenv(token_key, "")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        } if token else {}

        try:
            transport = await self.exit_stack.enter_async_context(
                sse_client(app["mcp_url"], headers=headers)
            )
            session = await self.exit_stack.enter_async_context(
                ClientSession(*transport)
            )
            await session.initialize()
            
            self.sessions[app_id] = session
            logger.info(f"Established SSE connection with {app_id} MCP server.")
            return session
            
        except Exception as e:
            logger.error(f"Failed to connect to {app_id} MCP server at {app['mcp_url']}: {e}")
            return None

    async def get_app_tools(self, app_id: str) -> List[Tool]:

        if app_id == "spotify":
            return [
                Tool("spotify_play", "Play a song on Spotify", {"type": "object", "properties": {"song_name": {"type": "string", "description": "Name of the song"}}, "required": ["song_name"]}),
                Tool("spotify_pause", "Pause the current song on Spotify", {"type": "object", "properties": {}}),
                Tool("spotify_next", "Skip to the next song on Spotify", {"type": "object", "properties": {}}),
                Tool("spotify_previous", "Go to the previous song on Spotify", {"type": "object", "properties": {}}),
                Tool("spotify_like", "Like the currently playing song on Spotify (add to liked songs)", {"type": "object", "properties": {}})
            ]
            
        # For all MCP SSE apps (GitHub, Gmail, Notion, etc.) discover tools dynamically.
        # If the app is hosted on our Render proxy, use the REST MCP discovery
        proxy_base = os.getenv("OPENDESK_PROXY_URL", "").rstrip('/')
        if proxy_base and app_id in ["notion", "github"]:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session_req:
                    url = f"{proxy_base}/mcp/{app_id}/tools"
                    async with session_req.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            raw_tools = data.get("tools", [])
                            return [Tool(t["name"], t["description"], t["inputSchema"]) for t in raw_tools]
            except Exception as e:
                logger.error(f"Failed to fetch REST tools for {app_id}: {e}")

        session = await self._get_session(app_id)
        if session:
            try:
                response = await session.list_tools()
                return response.tools
            except Exception as e:
                logger.error(f"Failed to fetch tools for {app_id}: {e}")
        return []

    async def call_tool(self, app_id: str, tool_name: str, params: Dict[str, Any]) -> Any:
        if app_id == "spotify" and tool_name.startswith("spotify_"):
            if tool_name == "spotify_play":
                return await self.spotify_play(params.get("song_name", ""))
            elif tool_name == "spotify_pause":
                return await self.execute("spotify", "pause", {})
            elif tool_name == "spotify_next":
                return await self.execute("spotify", "next_track", {})
            elif tool_name == "spotify_previous":
                return await self.execute("spotify", "previous_track", {})
            elif tool_name == "spotify_like":
                return await self.execute("spotify", "like_song", {})
                
        # For all MCP SSE apps (GitHub, Gmail, Notion, etc.) route through the live session.
        # If the app is hosted on our Render proxy, use the REST MCP call
        proxy_base = os.getenv("OPENDESK_PROXY_URL", "").rstrip('/')
        if proxy_base and app_id in ["notion", "github"]:
            try:
                session_id = self.get_session_id(app_id)
                import aiohttp
                async with aiohttp.ClientSession() as session_req:
                    url = f"{proxy_base}/mcp/{app_id}/call"
                    params_req = {"session_id": session_id}
                    async with session_req.post(url, params=params_req, json={"tool": tool_name, "args": params}) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            return str(result)
                        else:
                            return f"Error from proxy: {await resp.text()}"
            except Exception as e:
                logger.error(f"Failed to call REST tool for {app_id}: {e}")
                return f"Error: {e}"

        session = await self._get_session(app_id)
        if session:
            try:
                logger.info(f"Calling MCP tool '{tool_name}' on app '{app_id}' with params: {params}")
                result = await session.call_tool(tool_name, arguments=params)
                
                output_texts = []
                for content in result.content:
                    if content.type == "text":
                        output_texts.append(content.text)
                
                return "\n".join(output_texts) if output_texts else "Success (No text output)"
                
            except Exception as e:
                err_msg = f"Error calling {tool_name} on {app_id}: {e}"
                logger.error(err_msg)
                return f"Error: {err_msg}"
                
        return f"Error: Failed to connect to {app_id} session."

    async def shutdown(self) -> None:
        logger.info("Shutting down Connector Broker...")
        await self.exit_stack.aclose()
        self.sessions.clear()

# Global Singleton Instance
mcp_client = ConnectorBroker()
