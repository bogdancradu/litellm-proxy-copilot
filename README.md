# LiteLLM Proxy for GitHub Copilot

This repository sets up a self-hosted API that proxies requests to GitHub Copilot's models (like Claude Opus, Gemini, GPT 4) using a standard OpenAI-compatible interface. It uses [LiteLLM](https://docs.litellm.ai/) to handle the routing and protocol translation.

## Features

- **GitHub Copilot Access**: Use Copilot models via a standard API endpoint (`http://localhost:4000`).
- **One-Click Auth**: Includes a helper service (`http://localhost:4001`) to handle the GitHub Device Authorization Flow from your browser.
- **Smart Fallbacks**: Primary/primary-catch-all routing is configured so requests try the configured model chain when a model returns quota/errors. Current recommended chain:
  - `github_copilot/claude-opus-4.6` -> `github_copilot/gemini-3-pro-preview` -> `github_copilot/gpt-5-mini` (final fallback)
- **MCP Support**: Pre-configured Model Context Protocol servers (Memory, Filesystem) and semantic tool routing.

## Prerequisites

- **Docker** and **Docker Compose**
- A GitHub account with an active Copilot subscription

## Quick Start

### 1. Start the Services

Run the stack including the Proxy, Authentication Service, and Database:

```bash
docker compose up -d --build
```

### 2. Authenticate with GitHub

The proxy needs a GitHub token to access the models. We've included an authentication helper service.

