import os
import json
from dotenv import load_dotenv
import anthropic

load_dotenv()
workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
headers = {"anthropic-workspace-id": workspace_id} if workspace_id else {}
client = anthropic.Anthropic(default_headers=headers)
MODEL = os.getenv("MODEL", "claude-haiku-5-5")

# OFF SWITCH: the agent can never call the API more than this many times
MAX_TURNS = 5

TOOLS = [
    {
        "name": "get_order_status",
        "description": "Look up the shipping status of a customer order by its order ID. "
                       "Use this whenever the user asks where their order is.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID, like 'A100'."}
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "issue_refund",
        "description": "Issue a full refund for an order. Only use this if the customer "
                       "asks for a refund AND the order has not shipped yet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID to refund."}
            },
            "required": ["order_id"],
        },
    },
]

ORDERS = {
    "A100": {"status": "shipped", "carrier": "UPS", "eta": "Oct 15"},
    "B200": {"status": "processing", "carrier": None, "eta": "Oct 20"},
}

def get_order_status(order_id):
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": f"No order found with ID {order_id}"}
    return order

def issue_refund(order_id):
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": f"No order found with ID {order_id}"}
    order["status"] = "refunded"
    return {"result": f"Refund issued for order {order_id}"}

# Maps the tool name Claude uses to the Python function that runs it
TOOL_FUNCTIONS = {
    "get_order_status": get_order_status,
    "issue_refund": issue_refund,
}

# HUMAN-IN-THE-LOOP GATE: tools that change things need a person to approve them
REQUIRES_APPROVAL = {"issue_refund"}

def ask_human(name, tool_input):
    answer = input(f"\n>>> Claude wants to run {name}({json.dumps(tool_input)}). Allow? (y/n): ")
    return answer.strip().lower() == "y"

def run_agent(question):
    messages = [{"role": "user", "content": question}]

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n[turn {turn}]")
        response = client.messages.create(
            model=MODEL, max_tokens=500, tools=TOOLS, messages=messages
        )

        # If Claude is NOT asking for a tool, we're done.
        if response.stop_reason != "tool_use":
            for block in response.content:
                if block.type == "text":
                    print(block.text)
            return

        # Save Claude's reply to the conversation history.
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"Claude wants: {block.name}({json.dumps(block.input)})")

            # The approval gate.
            if block.name in REQUIRES_APPROVAL and not ask_human(block.name, block.input):
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "The user denied this action.",
                    "is_error": True,
                })
                continue

            # Run the tool and save the result.
            result = TOOL_FUNCTIONS[block.name](**block.input)
            print(f"Result: {result}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        # Send all the tool results back to Claude.
        messages.append({"role": "user", "content": tool_results})

    print(f"\nOFF SWITCH: stopped after {MAX_TURNS} turns without a final answer.")

if __name__ == "__main__":
    try:
        run_agent("Order B200 is taking forever. Check on it, and if it hasn't "
                  "shipped, refund me.")
    except KeyboardInterrupt:
        print("\nEMERGENCY STOP: Ctrl+C pressed. No further actions were taken.")
