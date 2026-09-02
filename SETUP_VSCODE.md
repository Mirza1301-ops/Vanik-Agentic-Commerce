# Running Vanik in VS Code

Written for someone who hasn't used VS Code before. Windows, macOS and Linux
commands are given wherever they differ.

There is nothing to install with pip. Vanik uses only what ships with Python.

---

## 1. Install the two things you need

**Python 3.10 or newer.** Check whether you already have it. Open a terminal —
on Windows press the Windows key, type `powershell`, hit Enter; on macOS press
Cmd+Space, type `terminal`, hit Enter — and run:

```
python --version          # Windows
python3 --version         # macOS and Linux
```

If you see `Python 3.10` or higher, you're set. If not, get it from
[python.org/downloads](https://www.python.org/downloads/).

> **Windows, do not skip this.** On the first screen of the installer there is a
> checkbox at the bottom that says **"Add python.exe to PATH"**. Tick it before
> clicking Install. Almost every "python is not recognised" problem is this
> checkbox.

**VS Code.** Download from [code.visualstudio.com](https://code.visualstudio.com/)
and install it with the defaults.

---

## 2. Open the project

Unzip `vanik_project.zip` somewhere sensible — `Documents/vanik` is fine. Avoid
folder names with spaces or accents; they cause odd errors later.

In VS Code: **File → Open Folder**, and pick the `vanik` folder itself, not the
folder containing it. You should see `run_demo.py`, `tests.py`, `README.md` and
a `vanik` folder in the sidebar on the left.

VS Code will ask two things:

- *"Do you trust the authors of the files in this folder?"* → **Yes, I trust the
  authors.** Without this, debugging is disabled.
- *"This workspace has extension recommendations."* → **Install**. That gets you
  the Python extension, which is what makes everything below work.

If the recommendation popup doesn't appear, click the Extensions icon in the
left bar (four squares), search for **Python** by Microsoft, and install it.

---

## 3. Point VS Code at your Python

Press **Ctrl+Shift+P** (Cmd+Shift+P on Mac). This opens the Command Palette, a
search box for every VS Code command — you'll use it constantly.

Type `Python: Select Interpreter` and press Enter. Pick any Python 3.10+ from the
list. This tells VS Code which Python to run your code with.

---

## 4. Run it

Press **F5**.

A dropdown appears asking which configuration to run. Pick **Run demo**. The
terminal opens at the bottom and the nine-act walkthrough prints out in colour.

That's the whole thing running. Press F5 again any time; it remembers your
choice.

The other configurations in that dropdown:

| Configuration | What it does |
|---|---|
| Run demo | The nine-act walkthrough |
| Run demo, then open the audit trail | Same, and opens `out/audit.html` in your browser |
| Run tests | The 26 rule tests |
| Run demo against real Razorpay test keys | Needs a `.env` file — see section 7 |

**If you'd rather use the terminal**, press Ctrl+` (the backtick key, above Tab)
to open one inside VS Code, then:

```
python run_demo.py            # Windows
python3 run_demo.py           # macOS and Linux
```

---

## 5. Look at the audit trail

The demo writes `out/audit.html`. VS Code shows you the HTML source rather than
the page, which isn't what you want. Three ways to see it properly:

- **Easiest:** run the **Run demo, then open the audit trail** configuration
  from F5. It opens in your normal browser when the demo finishes.
- Right-click `out/audit.html` in the sidebar → **Show in File Explorer** (or
  **Reveal in Finder**), then double-click it.
- Right-click it → **Show Preview**, if you installed the Live Preview extension
  from the recommendations.

---

## 6. The part VS Code is actually for: breakpoints

This is why you moved off Colab. A breakpoint pauses the program mid-run so you
can look at every variable at that exact moment. It is the fastest way to
understand code you didn't write.

Try this one:

1. Open `vanik/policy.py`.
2. Find the line `effect = max((v.effect for v in vs), ...)` inside `evaluate`.
   It's around line 101, and it's the line that decides whether the
   whole action is allowed, gated or denied.
3. Click in the narrow margin just left of the line number. A **red dot**
   appears. That's a breakpoint.
4. Press **F5** and pick **Run demo**.

The program runs and then freezes on that line. Now look at the panel on the
left, under **Variables**. Expand `vs`. That's the list of verdicts the rules
just produced — every rule that ran, what it decided, and the sentence it wrote
to explain itself. Expand `a` to see the money action being judged.

Along the top is a small toolbar:

| Button | Key | What it does |
|---|---|---|
| Continue | F5 | Run on until the next breakpoint |
| Step Over | F10 | Run the current line, stop on the next one |
| Step Into | F11 | Go *inside* the function on this line |
| Stop | Shift+F6 | Quit |

Press **F5** repeatedly. You'll stop here once per money action — eight times
across the demo — and watch the verdict list change as the buyer's cart and
spend history change. Watching `effect` flip from `allow` to `deny` to `gate` is
the whole design in one variable.

When you're done, click the red dot again to remove it.

**Two more breakpoints worth setting:**

- In `vanik/agent.py`, on the second `raise Refused(d)` inside `_gate` (line
  165, the deny branch). This fires only when a charge is actually being
  blocked, so it skips the cases that sail through.
- In `vanik/rzp.py`, on the `last = e` line inside `_call` (line 194). This
  fires during the injected capture failure, so you can watch the retry logic
  decide whether the error is safe to try again.

---

## 7. Optional: real Razorpay test keys

1. Sign in at [dashboard.razorpay.com](https://dashboard.razorpay.com) and flip
   the toggle to **Test Mode**. Check it says Test Mode before continuing.
2. **Account & Settings → API Keys → Generate Test Key.**
3. Copy the Key ID (it starts with `rzp_test_`) and the Key Secret. The secret is
   shown once.
4. In VS Code, copy `.env.example` to a new file named exactly `.env` and paste
   your keys in.
5. Press F5 and choose **Run demo against real Razorpay test keys**.

`.env` is already listed in `.gitignore`, so your keys won't be committed if you
push this anywhere.

The live run stops after it creates the payment link, because a human has to
open that link and pay before there is anything to capture. The offline run is
the one that shows the whole arc including the failure — that's deliberate, not
a limitation.

---

## 8. Two shortcuts worth learning now

**Ctrl+Shift+P** — the Command Palette. Every command lives here. If you can't
find a menu item, search for it here instead.

**Ctrl+P** — jump to a file by name. Type `pol` and hit Enter to land in
`policy.py`. Much faster than clicking through the sidebar once a project has a
dozen files.

Two more that pay off quickly: **F12** on any function name jumps to where it's
defined, and **Shift+F12** shows everywhere it's used.

---

## When something goes wrong

**`python: command not found` or `'python' is not recognized`**
Python isn't on your PATH. On Windows, re-run the installer, choose Modify, and
tick "Add python.exe to PATH". On macOS and Linux, use `python3` rather than
`python`.

**VS Code says `run_demo.py` does not exist when you press F5**
You opened the wrong folder. The launch configurations look for `run_demo.py`
directly inside the folder you opened. Do **File → Open Folder** again and pick
the `vanik` folder itself, not the folder containing it.

**`ModuleNotFoundError: No module named 'vanik'`**
Almost always means you're running a *different* Python from the one you
selected — a system Python that can't see the project. Redo section 3, then
check with `import sys; print(sys.executable)` in the terminal.

**F5 does nothing, or says "select a debug configuration"**
The Python extension isn't installed, or no interpreter is selected. Redo
sections 2 and 3.

**Everything runs but no `out/` files appear**
They're written next to `run_demo.py`, not next to wherever your terminal
happens to be. Look in the `out` folder in the VS Code sidebar; you may need to
click the refresh icon at the top of the Explorer panel.

**`launch.json` shows a red squiggle under `"debugpy"`**
You have an older Python extension. Either update it, or change every
`"type": "debugpy"` in `.vscode/launch.json` to `"type": "python"`.

**Breakpoints are hollow grey circles instead of solid red**
The debugger didn't attach to that file. Usually it means you started with
Ctrl+F5 (Run Without Debugging) instead of F5. Stop and press F5.

**The terminal shows `[34m` and similar junk instead of colours**
Your terminal doesn't handle colour codes. Harmless. In VS Code, switch the
integrated terminal to PowerShell or bash from the dropdown in the terminal
panel's top-right.

---

## What to do next

Now that you can set breakpoints, the useful next moves are:

- **Add a rule.** Open `vanik/policy.py` and look at `_amount_rules`. Every rule
  is a few lines that append a `Verdict`. Add one — a cap per category, or a
  rule that blocks charges outside business hours — then add a matching test to
  `tests.py` and run it.
- **Break something on purpose.** In `tests.py`, change an expected `DENY` to
  `ALLOW` and watch the test fail. Knowing what a failing test looks like before
  you need to read one is worth the two minutes.
- **Serve it.** Wrap `vanik/agent.py` in FastAPI and put the manifest at a real
  `/.well-known/agentic-commerce.json`, so an outside buyer agent can find you
  over HTTP rather than by importing your code.
