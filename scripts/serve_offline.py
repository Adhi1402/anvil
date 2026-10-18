"""Run the whole backend on your laptop with NO Google credentials and NO real data: in-memory Firestore, a rule-based
stand-in for Gemini, the supplier agents in-process. Safe for UI work (nothing reaches the live system).
  python scripts/serve_offline.py 8080
  ANVIL_REAL_GEMINI=1 python scripts/serve_offline.py 8080    # same, but with the real Gemini model (nothing is stored in the cloud)
  python scripts/serve_dashboard.py 8100      ->  http://localhost:8100/index.html?as=guest&api=http://localhost:8080"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("SUPPLIERS_URL", None)
from tests.fakes import install                    # noqa: E402

from anvil import ap2_layer                       # noqa: E402

fake_db, app = install()
if os.environ.get("ANVIL_REAL_GEMINI") == "1":      # real Gemini on Vertex AI (needs `gcloud auth application-default login`), still no real data
    import anvil.gemini as _g
    _g._client = None
ap2_layer.configure(ap2_layer.Layer(False, "offline mode"))
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Offline Anvil backend on http://localhost:{port} (fake Gemini, in-memory Firestore)")
    app.run(host="127.0.0.1", port=port, threaded=True)