1.  Open your browser to: **[http://localhost:4001/github](http://localhost:4001/github)**
2.  Click the button to **Copy Code** and open GitHub.
3.  Paste the code on the GitHub activation page and authorize the application.
4.  Once authorized, the token will be automatically saved to `./litellm_data`, and the LiteLLM proxy will pick it up.

*(You can watch the logs of the `litellm` container to see when the token is detected and the proxy starts).*

```bash
docker logs -f litellm-proxy
```

### 3. Use the API

The API behaves like a standard OpenAI endpoint.

**Base URL**: `http://localhost:4000`
**API Key**: `sk-1234` (default master key)

#### Python Example

```python
import litellm

response = litellm.completion(
    model="litellm_proxy/github_copilot/claude-opus-4.6",
    messages=[{"role": "user", "content": "Explain quantum computing in simple terms."}],
    api_base="http://localhost:4000",
    api_key="sk-1234"
)
print(response.choices[0].message.content)
```

#### Curl Example

```bash
curl -X POST "http://localhost:4000/v1/chat/completions" \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "github_copilot/claude-opus-4.6",
    "messages": [{ "role": "user", "content": "Explain quantum computing in simple terms." }]
  }'
```

## Using with Claude Code CLI

Claude Code is Anthropic's agentic coding tool that runs in your terminal. By default it connects directly to the Anthropic API, but you can point it at this LiteLLM proxy instead — letting you use your GitHub Copilot subscription to access Claude models without a separate Anthropic API key.

### Why use this setup?

GitHub Copilot subscriptions include a monthly quota of "premium requests" that cover models like Claude Opus and Gemini Pro. By routing Claude Code through this proxy you can use those included premium requests instead of paying for Anthropic API credits separately. When your premium request quota is exhausted, the proxy's fallback chain kicks in automatically — requests will cascade through the models defined in `config.yaml` and ultimately land on the last-resort fallback (by default `gpt-5-mini`) so your workflow doesn't break mid-session.

### Step 1: Install Claude Code

If you haven't already, install Claude Code via npm:

```bash
npm install -g @anthropic-ai/claude-code
```

> Requires Node.js v18+. See the [Claude Code docs](https://docs.claude.com/en/docs/claude-code/overview) for full installation details.

### Step 2: Make sure the proxy is running and authenticated

Follow the [Quick Start](#quick-start) steps above so the LiteLLM proxy is up on `http://localhost:4000` and you've completed the GitHub device auth flow.

### Step 3: Configure Claude Code to use the proxy

Set the following environment variables to redirect Claude Code to your local proxy instead of the Anthropic API:

```bash
export ANTHROPIC_BASE_URL=http://localhost:4000/v1
export ANTHROPIC_API_KEY=sk-1234
export ANTHROPIC_MODEL=github_copilot/claude-opus-4.6
```

You can add these to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) so they persist across sessions:

```bash
# LiteLLM proxy for Claude Code (GitHub Copilot backend)
echo 'export ANTHROPIC_BASE_URL=http://localhost:4000/v1' >> ~/.zshrc
echo 'export ANTHROPIC_API_KEY=sk-1234' >> ~/.zshrc
echo 'export ANTHROPIC_MODEL=github_copilot/claude-opus-4.6' >> ~/.zshrc
source ~/.zshrc
```

### Step 4: Launch Claude Code

Start Claude Code as usual from any project directory:

```bash
claude
```

Claude Code will now route all requests through the LiteLLM proxy, which forwards them to GitHub Copilot's model endpoints.

### How fallbacks work with Claude Code

The proxy's fallback chain is transparent to Claude Code — it simply sees a standard API response regardless of which backend model ultimately served it.

Here's what happens when you hit your Copilot premium request quota:

1. **Primary model** (`claude-opus-4.6`) — used while you have premium requests remaining.
2. **First fallback** (`gemini-3-pro-preview`) — the proxy automatically retries with this model if the primary returns a quota or rate-limit error.
3. **Last-resort fallback** (`gpt-5-mini`) — if the first fallback also fails, this model handles the request. It has the broadest availability and is least likely to be quota-limited.

The exact fallback chain is defined in `config.yaml` under the `fallbacks` key. You can customize the order or swap models to match your preference:

```yaml
# Example fallback configuration in config.yaml
model_list:
  - model_name: "github_copilot/claude-opus-4.6"
    litellm_params:
      model: "github_copilot/claude-opus-4.6"
    fallbacks:
      - "github_copilot/gemini-3-pro-preview"
      - "github_copilot/gpt-5-mini"   # last resort
```

> **Note:** When a fallback model handles a request, Claude Code won't notify you — the response will simply come from whichever model was available. If you notice differences in response quality or style, check the proxy logs (`docker compose logs -f litellm`) to see which model actually served each request.

### Switching back to the Anthropic API

To go back to using the Anthropic API directly, unset the environment variables:

```bash
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_API_KEY
unset ANTHROPIC_MODEL
```

Or remove the lines from your shell profile and restart your terminal.

## Running Locally (Without Docker)

If you need to run the scripts or proxy outside of Docker:

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Auth Server**:
    ```bash
    python run_proxy.py
    ```
    (Then visit `http://localhost:4001/github` to authenticate)

3.  **Run LiteLLM**:
    ```bash
    litellm --config config.yaml --detailed_debug
    ```

## Configuration

- **`docker-compose.yml`**: Defines the services (`litellm`, `github-auth`, `db`). The compose file now exposes an environment variable `CONFIG_TYPE` which the container can use to choose between `config-standard.yaml` and `config-premium.yaml` if you add them to the project.
- **`config.yaml`**: Configures the active model routing and fallback chains. By default the catch-all (`"*"`) routes to `claude-opus-4.6` and has an explicit `fallbacks` list so quota errors fall through to `gemini-3-pro-preview` and finally `gpt-5-mini`.
- **`run_proxy.py`**: The FastAPI helper that handles the GitHub Device Flow and saves tokens under `litellm_data`.

## Logging, Admin UI, and Troubleshooting

- Request/Response payloads: to preserve request/response payloads (useful for the admin UI or debugging), set in `config.yaml`:

```yaml
litellm_settings:
  drop_params: false    # preserve request/response parameters
  json_logs: true      # write logs as JSON for the admin UI / log ingestion
```

- Security note: enabling `drop_params: false` will include potentially sensitive data in logs. If you need to preserve payloads but sanitize specific fields, add a custom callback to strip or redact fields before deployment.

- Unsupported params / 500 errors: Some target providers (for example `gpt-5-mini` via the `github_copilot` wrapper) may reject provider-specific params such as `thinking`. If you see errors like:

```
UnsupportedParamsError: github_copilot does not support parameters: ['thinking']
```

  Options to fix:
  - Set `drop_params: true` to drop all extra params before calls (safe but loses full request payloads).
  - Add a small callback that strips only problematic params for specific fallback targets (e.g., remove `thinking` when routing to `gpt-5-mini`). This preserves most request data while avoiding provider errors.

- Fallback not happening / "Available Model Group Fallbacks=None":
  - Ensure the exact model id returned by the upstream (for example `claude-sonnet-4-5-20250929`) is present in your `config.yaml` with a `fallbacks` list, or the catch-all route (`"*"`) includes a `fallbacks` chain. The router uses the `fallbacks` defined on the selected model entry — if that model wasn't defined, LiteLLM will show `Fallbacks=None`.

- To enable verbose runtime details for debugging add:

```yaml
litellm_settings:
  set_verbose: true
```

- Tail logs from the container to watch JSON events (useful for validating payload content):

```bash
docker compose logs -f litellm
```