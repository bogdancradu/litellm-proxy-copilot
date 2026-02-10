import litellm

# Use the master key defined in docker-compose.yml
# Use 127.0.0.1 to avoid potential IPv6 issues
response = litellm.completion(
    model="litellm_proxy/github_copilot/gpt-4.1",
    messages=[{"role": "user", "content": "Explain quantum computing in simple terms."}],
    api_base="http://127.0.0.1:4000",
    api_key="sk-1234"
)

print(response.choices[0].message.content)