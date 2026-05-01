"""
Vault shim sweep (research file) pass 2 — fixes the re-export shim block
for aeat.core.errors treatment that uses CRLF line endings.
"""

import pathlib

BASE = pathlib.Path(r"Y:\code\aeat-worktrees\chore-476-restructure-execution")
RESEARCH = BASE / ".vault" / "research" / "2026-04-30-aeat-restructure-research.md"

REPL_CHAR = "�"  # replacement char for non-UTF8 chars when read with errors='replace'

# Read raw bytes so we preserve exact line endings
raw = RESEARCH.read_bytes()
text = raw.decode("utf-8", errors="replace")

old_block = (
    "- **Re-export shim at `aeat/errors.py`** (or\r\n"
    "  `aeat/core/errors/__init__.py`) re-exports every public symbol from\r\n"
    "  its new home. Existing consumers continue to work unchanged.\r\n"
    "- The 8 formulas exceptions ALREADY have a canonical alternative\r\n"
    "  home: `aeat.domain.formulas` re-exports them via `aeat.domain.formulas.__init__`.\r\n"
    "  The shim adds redundancy but is justified by the public-API\r\n"
    "  contract.\r\n"
    "- Shim removal is a **separate downstream decision** after a\r\n"
    "  documented deprecation window.\r\n"
    "\r\n"
    "Feeds the ADR public-surface table:\r\n"
    f"- `from aeat.core.errors import AeatError` {REPL_CHAR} preserve via shim.\r\n"
    f"- `from aeat.core.errors import FormulasError` (and the other 7) {REPL_CHAR}\r\n"
    "  preserve via shim; canonical home becomes `aeat.domain.formulas`.\r\n"
    f"- `from aeat.core.errors import McpLaunchError` {REPL_CHAR} preserve via shim;\r\n"
    "  canonical home becomes `aeat.entrypoints.mcp` (or `entrypoints/mcp`).\r\n"
    f"- `from aeat.core.errors import FilingFixtureError` {REPL_CHAR} preserve via shim;\r\n"
    "  canonical home becomes `aeat.domain.testing`."
)

new_block = (
    "- **Hard-cutover**: all callers at old `aeat.core.errors` paths updated to\r\n"
    "  new canonical homes in the Step 7 keystone PR. No backward-compat\r\n"
    "  re-export layer introduced.\r\n"
    "- The 8 formulas exceptions ALREADY have a canonical alternative\r\n"
    "  home: `aeat.domain.formulas` re-exports them via `aeat.domain.formulas.__init__`.\r\n"
    "\r\n"
    "Feeds the ADR public-surface table:\r\n"
    f"- `from aeat.core.errors import AeatError` {REPL_CHAR} hard-cutover to `aeat.core.errors`.\r\n"
    f"- `from aeat.core.errors import FormulasError` (and the other 7) {REPL_CHAR}\r\n"
    "  hard-cutover; canonical home becomes `aeat.domain.formulas`.\r\n"
    f"- `from aeat.core.errors import McpLaunchError` {REPL_CHAR} hard-cutover;\r\n"
    "  canonical home becomes `aeat.entrypoints.mcp` (or `entrypoints/mcp`).\r\n"
    f"- `from aeat.core.errors import FilingFixtureError` {REPL_CHAR} hard-cutover;\r\n"
    "  canonical home becomes `aeat.domain.testing`."
)

if old_block in text:
    text = text.replace(old_block, new_block, 1)
    RESEARCH.write_text(text, encoding="utf-8")
    print("OK: replaced re-export shim block for aeat.core.errors")
else:
    print("WARN: block not found — checking nearby text...")
    idx = text.find("Re-export shim at `aeat/errors.py`")
    if idx >= 0:
        print(repr(text[idx:idx+400]))
    else:
        idx = text.find("Re-export shim")
        print(f"First 'Re-export shim' at: {idx}")
        if idx >= 0:
            print(repr(text[idx:idx+300]))
