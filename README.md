# Vanik

A merchant that an AI buyer can transact with end to end, on Razorpay test mode,
where every rupee-moving call has to survive a deterministic gate first.

```
python3 run_demo.py          # full flow, offline, with the failure injected
python3 run_demo.py --open   # same, and opens the audit trail in a browser
python3 tests.py             # 26 rule-level tests
```

New to VS Code? **[SETUP_VSCODE.md](SETUP_VSCODE.md)** walks through it from
installing Python, including where to put breakpoints to see the policy engine
make decisions one at a time.

For real test keys:

```
RAZORPAY_KEY_ID=rzp_test_xxx RAZORPAY_KEY_SECRET=xxx python3 run_demo.py --live
```

Nothing outside the standard library. The client refuses any key that doesn't
start with `rzp_test_`.

---

## The problem this is aimed at

When a buyer agent shops on your behalf, three things break at once. You can't
see what it did. You can't bound what it's allowed to spend. And when a payment
call fails halfway, the agent has to decide whether to retry — which is the one
decision you never want an LLM making on its own.

Vanik puts a deterministic layer between the agent and the money.

## Shape

```
buyer agent  ─── reads ──▶  /.well-known/agentic-commerce.json
     │                      (signed manifest: SKUs, rails, which
     │                       actions move money, request schemas)
     │
     ├─ issues IntentMandate ─────────┐   signed by the buyer's wallet
     │                                │   caps, categories, TTL, step-up line
     ▼                                │
merchant agent                        │
  read tools ──── free                │
  money tools ────────────────────────▶  policy engine ──▶ ledger
                                          allow │ gate │ deny
                                                │
                                                ▼
                                          Razorpay test mode
```

Three files carry the weight:

- **`vanik/policy.py`** — eleven rules, no model in the loop. Same inputs always
  produce the same decision, so a decision can be replayed in a dispute.
- **`vanik/mandates.py`** — the AP2-style Intent → Cart → Payment chain. The
  merchant signs the cart, which freezes the price; the buyer signs a payment
  mandate against that exact cart digest. A price that changes after
  authorisation cannot be charged.
- **`vanik/ledger.py`** — append-only, each entry hashing its parent. Editing or
  removing an entry breaks every entry below it.

## The rules

| | Rule | What it stops |
|---|---|---|
| R0 | Known action | An unrecognised money action is denied, not allowed. Fails closed. |
| R1 | Mandate signature | Charging against a forged or expired authorisation |
| R2 | Intent scope | Buying from a category the human never authorised |
| R3 | Per-transaction cap | One oversized charge |
| R4 | Session cap | Death by a thousand small charges |
| R5 | Velocity | A retry loop draining the envelope |
| R6 | Currency | Settling in something the mandate doesn't cover |
| R7 | Idempotency | Double-charging on a retry or a replayed request |
| R8 | Step-up | Spending above the human's confirm-with-me line without asking |
| R9 | Refund bound | Refunding more than was captured, or to the wrong payment |
| R10 | Price integrity | A cart edited between quote and charge |

Strictest verdict wins: `deny` beats `gate` beats `allow`. Every verdict carries
a sentence written for a person, not a log parser:

```
POLICY DENY   Blocked order.create — ₹2,000.10 is over the buyer's
              per-transaction cap of ₹1,800.00 by ₹200.10.
              STOP  R3_TXN_CAP        ₹2,000.10 is over the buyer's cap by ₹200.10.
              STOP  R4_SESSION_CAP    This would take session spend to ₹2,000.10.
              HOLD  R8_STEP_UP        At or above the ₹1,500.00 confirm line.
```

## What the demo runs through

A human says: *"Get me 1kg of cold brew concentrate and something that goes with
it. Cap it at ₹1,800, and don't check with me unless it's over ₹1,500."*

1. The buyer agent reads the manifest cold, verifies the merchant signature, and
   issues itself a spending envelope from that one sentence.
