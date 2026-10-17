"""Spike: Google's official AP2 SDK (V2, github.com/google-agentic-commerce/AP2) issuing and verifying a mandate chain for an Anvil booking.
NOT wired into the app. Install the SDK from Google's repo (the PyPI package named "ap2" is an unrelated third-party project):
    git clone --depth 1 https://github.com/google-agentic-commerce/AP2 /tmp/AP2 && pip install /tmp/AP2
Shows: manager-issued open mandate (amount range + allowed payees), agent-presented closed payment mandate, chain verification,
deterministic constraint checks (catch overage and unapproved payee, NOT a class swap), forged-signature and replay rejection."""
import json, time
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK
from ap2.sdk.mandate import MandateClient
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate, AmountRange, AllowedPayees
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument

def key(kid):
    j = json.loads(JWK.from_pyca(ec.generate_private_key(ec.SECP256R1())).export()); j["kid"] = kid
    return JWK.from_json(json.dumps(j))
pub = lambda k: JWK.from_json(k.export_public())
cnf = lambda k: {"jwk": json.loads(k.export_public())}

manager, orchestrator = key("manager-key"), key("orchestrator-key")
client = MandateClient()
suppliers = [Merchant(id="supplier-agent-1", name="Flight Supplier Agent"),
             Merchant(id="hotel-supplier-1", name="Hotel Supplier Agent"),
             Merchant(id="transport-supplier-1", name="Transport Supplier Agent")]

# 1. The manager issues an OPEN mandate for flights: <= $600 (minor units), approved suppliers only.
open_m = OpenPaymentMandate(constraints=[AmountRange(currency="USD", max=60000), AllowedPayees(allowed=suppliers)],
                            cnf=cnf(orchestrator), iat=int(time.time()), exp=int(time.time()) + 86400)
open_tok = client.create(payloads=[open_m], issuer_key=manager)
print("open mandate issued, bytes:", len(open_tok))

def present_and_check(label, amount_usd, payee):
    closed = PaymentMandate(transaction_id="tx-" + label, payee=payee, payment_amount=Amount(amount=int(amount_usd * 100), currency="USD"),
                            payment_instrument=PaymentInstrument(id="corp-card-1", type="credit"))
    chain_tok = client.present(holder_key=orchestrator, mandate_token=open_tok, payloads=[closed], aud="anvil-executor", nonce="n-" + label)
    payloads = client.verify(token=chain_tok, key_or_provider=lambda _t: pub(manager), expected_aud="anvil-executor", expected_nonce="n-" + label)
    violations = PaymentMandateChain.parse(payloads).verify()
    print(f"{label:34} signature chain verified; constraint violations: {violations}")
    return chain_tok

tok = present_and_check("economy-480-approved-supplier", 480, suppliers[0])
present_and_check("emirates-business-590-same-price", 590, suppliers[0])      # class swap: invisible to AP2 constraints
present_and_check("over-cap-660", 660, suppliers[0])
present_and_check("unapproved-supplier", 480, Merchant(id="shadow-broker-9", name="Shadow"))

# tamper 1: corrupt the issuer (manager) signature on the open mandate, keeping the encoding valid
hops = tok.split("~~"); first = hops[0]; jwt0 = first.split("~")[0]; h0, p0, sig0 = jwt0.split(".")
sig0 = sig0[:-2] + ("AA" if not sig0.endswith("AA") else "BB")
bad = "~~".join([".".join([h0, p0, sig0]) + first[len(jwt0):]] + hops[1:])
try:
    client.verify(token=bad, key_or_provider=lambda _t: pub(manager), expected_aud="anvil-executor", expected_nonce="n-economy-480-approved-supplier")
    print("FORGED SIGNATURE VERIFIED (unexpected)")
except Exception as e:
    print("forged manager signature rejected:", type(e).__name__, str(e)[:120])
# tamper 1b: change the nonce the merchant expects (replay protection)
try:
    client.verify(token=tok, key_or_provider=lambda _t: pub(manager), expected_aud="anvil-executor", expected_nonce="some-other-nonce")
    print("REPLAY VERIFIED (unexpected)")
except Exception as e:
    print("replay with a different nonce rejected:", type(e).__name__, str(e)[:120])
# tamper 2: verify against the WRONG manager key
try:
    client.verify(token=tok, key_or_provider=lambda _t: pub(key("attacker")), expected_aud="anvil-executor", expected_nonce="n-economy-480-approved-supplier")
    print("WRONG KEY VERIFIED (unexpected)")
except Exception as e:
    print("wrong issuer key rejected:", type(e).__name__, str(e)[:140])
