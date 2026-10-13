import os
import sys
from dotenv import load_dotenv
import anthropic

load_dotenv()

if not os.getenv("ANTHROPIC_API_KEY"):
    sys.exit("No API key found. Did you create the .env file? See Step 1c.")

workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
headers = {"anthropic-workspace-id": workspace_id} if workspace_id else {}
client = anthropic.Anthropic(default_headers=headers)

MODEL = os.getenv("MODEL", "claude-haiku-5-5")

try:
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[
            {"role": "user", "content": "Say hello to a new lab student in one sentence."}
        ],
    )
except anthropic.BadRequestError as e:
    if "workspace" in str(e):
        sys.exit("Your API key needs a workspace. Either create a key inside a workspace "
                 "in the Console, or add ANTHROPIC_WORKSPACE_ID to .env. See Step 1c.")
    sys.exit(f"The API rejected the request: {e.message}")
except anthropic.AuthenticationError:
    sys.exit("Your API key was rejected. Double check it in .env.")
except anthropic.NotFoundError:
    sys.exit(f"Model '{MODEL}' wasn't found. Check the MODEL line in .env.")
except anthropic.RateLimitError:
    sys.exit("Rate limited. Wait a minute and try again.")
except anthropic.APIConnectionError:
    sys.exit("Couldn't reach the API. Check your internet connection.")

print(response.content[0].text)
print(f"\nTokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")