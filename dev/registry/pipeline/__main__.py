"""Run the generated export-tree developer CLI with ``python -m dev.registry.pipeline``."""

from __future__ import annotations

import sys

if __name__ == "__main__":
    # Facts-only publication must not import the generated-export CLI.  That
    # CLI imports the full Modelo compiler/rendering graph, whose import-time
    # descriptors resolve the runtime authority and recursively re-enter the
    # artifact decoder.  Keep this command on its intentionally narrow
    # publication boundary.
    if len(sys.argv) > 1 and sys.argv[1] == "publish-facts-authority":
        from .facts_cli import app
    else:
        from .cli import app

    app()
