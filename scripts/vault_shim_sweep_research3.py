"""
Vault shim sweep (research file) pass 3 — fixes the re-export shim block
for aeat.core.errors treatment, using raw bytes for exact matching.
"""

import pathlib

BASE = pathlib.Path(r"Y:\code\aeat-worktrees\chore-476-restructure-execution")
RESEARCH = BASE / ".vault" / "research" / "2026-04-30-aeat-restructure-research.md"

raw = RESEARCH.read_bytes()

# Build the old block in raw bytes — em-dash is \xe2\x80\x94
EM = b"\xe2\x80\x94"

old_block = (
    b"- **Re-export shim at `aeat/errors.py`** (or\r\n"
    b"  `aeat/core/errors/__init__.py`) re-exports every public symbol from\r\n"
    b"  its new home. Existing consumers continue to work unchanged.\r\n"
    b"- The 8 formulas exceptions ALREADY have a canonical alternative\r\n"
    b"  home: `aeat.domain.formulas` re-exports them via `aeat.domain.formulas.__init__`.\r\n"
    b"  The shim adds redundancy but is justified by the public-API\r\n"
    b"  contract.\r\n"
    b"- Shim removal is a **separate downstream decision** after a\r\n"
    b"  documented deprecation window.\r\n"
    b"\r\n"
    b"Feeds the ADR public-surface table:\r\n"
    b"- `from aeat.core.errors import AeatError` " + EM + b" preserve via shim.\r\n"
    b"- `from aeat.core.errors import FormulasError` (and the other 7) " + EM + b"\r\n"
    b"  preserve via shim; canonical home becomes `aeat.domain.formulas`.\r\n"
    b"- `from aeat.core.errors import McpLaunchError` " + EM + b" preserve via shim;\r\n"
    b"  canonical home becomes `aeat.entrypoints.mcp` (or `entrypoints/mcp`).\r\n"
    b"- `from aeat.core.errors import FilingFixtureError` " + EM + b" preserve via shim;\r\n"
    b"  canonical home becomes `aeat.domain.testing`."
)

new_block = (
    b"- **Hard-cutover**: all callers at old `aeat.core.errors` paths updated to\r\n"
    b"  new canonical homes in the Step 7 keystone PR. No backward-compat\r\n"
    b"  re-export layer introduced.\r\n"
    b"- The 8 formulas exceptions ALREADY have a canonical alternative\r\n"
    b"  home: `aeat.domain.formulas` re-exports them via `aeat.domain.formulas.__init__`.\r\n"
    b"\r\n"
    b"Feeds the ADR public-surface table:\r\n"
    b"- `from aeat.core.errors import AeatError` " + EM + b" hard-cutover to `aeat.core.errors`.\r\n"
    b"- `from aeat.core.errors import FormulasError` (and the other 7) " + EM + b"\r\n"
    b"  hard-cutover; canonical home becomes `aeat.domain.formulas`.\r\n"
    b"- `from aeat.core.errors import McpLaunchError` " + EM + b" hard-cutover;\r\n"
    b"  canonical home becomes `aeat.entrypoints.mcp` (or `entrypoints/mcp`).\r\n"
    b"- `from aeat.core.errors import FilingFixtureError` " + EM + b" hard-cutover;\r\n"
    b"  canonical home becomes `aeat.domain.testing`."
)

if old_block in raw:
    raw = raw.replace(old_block, new_block, 1)
    RESEARCH.write_bytes(raw)
    print("OK: replaced re-export shim block for aeat.core.errors (bytes)")
else:
    # Diagnose — show bytes around the target
    idx = raw.find(b"Re-export shim at `aeat/errors.py`")
    if idx >= 0:
        print("MISS — found 'Re-export shim at' but block doesn't match exactly.")
        print("Actual bytes around start:")
        print(repr(raw[idx - 2 : idx + 200]))
    else:
        print("MISS — 'Re-export shim at' not found at all; already fixed?")
