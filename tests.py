#!/usr/bin/env python3
"""Rule-level tests. Run: python3 tests.py

The demo shows one happy path through the system. These check that each rule
fires on its own, including the ones the demo never reaches.
"""
from __future__ import annotations

import time

from vanik.ledger import Ledger, redact
from vanik.mandates import CartLine, CartMandate, IntentMandate, PaymentMandate
from vanik.policy import ALLOW, DENY, GATE, MoneyAction, PolicyEngine

BS, MS = "buyer_key", "merchant_key"
PASS = FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  pass  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def intent(**kw) -> IntentMandate:
    d = dict(max_txn_minor=100_000, max_total_minor=200_000,
             allowed_categories=("beverage",), expires_at=time.time() + 600)
    d.update(kw)
    return IntentMandate(**d).sign(BS)


def cart(total_target: int = 50_000, category: str = "beverage",
         intent_id: str = "") -> CartMandate:
    c = CartMandate(intent_id=intent_id,
                    lines=[CartLine("SKU1", "Thing", category, 1, total_target)],
                    expires_at=time.time() + 600)
    return c.sign(MS)


def mandate_for(c: CartMandate) -> PaymentMandate:
    return PaymentMandate(cart_id=c.id, cart_digest=c.digest(),
                          amount_minor=c.total_minor).sign(BS)


def engine(m: IntentMandate) -> PolicyEngine:
    return PolicyEngine(m, BS, MS, Ledger("test"))


def action(c, pm, amount=None, kind="payment.capture", idem="k1", **kw):
    return MoneyAction(kind, amount if amount is not None else c.total_minor,
                       "INR", idem, cart=c, payment_mandate=pm, **kw)


# ---------------------------------------------------------------- mandates
def t_signature():
    m = intent()
    check("intent mandate verifies with the right key", m.verify(BS))
    check("intent mandate fails with a wrong key", not m.verify("other"))
    m.max_txn_minor = 999_999_999
    check("raising the cap invalidates the signature", not m.verify(BS))


def t_expiry():
    m = intent(expires_at=time.time() - 1)
    c = cart(); e = engine(m)
    d = e.evaluate(action(c, mandate_for(c)))
    check("R1 denies an expired mandate", d.effect == DENY, d.headline)


# ------------------------------------------------------------------ bounds
def t_txn_cap():
    m = intent(max_txn_minor=40_000)
    c = cart(50_000); e = engine(m)
    d = e.evaluate(action(c, mandate_for(c)))
    check("R3 denies over the per-transaction cap", d.effect == DENY)
    check("R3 explains the shortfall in rupees", "₹100.00" in d.headline,
          d.headline)


def t_session_cap():
    m = intent(max_txn_minor=100_000, max_total_minor=120_000)
    e = engine(m)
    c1 = cart(80_000); a1 = action(c1, mandate_for(c1), idem="a")
    e.commit(a1, e.evaluate(a1))
    c2 = cart(80_000); a2 = action(c2, mandate_for(c2), idem="b")
    check("R4 denies once cumulative spend would exceed the envelope",
          e.evaluate(a2).effect == DENY)


def t_velocity():
    m = intent(max_charges=1)
    e = engine(m)
    c1 = cart(10_000); a1 = action(c1, mandate_for(c1), idem="a")
    e.commit(a1, e.evaluate(a1))
    c2 = cart(10_000); a2 = action(c2, mandate_for(c2), idem="b")
    check("R5 denies past the charge-count cap", e.evaluate(a2).effect == DENY)


def t_scope():
    m = intent(allowed_categories=("beverage",))
    c = cart(10_000, category="equipment")
    d = engine(m).evaluate(action(c, mandate_for(c)))
    check("R2 denies a category the buyer never authorised", d.effect == DENY)


def t_currency():
    m = intent()
    c = cart(); e = engine(m)
    a = action(c, mandate_for(c)); a.currency = "USD"
    check("R6 denies a currency outside the mandate",
          e.evaluate(a).effect == DENY)


