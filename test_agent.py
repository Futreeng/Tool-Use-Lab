import copy
from types import SimpleNamespace

import pytest

import agent


# ---------- A fake Claude ----------
# These helpers build objects shaped like real API replies:
# same attribute names (.type, .text, .name, .input, .id), no network.

def text_block(text):
    return SimpleNamespace(type="text", text=text)

def tool_block(name, tool_input, block_id):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=block_id)

def reply(stop_reason, *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


class FakeClient:
    """Pretends to be anthropic.Anthropic.
    Returns scripted replies in order and records every call the agent makes."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []
        self.messages = self  # so client.messages.create(...) works

    def create(self, **kwargs):
        # Snapshot what the agent sent, since it keeps appending to the same list
        self.calls.append(copy.deepcopy(kwargs))
        if not self._replies:
            raise AssertionError("The agent called Claude more times than the test scripted.")
        return self._replies.pop(0)


# ---------- Test setup ----------

@pytest.fixture(autouse=True)
def fresh_orders():
    """Reset the fake database after every test so tests can't affect each other."""
    saved = copy.deepcopy(agent.ORDERS)
    yield
    agent.ORDERS.clear()
    agent.ORDERS.update(saved)

def always_yes(name, tool_input):
    return True

def always_no(name, tool_input):
    return False

def refund_script():
    """Claude checks order B200, asks to refund it, then gives a final answer."""
    return [
        reply("tool_use", tool_block("get_order_status", {"order_id": "B200"}, "t1")),
        reply("tool_use", tool_block("issue_refund", {"order_id": "B200"}, "t2")),
        reply("end_turn", text_block("All done.")),
    ]


# ---------- The tests ----------

def test_denied_refund_does_not_change_order():
    fake = FakeClient(refund_script())
    agent.run_agent("Refund B200", client=fake, approve=always_no)
    assert agent.ORDERS["B200"]["status"] == "processing"

def test_denial_is_reported_back_to_claude():
    fake = FakeClient(refund_script())
    agent.run_agent("Refund B200", client=fake, approve=always_no)
    results_sent = fake.calls[2]["messages"][-1]["content"]
    assert len(results_sent) == 1  # exactly one result per tool request
    assert results_sent[0]["tool_use_id"] == "t2"
    assert results_sent[0].get("is_error") is True

def test_approved_refund_changes_order():
    fake = FakeClient(refund_script())
    agent.run_agent("Refund B200", client=fake, approve=always_yes)
    assert agent.ORDERS["B200"]["status"] == "refunded"

def test_read_only_tool_never_asks_for_approval():
    asked = []
    def spy(name, tool_input):
        asked.append(name)
        return True
    fake = FakeClient([
        reply("tool_use", tool_block("get_order_status", {"order_id": "A100"}, "t1")),
        reply("end_turn", text_block("It shipped.")),
    ])
    agent.run_agent("Where is A100?", client=fake, approve=spy)
    assert asked == []

def test_off_switch_stops_the_loop():
    endless = [
        reply("tool_use", tool_block("get_order_status", {"order_id": "A100"}, f"t{i}"))
        for i in range(10)
    ]
    fake = FakeClient(endless)
    result = agent.run_agent("Loop forever", client=fake, approve=always_yes, max_turns=3)
    assert result is None
    assert len(fake.calls) == 3

def test_unknown_tool_is_reported_not_crashed():
    fake = FakeClient([
        reply("tool_use", tool_block("delete_database", {}, "t1")),
        reply("end_turn", text_block("I can't do that.")),
    ])
    result = agent.run_agent("Wipe everything", client=fake, approve=always_yes)
    result_sent = fake.calls[1]["messages"][-1]["content"][0]
    assert result_sent["is_error"] is True
    assert result == "I can't do that."

def test_final_answer_is_returned():
    fake = FakeClient([reply("end_turn", text_block("Hello!"))])
    assert agent.run_agent("Hi", client=fake, approve=always_no) == "Hello!"