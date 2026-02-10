import asyncio
import os
import json
import time
import requests
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Using the LiteLLM Client ID for GitHub Copilot access
CLIENT_ID = "Iv1.b507a08c87ecfe98"
TOKEN_DIR = os.path.expanduser("~/.config/litellm/github_copilot")
TOKEN_FILE = os.path.join(TOKEN_DIR, "access-token")
API_KEY_FILE = os.path.join(TOKEN_DIR, "api-key.json")

app = FastAPI()

def get_common_headers(access_token=None):
    headers = {
        "accept": "application/json",
        "editor-version": "vscode/1.85.1",
        "editor-plugin-version": "copilot/1.155.0",
        "user-agent": "GithubCopilot/1.155.0",
        "accept-encoding": "gzip,deflate,br",
    }
    if access_token:
        headers["authorization"] = f"token {access_token}"
    return headers

@app.get("/github", response_class=HTMLResponse)
async def github_auth():
    """Starts the GitHub Device Flow Authentication."""
    try:
        data = {
            "client_id": CLIENT_ID, 
            "scope": "read:user"
        }
        response = None
        last_error = None
        for attempt in range(4):
            try:
                response = requests.post(
                    "https://github.com/login/device/code",
                    headers=get_common_headers(),
                    json=data,
                    timeout=15
                )
                if response.status_code == 503:
                    last_error = f"503 Service Unavailable (attempt {attempt + 1})"
                    time.sleep(2 + attempt)
                    continue
                response.raise_for_status()
                last_error = None
                break
            except Exception as e:
                last_error = str(e)
                time.sleep(2 + attempt)

        if last_error:
            raise RuntimeError(
                "GitHub device code endpoint unavailable. "
                "Please try again in a few minutes."
            )
        auth_data = response.json()
        
        device_code = auth_data.get("device_code")
        user_code = auth_data.get("user_code")
        verification_uri = auth_data.get("verification_uri")
        interval = auth_data.get("interval", 5)

        asyncio.create_task(poll_for_token(device_code, interval))

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>LiteLLM GitHub Auth</title>
            <style>
                body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; text-align: center; background: #f6f8fa; }}
                .card {{ background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
                h1 {{ color: #24292f; margin-bottom: 10px; }}
                .code {{ font-size: 32px; font-family: monospace; letter-spacing: 2px; background: #f6f8fa; padding: 15px; margin: 20px 0; border-radius: 6px; border: 1px dashed #d0d7de; font-weight: bold; color: #0969da; }}
                button {{ background: #2da44e; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: 0.2s; }}
                button:hover {{ background: #2c974b; box-shadow: 0 2px 8px rgba(46,164,78,0.2); }}
                p {{ color: #57606a; line-height: 1.5; }}
                .step {{ margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>GitHub Authentication</h1>
                <p>Authorize this LiteLLM Proxy to access GitHub Copilot models.</p>
                
                <div class="code" id="userCode">{user_code}</div>
                
                <p class="step">1. Click the button to copy code & open GitHub.<br>2. Paste the code and authorize.</p>
                
                <button onclick="startAuth()">Copy Code & Open GitHub</button>
                
                <div id="status" style="margin-top: 20px; color: #57606a; font-size: 14px;">Waiting for authorization...</div>
            </div>

            <script>
                function startAuth() {{
                    const code = document.getElementById('userCode').innerText;
                    navigator.clipboard.writeText(code).then(() => {{
                        document.getElementById('status').innerText = "Code copied! Opening GitHub...";
                        setTimeout(() => {{
                            window.open('{verification_uri}', '_blank');
                        }}, 500);
                    }});
                }}
            </script>
        </body>
        </html>
        """
        return html

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in /github endpoint: {e}")
        return HTMLResponse(
            content=(
                "<h1>Error starting auth</h1>"
                f"<p>{str(e)}</p>"
                "<p>Please retry shortly or check network/proxy access to github.com.</p>"
            ),
            status_code=500
        )

async def poll_for_token(device_code, interval):
    """Polls GitHub for the access token. Once received, exchanges it for a Copilot token (if needed) and saves it."""
    print(f"[*] Polling for token (Interval: {interval}s)...")
    
    polling_url = "https://github.com/login/oauth/access_token"
    # Authenticator.py uses JSON payload for polling too
    data = {
        "client_id": CLIENT_ID,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
    }

    # Poll for up to 5 minutes
    for _ in range(60): 
        await asyncio.sleep(interval)
        
        try:
            # Use get_common_headers() and json=data 
            res = requests.post(polling_url, headers=get_common_headers(), json=data)
            res_data = res.json()
            
            error = res_data.get("error")
            if error:
                if error == "authorization_pending":
                    continue
                elif error == "slow_down":
                    interval += 5
                    continue
                elif error == "expired_token":
                    print("[!] Device code expired.")
                    break
                else:
                    print(f"[!] Polling error: {error}")
                    break
            
            access_token = res_data.get("access_token")
            if access_token:
                print("[+] GitHub Access Token received!")
                save_token(access_token)
                
                # Also retrieve and save the Copilot API Key
                retrieve_copilot_token(access_token)
                
                print("[*] Token saved. LiteLLM should pick it up.")
                
                break
                
        except Exception as e:
            print(f"[!] Polling exception: {e}")
            break

def save_token(token):
    """Saves the token to the path LiteLLM expects."""
    try:
        os.makedirs(TOKEN_DIR, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
            
        print(f"[+] Token saved to {TOKEN_FILE}")
        
    except Exception as e:
        print(f"[!] Failed to save token: {e}")

def retrieve_copilot_token(access_token):
    """Exchanges the OAuth token for a Copilot API token and saves it."""
    print("[*] Retrieving Copilot API Token...")
    try:
        url = "https://api.github.com/copilot_internal/v2/token"
        headers = get_common_headers(access_token)
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            api_key_data = response.json()
            # The response usually contains 'token', 'expires_at', etc.
            # We save the entire JSON response as api-key.json, which LiteLLM expects.
            
            with open(API_KEY_FILE, "w") as f:
                json.dump(api_key_data, f)
            print(f"[+] Copilot API Key saved to {API_KEY_FILE}")
        else:
            print(f"[!] Failed to retrieve Copilot Token: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"[!] Exception retrieving Copilot Token: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4001)
