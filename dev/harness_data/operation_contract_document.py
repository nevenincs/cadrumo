"""Write the operation contract document the MCP harness ships from the production registry.

The harness answers ``search`` and ``describe`` for a connection with no
session and with no runtime running from this document, so it has to be
written again whenever an operation is added or removed or its contract or
request changes. The registry is the authority and the document is its copy;
a test beside the registry's tests holds the two together::

    python -m dev.harness_data.operation_contract_document
"""

from __future__ import annotations

from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.tests.operation_contract_document import (
    DOCUMENT_ROOT,
    registered_descriptions,
    render_contract_document,
)
from cadrumo_harness.mcp.public_operation_discovery import CONTRACT_PART_SUFFIX

_UTF_8 = "utf-8"
_LINE_END = "\n"


def main() -> int:
    """Write the document from the production registry, and drop the part of a family that is gone."""
    document = render_contract_document(registered_descriptions(build_production_operation_registry()))
    DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in sorted(DOCUMENT_ROOT.glob(f"*{CONTRACT_PART_SUFFIX}")):
        if stale.name not in document and stale.is_file():
            stale.unlink()
    for name, text in document.items():
        (DOCUMENT_ROOT / name).write_text(text, encoding=_UTF_8, newline=_LINE_END)
    operations = sum(text.count(_LINE_END) for text in document.values())
    print(f"wrote {DOCUMENT_ROOT} ({operations} operations in {len(document)} parts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
