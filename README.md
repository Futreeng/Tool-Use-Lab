# Tool Use Lab: Build a Safe AI Agent, Step by Step

A beginner-friendly, hands-on lab for the Claude API. You'll go from your very first API call to a working AI agent that uses tools, asks a human before taking real actions, and has an automated grader that proves its safety gates work.

**Who this is for:** anyone who knows a little Python and wants to actually *build* with an AI API, not just read about it.

**What you'll build:** a customer-support agent that can look up orders and issue refunds, with a human approval gate in front of every refund.

**Time:** about 2 to 3 hours.

**Cost:** a few cents at most. The lab uses Claude Haiku, the smallest and cheapest model, and the grader runs on a fake Claude, so testing costs nothing.

---

> ## ⚠️ Safety first: this is a rule, not a suggestion
>
> Any time an AI model can take actions in the real world (refund money, send email, delete files), you need **two things**:
>
> 1. **A human in the loop.** A person approves every action that changes something.
> 2. **An off switch.** A hard limit that stops the agent no matter what it wants to do.
>
> In this lab, these are **mandatory gates, not optional extras.** You'll build both, and then you'll write tests that prove they work.

---

## Table of Contents

- [Setup](#setup)
- [Windows Gotchas](#windows-gotchas)
- [Step 1: Your First API Call](#step-1-your-first-api-call)
- [Step 2: Give Claude a Tool](#step-2-give-claude-a-tool)
- [Step 3: The Grader](#step-3-the-grader)
- [Lessons From Building This Lab](#lessons-from-building-this-lab)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

---

## Setup

### Get an API key (everyone)

1. Go to [console.anthropic.com](https://console.anthropic.com) and create an API key.
2. **Create the key inside a workspace.** If your key isn't tied to a workspace, every request needs an extra workspace ID. See [Troubleshooting](#troubleshooting).
3. Open **Billing → Limits** and set a low monthly spend limit. Real labs should never surprise anyone with a bill.

### Option A: GitHub Codespaces (easiest, nothing to install)

1. On this repo's GitHub page, click **Code → Codespaces → Create codespace**.
2. When asked, paste your API key into the `ANTHROPIC_API_KEY` secret. It's stored securely by GitHub and never written to a file.
3. Wait for the setup to finish. Python and every package are installed for you.
4. Skip ahead to [Step 1](#step-1-your-first-api-call).

### Option B: Your own computer

**Mac or Linux:**

```bash
git clone <this-repo-url>
cd tool-use-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
git clone <this-repo-url>
cd tool-use-lab
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

You'll know the environment is active when you see `(.venv)` at the start of your prompt.

Then create a file named `.env` in the project folder:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
MODEL=claude-haiku-5-5
```

The `.gitignore` file already keeps `.env` out of Git, so your key never gets uploaded. **Never remove `.env` from `.gitignore`.**

---

## Windows Gotchas

Every one of these happened for real while building this lab. If you're on Windows, read this list before you start. It will save you an hour.

| Problem | What's going on | Fix |
|---|---|---|
| Typing `python` opens the Microsoft Store | That's a Windows shortcut, not your real Python | Use `py` to create the venv. After activating, `python` works normally. |
| "Running scripts is disabled on this system" | Windows blocks scripts by default | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| "No such file or directory" for a file you made | Notepad saved it as `hello.py.txt` or `.env.txt` | Run `dir -Force` to see real names. Fix with `Rename-Item`. |
| Files seem to vanish | You're in the wrong folder, or created a folder inside a folder | Run `dir -Force` before running anything |
| Slow installs or locked-file errors | The project is inside OneDrive, which tries to sync thousands of files | Keep projects in a folder like `C:\dev` |
| Moved your project and nothing works | A virtual environment can't be moved | Delete `.venv` and create it again |
| `NameError` on a line like `dir -Force` | A terminal command got pasted into a `.py` file | Terminal commands go in the terminal. Python goes in the file. |
| `import anthropic` takes 7+ seconds | The SDK has thousands of small files, and antivirus scans each one | Harmless. The grader avoids it entirely (see Step 3). |
| Git warns "LF will be replaced by CRLF" | Windows and Mac end lines differently | The `.gitattributes` file in this repo handles it |

---

## Step 1: Your First API Call

**Goal:** send one message to Claude and get a reply, with friendly errors when something goes wrong.

**File:** `hello.py`

Run it:

```bash
python hello.py
```

✅ **Checkpoint:** you should see a one-sentence greeting and a token count, something like `Tokens used: 24 in, 41 out`.

### What just happened

- `load_dotenv()` reads your `.env` file so Python can see your key.
- `client.messages.create(...)` is the actual API call. It takes three things:
  - **model:** which Claude to use.
  - **max_tokens:** a ceiling on reply length, which also caps cost.
  - **messages:** the conversation, written as a list of turns.
- `response.content[0].text` pulls out the reply. Replies come back as a **list of content blocks**, and that detail matters a lot in Step 2.
- Every `except` block turns a scary error into one sentence that tells you what to fix. **That's the difference between a lab and a code sample.**

---

## Step 2: Give Claude a Tool

**Goal:** let Claude look up orders and issue refunds, safely.

**File:** `agent.py`

### The big idea

**Claude never runs a tool itself.** It can't. It sends back a request that says, in effect, "please call `get_order_status` with `A100`." **Your code** decides whether to run it. That's exactly why the safety gate lives in your code, not in the model.

### The three rules of tool use

Almost every tool-use bug breaks one of these:

1. **Save Claude's reply to the conversation history.** The API has no memory, so every call resends the whole conversation, including Claude's tool request.
2. **Label every tool result with the matching `tool_use_id`.** That's how Claude knows which request the result answers.
3. **Send tool results back in a `user` message.** From the API's point of view, your code speaks on the user's side of the conversation.

### The agent loop

Real tasks can need several tool calls in a row. To answer "check my order, and refund me if it hasn't shipped," Claude first looks up the order, then asks for the refund. So the round trip runs in a loop until Claude stops asking for tools (`stop_reason` is no longer `"tool_use"`).

### The safety gates

| Gate | What it does | Where it lives |
|---|---|---|
| **Human approval** | Any tool in `REQUIRES_APPROVAL` pauses and asks a person y/n before running | The `# HUMAN-IN-THE-LOOP GATE` block |
| **Turn limit** | The agent can never call the API more than `MAX_TURNS` times | The `for` loop in `run_agent` |
| **Emergency stop** | Ctrl+C at any moment stops cleanly, with no further actions | The `except KeyboardInterrupt` at the bottom |
| **Unknown tools** | If Claude asks for a tool that doesn't exist, it gets an error back instead of crashing the program | The `# Safety:` block |

Notice the design choice: `get_order_status` only *looks*, so it runs without asking. `issue_refund` *changes* data, so it always asks. **Looking versus acting** is the core decision for any agent.

### Try all the safety paths

Run `python agent.py` several times:

1. **Answer `y`.** Claude checks the order, you approve, and the refund goes through.
2. **Answer `n`.** No refund happens, and Claude explains that a reviewer declined it.
3. **Set `MAX_TURNS = 1`.** The off switch fires. (Set it back to 5 afterward.)
4. **Press Ctrl+C at the approval prompt.** You get a clean emergency stop.

A safety gate you haven't tested with a **no** is a gate you're only hoping works.

### Bonus lesson: tool results are part of your prompt

The first version of this lab told Claude `"The user denied this action."` Claude got confused: the *customer* had asked for the refund, so why would the user deny it? It offered to try again.

The fix was one string: `"A human reviewer declined this action. It was not performed. Do not retry it..."` After that change, Claude explained the situation correctly and pointed the customer to support.

**The safety gate stopped the action both times. Clear wording is what made Claude behave sensibly afterward.** You need both.

---

## Step 3: The Grader

**Goal:** prove the safety gates work, automatically, for free, every time.

**File:** `test_agent.py`

Run it:

```bash
pytest -v
```

✅ **Checkpoint:** `7 passed` in well under a second, with no API key or internet needed.

### How it works

- **A fake Claude.** `FakeClient` has the same shape as the real client, but it returns scripted replies. `run_agent` can't tell the difference.
- **Why that's possible:** `run_agent` takes the `client` and the `approve` function as inputs instead of grabbing them itself. Real runs pass in real Claude and a real human. Tests pass in fakes. (Notice that `approve` has no default value, so you *can't* run the agent without deciding who approves its actions.)
- **The tests check the data, not just the printed text.** Did the order actually get refunded or not? Printed text can lie. Data is the truth.
- **Lazy import:** `agent.py` only imports the `anthropic` SDK inside `make_client()`. Tests never call that function, so they never pay the SDK's load time. On one Windows machine, this cut the test run from about 9 seconds to 0.25.

### ⚡ Exercise: Break it on purpose

A test that can't fail proves nothing. Let's prove these tests can catch the scariest possible bug: a fake approval gate.

1. Commit your work first, so you can get back to it safely.
2. In `agent.py`, find the `# HUMAN-IN-THE-LOOP GATE` block and delete the `continue` on its last line. Save.
3. Run `pytest -v`. Two tests should **fail**:
   - `assert 'refunded' == 'processing'`: the human said no, and the refund happened anyway.
   - `assert 2 == 1`: Claude got two answers to one request, a denial *and* a success.
4. Undo the damage with `git restore agent.py`, then run `pytest -v` to get back to 7 passed.

**One missing word turns "no" into "yes."** The grader is what catches it.

---

## Lessons From Building This Lab

These are real problems hit while building this, kept here because they're exactly what learners run into.

- **The workspace error.** Newer API keys can be tied to a person instead of a workspace. Those keys return a `400` error asking for an `anthropic-workspace-id` header. A 400 rather than a 401 is actually good news: it means the key itself is valid. The lab now handles both kinds of key and explains the fix in plain English.
- **The weak test.** The first version of the denial test only checked the *first* tool result. With the gate broken, the code sent two results (a denial, then a success), and the test still passed. Running the break-it-on-purpose exercise exposed it. The fix was to assert there's **exactly one** result per tool request. Lesson: a test can pass while checking the wrong thing, and the only way to know is to break the code and see whether the test notices.
- **The slow grader.** Tests took 9 seconds even though each test took 0.01. Measuring showed `import anthropic` alone took 7 seconds, spread across 2,785 small modules, with no single slow package. The fix was a lazy import so tests never load the SDK.
- **The confusing denial.** Wording a denial as "the user denied this" confused Claude, because the user had asked for the action. Rewording it as a human reviewer's decision fixed Claude's behavior without changing the gate at all.

---

## Troubleshooting

| You see | It means | Fix |
|---|---|---|
| `No API key found` | `.env` is missing or misnamed | Check with `dir -Force` (Windows) or `ls -a` (Mac/Linux) |
| `Your API key was rejected` | The key is wrong or was deleted | Create a new key in the Console |
| `Your API key needs a workspace` | Your key isn't scoped to a workspace | Create a key inside a workspace, **or** add `ANTHROPIC_WORKSPACE_ID=wrkspc_...` to `.env` |
| `Model '...' wasn't found` | The model name in `.env` is wrong | Check the `MODEL` line |
| `ModuleNotFoundError: No module named 'anthropic'` | Packages aren't installed in this environment | Activate `.venv`, then run `pip install -r requirements.txt` |
| `SyntaxError` with `^^^^` arrows | A paste went wrong, often two lines glued together | Look right at the arrows. Replace the whole file rather than editing pieces. |
| The agent seems frozen | It's waiting for your y/n answer | Look for the `>>> Allow? (y/n)` prompt |

---

## Project Structure

```
tool-use-lab/
├── hello.py                  Step 1: first API call
├── agent.py                  Step 2: tool-use agent with safety gates
├── test_agent.py             Step 3: grader with a fake Claude
├── requirements.txt          Packages the lab needs
├── .devcontainer/            Codespaces setup
├── .env                      Your API key (never committed)
├── .gitignore                Keeps secrets and junk out of Git
└── .gitattributes            Consistent line endings on every OS
```

---

**Remember:** the human approval gate and the off switches are mandatory in every version of this agent, including any you build next. Give a model the ability to act, and you owe the world a way to say no and a way to stop it.