2. The merchant's upsell tool withholds the ₹4,890 grinder — it's `equipment`,
   which the buyer never authorised. It offers the ₹390 syrup instead.
3. The buyer agent sizes its headroom off the discounted subtotal and forgets
   GST and shipping land on top. It adds the syrup. **R3 blocks the order at
   ₹2,000.10, over by ₹200.10.** The agent drops the add-on and re-quotes rather
   than waking the human.
4. The new total is ₹1,563.30 — inside the cap but above the confirm line.
   **R8 holds it.** The human approves once, and the approval binds to that cart
   digest, so the link and the capture don't ask again.
5. The buyer pays by UPI. The payment sits authorised, not captured.

### The failure

The capture call times out. Three times.

```
FAILURE         capture failed after 3 attempts — [504/GATEWAY_TIMEOUT]
merchant agent  the outcome is unknown: the charge may or may not have gone
                through, so a blind retry could take the money twice
merchant agent  reconciled against Razorpay — payment is 'authorized at source',
                ₹0.00 actually captured
merchant agent  money did not move, so exactly one more capture is safe
merchant agent  Captured ₹1,563.30 on pay_GVXNUCCHZQLVRL.
```

The agent stops retrying and stops guessing. It asks Razorpay what actually
happened (`GET /orders/{id}/payments`), gets ground truth, and acts on it once.
The idempotency key is still unused — the engine only burns a key on a
*confirmed* result — so the retry is safe by construction rather than by luck.

Then, in order: a duplicate webhook delivery is ignored, a forged one is rejected
on signature, a stuck retry loop hits **R7** and is denied, and an over-scoped
₹1,800 refund hits **R9** before being re-scoped to the ₹268.80 filter line.

Forty entries, chain intact. The last act edits one captured amount in a copy of
the ledger and shows the chain breaking at entry 32.

## The audit trail

`out/audit.html` renders the chain as a literal spine down the page. Money
actions are solid nodes; blocked and held actions open into the full rule
breakdown that produced the decision. Contact details are masked on write, so
the record is safe to hand to someone outside the team.

`out/audit.jsonl` is the same data, one canonical JSON object per line, for
piping into whatever you already run.

## Honest notes

- Mandate signatures are HMAC with a shared secret. That is enough to show the
  flow but is not the real thing — production needs detached JWS over the
  buyer's and merchant's own keys. The verification call sites don't change.
- Razorpay's core payments API dedupes order creation on `receipt`, not on an
  idempotency header (that header exists on the RazorpayX payout API). So the
  client keeps an application-level idempotency store, sets `receipt` from the
  same key, and stamps the key into `notes` so it's visible in the dashboard.
- The buyer agent has no model call in it. That's deliberate: it keeps the demo
  deterministic and puts the interesting behaviour in the mandate and policy
  layers, which is where it belongs. Swapping in a real planner changes nothing
  below the tool boundary.
- Manifest verification uses the merchant secret directly here. Over the wire it
  would be the merchant's published public key.
- The offline transport reproduces Razorpay's request and response shapes so the
  failure path is reproducible on demand rather than something you wait for. The
  same `Client` code runs against `api.razorpay.com` with `--live`.

## Layout

```
SETUP_VSCODE.md      setup and debugging guide, written for a first-timer
run_demo.py          the nine-act walkthrough
tests.py             26 rule-level tests
data/catalog.json    products, offers, shipping rules
vanik/
  catalog.py         manifest + agent-readable feed
  mandates.py        Intent / Cart / Payment mandate chain
  policy.py          the gate
  ledger.py          hash-chained audit log
  rzp.py             Razorpay client, HTTP + offline transports
  agent.py           merchant tool surface, reconciliation, webhooks
  buyer.py           the buyer-side agent
  report.py          HTML audit trail
.vscode/             launch configs, tasks, recommended extensions
.env.example         template for Razorpay test keys
```
