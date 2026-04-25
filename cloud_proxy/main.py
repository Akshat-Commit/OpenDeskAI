import os
import base64
import httpx
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="OpenDesk Universal Auth Proxy")

# MASTER CONFIGURATION
# In production, these should be set in your Cloud Provider's Environment Variables (Vercel/Render)
APPS = {
    "spotify": {
        "auth_url": "https://accounts.spotify.com/authorize",
        "token_url": "https://accounts.spotify.com/api/token",
        "scopes": "user-modify-playback-state user-read-playback-state user-read-currently-playing",
        "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scopes": "repo workflow",
        "client_id": os.getenv("GITHUB_CLIENT_ID"),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "scopes": "",
        "client_id": os.getenv("NOTION_CLIENT_ID"),
        "client_secret": os.getenv("NOTION_CLIENT_SECRET"),
    },
    "gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": "https://mail.google.com/ https://www.googleapis.com/auth/gmail.send",
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": "channels:read chat:write groups:read im:read",
        "client_id": os.getenv("SLACK_CLIENT_ID"),
        "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
    }
}

@app.get("/")
async def root():
    return {"message": "OpenDesk Auth Proxy is running"}

@app.get("/login/{app_id}")
async def login(app_id: str, port: int = 8888):
    if app_id not in APPS:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not supported")
    
    config = APPS[app_id]
    if not config["client_id"]:
        raise HTTPException(status_code=500, detail=f"Master Client ID for {app_id} is not configured on server")

    params = {
        "client_id": config["client_id"],
        "response_type": "code",
       "redirect_uri": f"{os.getenv('PROXY_URL').rstrip('/')}/callback/{app_id}",
        "state": str(port), # Pass the local user's port through the state
    }
    
    if config["scopes"]:
        params["scope"] = config["scopes"]
        
    if app_id == "gmail":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
        
    auth_query = urllib.parse.urlencode(params)
    return RedirectResponse(f"{config['auth_url']}?{auth_query}")

@app.get("/callback/{app_id}")
async def callback(app_id: str, code: Optional[str] = None, state: Optional[str] = "8888", error: Optional[str] = None):
    if error:
        return {"error": error}
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
        
    if app_id not in APPS:
        raise HTTPException(status_code=404, detail="App not supported")
    
    config = APPS[app_id]
    local_port = state # The port we passed earlier
    
    async with httpx.AsyncClient() as client:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{os.getenv('PROXY_URL').rstrip('/')}/callback/{app_id}",
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
    
    # Redirect back to the user's local machine
    return RedirectResponse(
        url=f"http://localhost:{local_port}/callback?access_token={access_token}&refresh_token={refresh_token}&app_id={app_id}"
    )
