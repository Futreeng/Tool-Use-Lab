import os
import sys
import json
from dotenv import load_dotenv

DEFAULT_MODEL = "claude-haiku-5-5"

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

def make_client():
    import anthropic
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("No API key found. Did you create the .env file? See Step 1c.")
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    headers = {"anthropic-workspace-id": workspace_id} if workspace_id else {}
    return anthropic.Anthropic(default_headers=headers)

def run_agent(question, client, approve, model=DEFAULT_MODEL, max_turns=MAX_TURNS):
    """Run the agent loop. Returns Claude's final answer, or None if the off switch fires."""
    messages = [{"role": "user", "content": question}]

    for turn in range(1, max_turns + 1):
        print(f"\n[turn {turn}]")
        response = client.messages.create(
            model=model, max_tokens=500, tools=TOOLS, messages=messages
        )

        # TODO 1: If Claude is NOT asking for a tool, we're done.
        # Hint: if response.stop_reason isn't "tool_use", join the .text of every
        # text block in response.content, print it, and return it.

        # TODO 2: Save Claude's reply to the conversation history (Rule 1).
        # Hint: one line. Append a message with role "assistant".

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"Claude wants: {block.name}({json.dumps(block.input)})")

            # Safety: Claude asked for a tool that doesn't exist (provided for you)
            if block.name not in TOOL_FUNCTIONS:
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": f"Unknown tool: {block.name}", "is_error": True,
                })
                continue

            # TODO 3: The HUMAN-IN-THE-LOOP GATE. This is mandatory, not optional.
            # Hint: if block.name is in REQUIRES_APPROVAL and approve(block.name, block.input)
            # returns False, append this result and then `continue` (don't forget it!):
            #   {"type": "tool_result", "tool_use_id": block.id,
            #    "content": "A human reviewer declined this action. It was not performed. "
            #               "Do not retry it; explain to the customer that it needs review.",
            #    "is_error": True}

            # TODO 4: Run the tool and save the result (Rule 2).
            # Hint: call TOOL_FUNCTIONS[block.name](**block.input), print the result, then
            # append {"type": "tool_result", "tool_use_id": block.id,
            #         "content": json.dumps(result)}

        # TODO 5: Send all the tool results back to Claude (Rule 3).
        # Hint: one line. Append a message with role "user".

    print(f"\nOFF SWITCH: stopped after {max_turns} turns without a final answer.")
    return None

if __name__ == "__main__":
    client = make_client()
    model = os.getenv("MODEL", DEFAULT_MODEL)
    try:
        run_agent(
            "Order B200 is taking forever. Check on it, and if it hasn't shipped, refund me.",
            client=client,
            approve=ask_human,
            model=model,
        )
    except KeyboardInterrupt:
        print("\nEMERGENCY STOP: Ctrl+C pressed. No further actions were taken.")