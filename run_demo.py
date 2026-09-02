#!/usr/bin/env python3
"""End-to-end: an AI buyer transacts with a merchant it has never seen.

  python3 run_demo.py                 # offline, deterministic, with fault injection
  python3 run_demo.py --live          # same flow against api.razorpay.com test mode
        env: RAZORPAY_KEY_ID=rzp_test_... RAZORPAY_KEY_SECRET=...

Writes out/audit.html, out/audit.jsonl and out/manifest.json.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import uuid
from pathlib import Path

from vanik import catalog as cat
from vanik.agent import MerchantAgent, Refused, new_idem
from vanik.buyer import BuyerAgent
from vanik.ledger import Ledger
from vanik.mandates import rupees
from vanik.policy import PolicyEngine
from vanik.report import write as write_report
from vanik.rzp import Client, HttpTransport, MockTransport, RzpError

ROOT = Path(__file__).parent
OPEN_REPORT = False
BUYER_SECRET = "buyer_wallet_key_demo"
MERCHANT_SECRET = "merchant_signing_key_demo"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

W = 78
C = {"h": "\033[1m", "d": "\033[2m", "r": "\033[31m", "g": "\033[32m",
     "y": "\033[33m", "b": "\033[34m", "x": "\033[0m"}
if not sys.stdout.isatty() and not os.getenv("FORCE_COLOR"):
    C = dict.fromkeys(C, "")


def act(n: int, title: str):
    print(f"\n{C['h']}{'─' * W}\n  {n}. {title}\n{'─' * W}{C['x']}")


def say(who: str, msg: str):
    print(f"  {C['b']}{who:<15}{C['x']}{msg}")


def verdict_block(d):
    colour = {"allow": C["g"], "deny": C["r"], "gate": C["y"]}[d.effect]
    print(f"  {colour}{'POLICY ' + d.effect.upper():<15}{C['x']}{d.headline}")
    for v in d.verdicts:
        if v.effect == "allow" and d.effect != "allow":
            continue
        mark = {"allow": "ok  ", "deny": "STOP", "gate": "HOLD"}[v.effect]
        print(f"  {C['d']}{'':<15}{mark} {v.rule:<22}{v.explain}{C['x']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="call api.razorpay.com with test keys")
    ap.add_argument("--open", action="store_true", dest="open_report",
                    help="open the audit trail in your browser when done")
    args = ap.parse_args()
    global OPEN_REPORT
    OPEN_REPORT = args.open_report

    run_id = f"run_{uuid.uuid4().hex[:10]}"
    ledger = Ledger(run_id)
    catalog = cat.load_catalog(ROOT / "data" / "catalog.json")

    if args.live:
        kid, ksec = os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")
        if not kid or not ksec:
            print("set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET", file=sys.stderr)
            return 2
        transport = HttpTransport(kid, ksec)
        mode = "live-test-keys"
    else:
        transport = MockTransport()
        mode = "test (offline simulator)"

    client = Client(transport=transport, ledger=ledger,
                    webhook_secret="whsec_kadai_demo")

    # ==================================================================
    act(1, "The buyer agent discovers a merchant it has never seen")
    # ==================================================================
    instruction = ("Get me 1kg of cold brew concentrate and something that goes "
                   "with it. Cap it at ₹1,800, and don't check with me unless "
                   "it's over ₹1,500. Ship to 560001.")
    say("human", instruction)

    manifest = cat.manifest(catalog, "https://kadai.example", MERCHANT_SECRET)
    (ROOT / "out" / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")

    buyer = BuyerAgent(ledger, BUYER_SECRET)
    ok = buyer.read_manifest(manifest, MERCHANT_SECRET)
    say("buyer agent", f"read /.well-known/agentic-commerce.json — signature "
                       f"{'verifies' if ok else 'FAILS'}, "
                       f"{manifest['catalog']['count']} SKUs, settles via "
                       f"{manifest['settlement']['psp']} in "
                       f"{manifest['settlement']['mode']} mode")
    say("", f"{C['d']}money actions declared: "
            f"{', '.join(a['name'] for a in manifest['actions'] if a['money_action'])}"
            f"{C['x']}")

    intent = buyer.issue_intent(
        max_txn_minor=180_000, max_total_minor=180_000,
        categories=("beverage", "accessory"),
        step_up_over_minor=150_000, ttl_s=900, human_present=False,
    )
    say("buyer agent", f"issued intent {intent.id}: ≤{rupees(intent.max_txn_minor)} "
                       f"per charge, categories {list(intent.allowed_categories)}, "
                       f"human confirm above {rupees(intent.step_up_over_minor)}")

    policy = PolicyEngine(intent, BUYER_SECRET, MERCHANT_SECRET, ledger)
    merchant = MerchantAgent(catalog, client, policy, ledger, MERCHANT_SECRET)

    # ==================================================================
    act(2, "Search, quote, and an upsell that overshoots the mandate")
    # ==================================================================
    hits = merchant.search_catalog("cold brew concentrate",
                                   categories=list(intent.allowed_categories))
    say("merchant agent", hits.explain)
    for p in hits.data["products"][:3]:
        print(f"  {C['d']}{'':<15}{p['sku']:<14}{p['name']:<34}"
              f"{rupees(p['price_minor'])}{C['x']}")

    items = [{"sku": "KC-CB-1KG", "qty": 1}, {"sku": "KC-FLT-100", "qty": 1}]
    q = merchant.quote_cart(items, "560001", intent.id)
    base = q.data["cart"]
    say("merchant agent", q.explain)

    # The buyer agent sizes its headroom off the discounted subtotal and forgets
    # that GST and shipping land on top. This is the ordinary way an agent
    # overspends, and the reason the gate is deterministic rather than a prompt.
    naive_headroom = intent.max_total_minor - (base.subtotal_minor -
                                               base.discount_minor)
    add = merchant.suggest_addons(base.id, naive_headroom,
                                  intent.allowed_categories)
    say("merchant agent", add.explain)
    for sku, why in add.data["withheld"]:
        say("", f"{C['d']}withheld {sku} — {why}{C['x']}")
    if add.data["suggestions"]:
        pick = add.data["suggestions"][0]
        say("buyer agent", f"I have {rupees(naive_headroom)} spare, adding "
                           f"{pick['name']} at {rupees(pick['price_minor'])}")
        items.append({"sku": pick["sku"], "qty": 1})

    q = merchant.quote_cart(items, "560001", intent.id)
    say("merchant agent", q.explain)
    cart = q.data["cart"]
    pm = buyer.authorise(cart)

    # ==================================================================
    act(3, "First money action is refused, and the agent handles it")
    # ==================================================================
    try:
        merchant.create_order(cart, pm, new_idem("order"))
    except Refused as e:
        verdict_block(e.decision)
        say("buyer agent", "not escalating to the human — dropping the add-on "
                           "and re-quoting")
        items = buyer.react_to_refusal(e.decision, items, ["KC-CRM-250"])

    q = merchant.quote_cart(items, "560001", intent.id)
    cart = q.data["cart"]
    pm = buyer.authorise(cart)
    say("merchant agent", q.explain)

    # ==================================================================
    act(4, "Second attempt clears the caps but trips the human gate")
    # ==================================================================
    idem_order = new_idem("order")
    try:
        merchant.create_order(cart, pm, idem_order)
    except Refused as e:
        verdict_block(e.decision)
        say("human", f"push notification answered: approve "
                     f"{rupees(cart.total_minor)} at Kadai Coffee")
        ledger.append("human", "step_up.approved", {
            "decision_id": e.decision.id, "amount_minor": cart.total_minor,
            "cart_digest": cart.digest()[:16],
            "explain": "Buyer confirmed this exact cart on their phone.",
        })
        policy.approve(e.decision.id, cart.digest())
        verdict_block(policy.re_evaluate_with_approval(
            _action_for(cart, pm, idem_order), e.decision))

    res = merchant.create_order(cart, pm, idem_order)
    say("merchant agent", res.explain)
    order = res.data["order"]

    link = merchant.create_payment_link(order, new_idem("link"), cart, pm)
    say("merchant agent", link.explain)

    # ==================================================================
    act(5, "The buyer pays, and the capture call fails ambiguously")
    # ==================================================================
    if args.live:
        say("system", "open the link above in test mode, pay, then re-run with "
                      "the order id to continue")
        _finish(ledger, run_id, mode)
        return 0

    auth = transport.simulate_authorization(order["id"], method="upi")
    say("buyer", f"paid via UPI — payment {auth['id']} is authorized, "
                 f"{rupees(auth['amount'])} held, not yet taken")

    hook = json.dumps({"id": f"evt_{uuid.uuid4().hex[:12]}",
                       "event": "payment.authorized",
                       "payload": {"payment": {"entity": auth}}}).encode()
    seen: set = set()
    r = merchant.handle_webhook(hook, client.sign_webhook(hook), seen)
    say("merchant agent", r.explain)

    # Inject the failure: the capture endpoint times out on every attempt.
    transport.inject("/capture", [RzpError(504, "GATEWAY_TIMEOUT",
                                           "upstream timed out", True)
                                  for _ in range(3)])
    idem_cap = new_idem("capture")
    say("merchant agent", "capturing the authorized amount…")
    payment = None
    try:
        payment = merchant.capture_payment(auth["id"], cart.total_minor,
                                           cart.currency, idem_cap, cart,
                                           pm).data["payment"]
    except RzpError as e:
        print(f"  {C['r']}{'FAILURE':<15}{C['x']}capture failed after "
              f"{client.max_attempts} attempts — {e}")
        say("merchant agent", "the outcome is unknown: the charge may or may not "
                              "have gone through, so a blind retry could take the "
                              "money twice")
        ledger.append("merchant_agent", "capture.outcome_unknown", {
            "payment_id": auth["id"], "idempotency_key": idem_cap,
            "explain": ("Three capture attempts returned no definite answer. "
                        "Stopping retries and reconciling against Razorpay "
                        "instead of guessing."),
        })

        truth = merchant.reconcile_order(order["id"])
        say("merchant agent", f"reconciled against Razorpay — payment is "
                              f"'{truth['state']}', "
                              f"{rupees(truth['payments'][0].get('amount_captured', 0))} "
                              f"actually captured")
        say("merchant agent", "money did not move, so exactly one more capture "
                              "is safe — reusing the same idempotency key")

        res = merchant.capture_payment(auth["id"], cart.total_minor,
                                       cart.currency, idem_cap, cart, pm)
        say("merchant agent", C["g"] + res.explain + C["x"])
        payment = res.data["payment"]

    # ==================================================================
    act(6, "Duplicate and forged webhooks")
    # ==================================================================
    hook2 = json.dumps({"id": "evt_captured_001", "event": "payment.captured",
                        "payload": {"payment": {"entity": payment}}}).encode()
    sig = client.sign_webhook(hook2)
    say("razorpay", "delivering payment.captured")
    say("merchant agent", merchant.handle_webhook(hook2, sig, seen).explain)
    say("razorpay", "delivering payment.captured again (delivery retry)")
    say("merchant agent", merchant.handle_webhook(hook2, sig, seen).explain)
    say("attacker", "posting a payment.captured for ₹9,99,999 with a guessed "
                    "signature")
    forged = json.dumps({"id": "evt_forged", "event": "payment.captured",
                         "payload": {"amount": 99999900}}).encode()
    say("merchant agent", C["r"] +
        merchant.handle_webhook(forged, "deadbeef" * 8, seen).explain + C["x"])

    # ==================================================================
    act(7, "Replay protection on the charge itself")
    # ==================================================================
    say("merchant agent", "a stuck retry loop tries the same capture again")
    try:
        merchant.capture_payment(auth["id"], cart.total_minor, cart.currency,
                                 idem_cap, cart, pm)
    except Refused as e:
        verdict_block(e.decision)

    # ==================================================================
    act(8, "Refunds are bounded by what was actually captured")
    # ==================================================================
    say("buyer agent", "filters arrived damaged — asking for ₹1,800 back")
    try:
        merchant.refund_payment(payment, 180_000, "damaged goods",
                                new_idem("refund"))
    except Refused as e:
        verdict_block(e.decision)
    say("buyer agent", "re-scoping to the filters line only")
    r = merchant.refund_payment(payment, 26_880, "filters damaged in transit",
                                new_idem("refund"))
    say("merchant agent", C["g"] + r.explain + C["x"])

    # ==================================================================
    act(9, "The audit trail")
    # ==================================================================
    ok, msg = ledger.verify()
    print(f"  {C['g' if ok else 'r']}{'CHAIN':<15}{C['x']}{msg}")

    tampered = copy.deepcopy(ledger)
    for e in tampered.entries:
        if e.event == "payment.captured":
            e.payload["amount_minor"] = 1
            break
    ok2, msg2 = tampered.verify()
    print(f"  {C['r']}{'TAMPER TEST':<15}{C['x']}edited a captured amount in a "
          f"copy → {msg2}")

    _finish(ledger, run_id, mode)
    return 0


def _action_for(cart, pm, idem):
    from vanik.policy import MoneyAction
    return MoneyAction("order.create", cart.total_minor, cart.currency, idem,
                       cart=cart, payment_mandate=pm)


def _finish(ledger: Ledger, run_id: str, mode: str) -> None:
    out = ROOT / "out"
    (out / "audit.jsonl").write_text(ledger.to_jsonl(), encoding="utf-8")
    write_report(ledger, {"run_id": run_id, "buyer": "buyer_agent_demo",
                          "merchant": "Kadai Coffee", "mode": mode},
                 out / "audit.html")
    print(f"\n  wrote out/audit.html · out/audit.jsonl · out/manifest.json\n")
    if OPEN_REPORT:
        import webbrowser
        webbrowser.open((out / "audit.html").resolve().as_uri())


if __name__ == "__main__":
    raise SystemExit(main())
