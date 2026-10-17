"""Issue Anvil's AP2 open payment mandates with Google's official AP2 SDK (run on the MANAGER's machine).

    python scripts/ap2_issue.py            # first run: creates keys, writes data/ap2_open_mandates.json
    python scripts/ap2_issue.py --reissue  # re-sign open mandates (new expiry/caps) with the existing manager key

Keys live in ~/.anvil/ (outside the repo, never committed):
  ap2-manager-key.jwk   the manager's PRIVATE key. Signs the open mandates; the server never has it.
  ap2-orchestrator.jwk  the orchestrator's PRIVATE key. Goes to Cloud Run as ANVIL_AP2_ORCH_KEY (base64, printed below).
Commit data/ap2_open_mandates.json (signed tokens + the manager PUBLIC key only)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jwcrypto.jwk import JWK
from anvil import ap2_layer
from data.store import DEMO_MANDATE

HOME = Path.home() / ".anvil"
HOME.mkdir(mode=0o700, exist_ok=True)
mk_path, ok_path = HOME / "ap2-manager-key.jwk", HOME / "ap2-orchestrator.jwk"


def load_or_make(path, kid):
    if path.exists():
        return JWK.from_json(path.read_text())
    k = ap2_layer.new_key(kid)
    path.write_text(k.export()); os.chmod(path, 0o600)
    print("created", path)
    return k


manager, orch = load_or_make(mk_path, "anvil-manager-key-1"), load_or_make(ok_path, "anvil-orchestrator-key-1")
constraints = {k: v for k, v in DEMO_MANDATE.items() if k not in ("id", "signed_by")}
meta = ap2_layer.issue_open_mandates(constraints, manager, ap2_layer.public_dict(orch))
out = Path(__file__).resolve().parent.parent / "data" / "ap2_open_mandates.json"
out.write_text(json.dumps(meta, indent=1))
print("wrote", out, "| caps (cents):", meta["caps_cents"], "| expires:", meta["exp"])
print("\nSet on Cloud Run (value is the base64 orchestrator PRIVATE key; treat as a secret):")
print("  gcloud run services update anvil --region us-central1 --update-env-vars ANVIL_AP2_ORCH_KEY=" + ap2_layer.key_to_b64(orch))
