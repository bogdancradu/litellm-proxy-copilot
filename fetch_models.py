import requests
import os
import time

def get_github_copilot_token(github_pat):
    """Exchanges a GitHub PAT for a Copilot-specific internal token (gno)."""
    print(f"[*] Exchanging GitHub PAT for Copilot Token...")
    
    # This endpoint is internal and used by the VS Code extension
    auth_url = "https://api.github.com/copilot_internal/v2/token"
    headers = {
        "Authorization": f"token {github_pat}",
        "Accept": "application/json",
        "User-Agent": "GitHubCopilot/1.155.0",
        "Editor-Version": "vscode/1.85.1"
    }

    try:
        response = requests.get(auth_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("[+] Successfully obtained Copilot Token!")
            return data.get("token")
        else:
            print(f"[!] Failed to get Copilot Token. Status: {response.status_code}")
            print(f"[!] Response: {response.text}")
            print("\n[!] Make sure your PAT has access to Copilot (usually requires an active subscription).")
            return None
    except Exception as e:
        print(f"[!] Error getting token: {e}")
        return None

def fetch_models(copilot_token):
    """Uses the Copilot token to fetch available models."""
    print(f"\n[*] Fetching available models from GitHub Copilot API...")
    
    url = "https://api.githubcopilot.com/models"
    headers = {
        "Authorization": f"Bearer {copilot_token}",
        "Editor-Version": "vscode/1.85.1",
        "Editor-Plugin-Version": "copilot/1.155.0",
        "User-Agent": "GithubCopilot/1.155.0",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            print(f"[+] Found {len(models)} models:\n")
            print(f"{'ID':<40} {'Capabilities':<20}")
            print("-" * 60)
            for model in models:
                model_id = model.get('id')
                # Try to guess capabilities based on name
                caps = "Chat/Code"
                if "embedding" in model_id:
                    caps = "Embeddings"
                print(f"{model_id:<40} {caps:<20}")
            return models
        else:
            print(f"[!] Failed to fetch models. Status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"[!] Error fetching models: {e}")

if __name__ == "__main__":
    # 1. Try to get PAT from file (User preference)
    # Uses os.path.expanduser("~") to get $HOME/user profile directory cross-platform
    token_path = os.path.join(os.path.expanduser("~"), ".config", "litellm", "github_copilot", "access-token")
    pat = None
    
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r') as f:
                pat = f.read().strip()
            print(f"[*] Using token from: {token_path}")
        except Exception as e:
            print(f"[-] Could not read {token_path}: {e}")

    # 2. Fallback to Environment Variable
    if not pat:
        pat = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        if pat:
            print("[*] Using token from environment variable GITHUB_PERSONAL_ACCESS_TOKEN")
    
    if not pat:
        print("[!] Error: No GitHub Token found.")
        print(f"[!]   Checked file: {token_path}")
        print("[!]   Checked env var: GITHUB_PERSONAL_ACCESS_TOKEN")
        exit(1)

    # 2. Get the internal Copilot token
    copilot_token = get_github_copilot_token(pat)

    # 3. List models
    if copilot_token:
        fetch_models(copilot_token)
