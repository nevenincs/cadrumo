"""Controlled child that proves the assets CLI runner closes its secret pipe."""

from __future__ import annotations

import json
import sys


def main() -> int:
    """Read a complete JSON stream so an open stdin pipe cannot pass this fixture."""
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        return 2
    print(json.dumps({"status": "ok", "result": {"setup_state": "complete", "configured": True}}))
    return 0


if __name__ == "__main__":  # pragma: no cover - executable fixture boundary
    raise SystemExit(main())
