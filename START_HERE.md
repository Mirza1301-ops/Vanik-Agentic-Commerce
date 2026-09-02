# Start here

## Run it

**Double-click `RUN_DEMO.bat`.**

That's the whole thing. It finds Python by itself, so you don't need to set up
PATH, open a terminal, or type any commands.

A black window opens, the demo prints out, and the audit trail opens in your
browser when it finishes. The window stays open until you press a key, so you
can read it.

Windows may show a blue "Windows protected your PC" box the first time, because
the file came from the internet. Click **More info**, then **Run anyway**.

**Double-click `RUN_TESTS.bat`** to run the 26 rule tests instead. You want
`26 passed, 0 failed`.

On macOS or Linux, use `run.sh` instead of the `.bat` files.

---

## If it says Python was not found

Install it from **[python.org/downloads](https://www.python.org/downloads/)**.

On the installer's **first screen** there's a checkbox at the bottom that says
**"Add python.exe to PATH"**. Tick it before clicking Install. It's off by
default and it's the cause of most Windows Python trouble.

Then double-click `RUN_DEMO.bat` again.

The launcher also checks the two places Python normally installs, so it will
often work even if you missed that checkbox.

---

## What you're looking at

A merchant that an AI buyer can shop from end to end, on Razorpay test mode,
where every action that moves money has to get past a deterministic gate first.

The demo runs nine acts. Four are worth reading closely:

| | What happens |
|---|---|
| **Act 3** | A charge is **blocked**. The buyer agent worked out its budget from the discounted subtotal and forgot GST and shipping land on top, putting it ₹200.10 over its limit. It drops the add-on and re-quotes instead of waking the human. |
| **Act 5** | The payment capture **fails three times**. The agent doesn't know whether money moved, so it stops retrying, asks Razorpay what actually happened, and captures exactly once. |
| **Act 7** | A stuck retry loop tries the same charge again and is **refused** before it can double-charge. |
| **Act 8** | A refund larger than what was captured is **refused**, then re-scoped to the damaged item. |

At the end it verifies the audit trail, then deliberately edits one amount in a
copy to show the tamper detection catching it.

---

## The audit trail

`out/audit.html`, which opens automatically. This is the artefact worth showing
someone: the hash chain drawn as a line down the page, solid dots for actions
that moved money, and every blocked or held decision expanding into the exact
rules that produced it.

Double-click it any time to reopen.

---

## Everything else

- **`README.md`** — how the system is built and why, including the eleven rules
- **`SETUP_VSCODE.md`** — VS Code setup, and where to put breakpoints to watch
  the policy engine decide one action at a time
- **`.env.example`** — copy to `.env` and add real Razorpay test keys if you
  want live API calls

Nothing needs installing. The project uses only what ships with Python.
