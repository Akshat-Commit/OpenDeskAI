import os
import base64
import httpx
import urllib.parse
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from typing import Optional
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import asyncpg

load_dotenv()

db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check for critical env var
    if not os.getenv("OPENDESK_PROXY_URL"):
        print("CRITICAL ERROR: OPENDESK_PROXY_URL environment variable is not set!")
    
    global db_pool
    db_pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        statement_cache_size=0
    )
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                session_id TEXT,
                app_id TEXT,
                access_token TEXT,
                refresh_token TEXT,
                timestamp FLOAT,
                PRIMARY KEY (session_id, app_id)
            )
        """)
        
    yield
    await db_pool.close()

app = FastAPI(title="OpenDesk Universal Auth Proxy", lifespan=lifespan)

# MASTER CONFIGURATION
# In production, these should be set in your Cloud Provider's Environment Variables (Vercel/Render)
APPS = {
    "spotify": {
        "auth_url": "https://accounts.spotify.com/authorize",
        "token_url": "https://accounts.spotify.com/api/token",
        "scopes": "user-modify-playback-state user-read-playback-state user-read-currently-playing",
        "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
        "auth_style": "header",   # Spotify uses Basic Auth for token refresh
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scopes": "repo workflow",
        "client_id": os.getenv("GITHUB_CLIENT_ID"),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
        "auth_style": "body",     # GitHub sends client creds in body
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "scopes": "",
        "client_id": os.getenv("NOTION_CLIENT_ID"),
        "client_secret": os.getenv("NOTION_CLIENT_SECRET"),
        "auth_style": "header",   # Notion uses Basic Auth
    },
    "gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": "https://mail.google.com/ https://www.googleapis.com/auth/gmail.send",
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_style": "body",     # Google sends client creds in body
    },
    "google_calendar": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": "https://www.googleapis.com/auth/calendar",
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_style": "body",     # Google sends client creds in body
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": "channels:read chat:write groups:read im:read files:read users:read",
        "user_scopes": "channels:history groups:history im:history search:read",
        "client_id": os.getenv("SLACK_CLIENT_ID"),
        "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
        "auth_style": "header",   # Slack uses Basic Auth
    }
}

@app.get("/")
async def root():
    return {"message": "OpenDesk Auth Proxy is running"}

@app.get("/login/{app_id}")
async def login(app_id: str, session_id: str):
    if app_id not in APPS:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not supported")
    
    config = APPS[app_id]
    if not config["client_id"]:
        raise HTTPException(status_code=500, detail=f"Master Client ID for {app_id} is not configured on server")

    params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": f"{os.getenv('OPENDESK_PROXY_URL').rstrip('/')}/callback/{app_id}",
        "state": session_id, 
    }
    
    if config["scopes"]:
        params["scope"] = config["scopes"]
        
    # Google apps need offline access + consent prompt to get a refresh_token
    if app_id in ("gmail", "google_calendar"):
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    # Slack needs user_scope for user-level permissions alongside bot scopes
    if app_id == "slack" and config.get("user_scopes"):
        params["user_scope"] = config["user_scopes"]

    auth_query = urllib.parse.urlencode(params)
    return RedirectResponse(f"{config['auth_url']}?{auth_query}")

@app.get("/callback/{app_id}")
async def callback(app_id: str, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        return HTMLResponse(f"<h1>Error</h1><p>{error}</p>")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
        
    if app_id not in APPS:
        raise HTTPException(status_code=404, detail="App not supported")
    
    config = APPS[app_id]
    session_id = state
    
    async with httpx.AsyncClient() as client:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{os.getenv('OPENDESK_PROXY_URL').rstrip('/')}/callback/{app_id}",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
        }
        headers = {"Accept": "application/json"}
        
        # Some apps require Basic Auth for exchange
        if app_id in ["spotify", "notion", "slack"]:
            auth_str = f"{config['client_id']}:{config['client_secret']}"
            headers["Authorization"] = f"Basic {base64.b64encode(auth_str.encode()).decode()}"

        try:
            response = await client.post(config["token_url"], data=data, headers=headers)
            response.raise_for_status()
            tokens = response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token", "")
    
    if session_id:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO tokens VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (session_id, app_id) 
                DO UPDATE SET access_token=$3, 
                refresh_token=$4, timestamp=$5
            """, session_id, app_id, 
                access_token, refresh_token, time.time())
    
    return HTMLResponse("""
<html>
<body style="font-family:sans-serif;text-align:center;
padding:50px;background:#1a1a2e;color:white;">
<h1 style="color:#1DB954">✅ Connected!</h1>
<p>You can now close this tab and return to Telegram.</p>
<p style="color:#888;font-size:14px">
OpenDesk has securely saved your access.</p>
</body>
</html>
""")

@app.get("/tokens/{session_id}/{app_id}")
async def get_tokens(session_id: str, app_id: str, force_refresh: bool = False):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM tokens WHERE session_id=$1 AND app_id=$2", 
            session_id, app_id
        )
        if row:
            access_token = row["access_token"]
            refresh_token = row["refresh_token"]
            
            # Refresh if older than 55 minutes (3300 seconds) OR if force_refresh is requested
            if (time.time() - row["timestamp"] >= 3300 or force_refresh) and refresh_token:
                # FIX: was OAUTH_CONFIGS (undefined) — correct variable is APPS
                config = APPS.get(app_id)
                if config:
                    data = {
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    }
                    if config.get("auth_style") == "body":
                        data["client_id"] = config["client_id"]
                        data["client_secret"] = config["client_secret"]
                        
                    headers = {}
                    if config.get("auth_style") == "header":
                        auth_str = f"{config['client_id']}:{config['client_secret']}"
                        headers["Authorization"] = f"Basic {base64.b64encode(auth_str.encode()).decode()}"
                        
                    try:
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(config["token_url"], data=data, headers=headers)
                            if resp.status_code == 200:
                                new_tokens = resp.json()
                                access_token = new_tokens.get("access_token", access_token)
                                refresh_token = new_tokens.get("refresh_token", refresh_token)
                                
                                await conn.execute("""
                                    UPDATE tokens SET access_token=$1, refresh_token=$2, timestamp=$3 
                                    WHERE session_id=$4 AND app_id=$5
                                """, access_token, refresh_token, time.time(), session_id, app_id)
                    except Exception as e:
                        print(f"Error refreshing {app_id} token: {e}")

            return {"access_token": access_token, "refresh_token": refresh_token}
            
    raise HTTPException(status_code=404, detail="Tokens not found")

@app.get("/health")
async def health_check():
    """Liveness + DB connectivity check for monitoring and diagnostics."""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "ok",
            "database": "ok",
            "proxy": "OpenDesk Auth Proxy",
            "apps_configured": [k for k, v in APPS.items() if v.get("client_id")]
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database": "error",
            "detail": str(e)
        }