# ------------------------------------------------------------------- gates
def t_step_up():
    m = intent(step_up_over_minor=40_000)
    c = cart(50_000); pm = mandate_for(c); e = engine(m)
    a = action(c, pm)
    d = e.evaluate(a)
    check("R8 holds a large charge for a human", d.effect == GATE)
    e.approve(d.id, c.digest())
    check("approval clears the hold",
          e.re_evaluate_with_approval(a, d).effect == ALLOW)
    c2 = cart(50_000)
    d2 = e.evaluate(action(c2, mandate_for(c2), idem="k2"))
    check("approval does not carry over to a different cart",
          d2.effect == GATE)


# -------------------------------------------------------------- integrity
def t_idempotency():
    m = intent(); e = engine(m)
    c = cart(10_000); pm = mandate_for(c)
    a = action(c, pm, idem="same")
    e.commit(a, e.evaluate(a))
    check("R7 denies a replay of a completed action",
          e.evaluate(action(c, pm, idem="same")).effect == DENY)
    check("R7 denies a missing idempotency key",
          e.evaluate(action(c, pm, idem="")).effect == DENY)


def t_price_drift():
    m = intent(); e = engine(m)
    c = cart(10_000); pm = mandate_for(c)
    c.lines[0].unit_minor = 90_000          # merchant raises price post-auth
    c.sign(MS)                              # and re-signs it
    d = e.evaluate(action(c, pm))
    check("R10 denies a cart edited after the buyer authorised it",
          d.effect == DENY, d.headline)


def t_unsigned_cart():
    m = intent(); e = engine(m)
    c = CartMandate(lines=[CartLine("S", "T", "beverage", 1, 10_000)])
    check("R10 denies an unsigned cart",
          e.evaluate(action(c, None)).effect == DENY)


def t_refund_bound():
    m = intent(); e = engine(m)
    over = MoneyAction("refund.create", 60_000, "INR", "r1",
                       target_payment_id="pay_1", captured_minor=50_000)
    check("R9 denies a refund larger than the capture",
          e.evaluate(over).effect == DENY)
    part = MoneyAction("refund.create", 20_000, "INR", "r2",
                       target_payment_id="pay_1", captured_minor=50_000,
                       already_refunded_minor=20_000)
    check("R9 allows a partial refund inside the headroom",
          e.evaluate(part).effect == ALLOW)
    third = MoneyAction("refund.create", 20_000, "INR", "r3",
                        target_payment_id="pay_1", captured_minor=50_000,
                        already_refunded_minor=40_000)
    check("R9 counts refunds already issued",
          e.evaluate(third).effect == DENY)


def t_unknown_action():
    m = intent(); e = engine(m)
    a = MoneyAction("payout.create", 10_000, "INR", "x")
    check("R0 fails closed on an unrecognised money action",
          e.evaluate(a).effect == DENY)


# ---------------------------------------------------------------- ledger
def t_chain():
    l = Ledger("t")
    for i in range(6):
        l.append("test", f"e{i}", {"i": i})
    check("chain verifies when untouched", l.verify()[0])
    l.entries[3].payload["i"] = 99
    ok, msg = l.verify()
    check("chain detects an edited payload", not ok and "4" in msg, msg)


def t_chain_deletion():
    l = Ledger("t")
    for i in range(5):
        l.append("test", f"e{i}", {"i": i})
    del l.entries[2]
    check("chain detects a removed entry", not l.verify()[0])


def t_redaction():
    out = redact({"email": "arjun.mehta@example.com",
                  "contact": "9876543210",
                  "nested": [{"vpa": "arjun@okaxis"}],
                  "amount_minor": 1000})
    check("redaction masks contact details",
          "arjun.mehta" not in str(out) and "9876543210" not in str(out), out)
    check("redaction leaves amounts intact", out["amount_minor"] == 1000)


if __name__ == "__main__":
    print("policy and ledger tests\n")
    for fn in [t_signature, t_expiry, t_txn_cap, t_session_cap, t_velocity,
               t_scope, t_currency, t_step_up, t_idempotency, t_price_drift,
               t_unsigned_cart, t_refund_bound, t_unknown_action, t_chain,
               t_chain_deletion, t_redaction]:
        fn()
    print(f"\n  {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
