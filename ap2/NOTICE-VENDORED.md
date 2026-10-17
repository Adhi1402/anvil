# Vendored: Agent Payments Protocol (AP2) Python SDK

- Source: https://github.com/google-agentic-commerce/AP2 (path `code/sdk/python/ap2`: `models/` and `sdk/` only, tests omitted)
- Commit: `e1ea56db72a6385bce3e5c1112b3a56ce60acb43` (AP2 V2, released 2026-04-28)
- License: Apache-2.0 (see `LICENSE` in this directory). Files are unmodified.
- Why vendored: the PyPI package named `ap2` is an unrelated third-party project, and Google's repo is not published to PyPI under that name,
  so the SDK is copied here to keep the Cloud Run build reproducible. Its runtime dependencies are pinned in the repo-root `requirements.txt`.
- Used by: `anvil/ap2_layer.py` (second, deterministic gate next to the Gemini audit).
