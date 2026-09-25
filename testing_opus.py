import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    tools=[
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "allowed_callers": ["direct"],
        }
    ],
    messages=[
        {
            "role": "user",
            "content": "Search the web for the latest news about the Mars rover and summarize it."
        }
    ],
)

print(response.content)
