"""
Vault shim sweep (research file) — rewrites forward-looking shim/deprecation
language in the aeat-restructure research document to reflect the hard-cutover
migration model that was adopted.

Run from the worktree root:
    python scripts/vault_shim_sweep_research.py
"""

import pathlib

BASE = pathlib.Path(r"Y:\code\aeat-worktrees\chore-476-restructure-execution")
RESEARCH = BASE / ".vault" / "research" / "2026-04-30-aeat-restructure-research.md"


def apply_replacements(path: pathlib.Path, replacements: list[tuple[str, str]]) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    original = text
    count = 0
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new, 1)
            count += 1
        else:
            print(f"  WARN: not found: {old[:80]!r}")
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"  OK: {path.name} ({count} replacements)")
    else:
        print(f"  SKIP: {path.name} (no changes)")
    return count


# Note: the file was read with errors='replace' so some non-ASCII chars
# (em-dashes U+2014, arrows U+2192) may appear as U+FFFD in the string.
# We need to use the replacement character � in our search strings
# where those characters appear.

REPL_CHAR = "�"

replacements = [
    # Line 259: persistence.storage re-export shim
    (
        "preserved via the `aeat.adapters.persistence.storage` re-export shim. Per-sub-module",
        "preserved via hard-cutover: all callers updated to new canonical paths in the "
        "Step 7 keystone PR. Per-sub-module",
    ),

    # Lines 531-532: aeat.core.errors must keep working via shim
    (
        "must keep working through the restructure (re-export shim at\n"
        "  `aeat/errors.py` if needed, or document the breaking change).",
        "must keep working through the restructure (hard-cutover: all callers updated "
        "to new canonical paths in the Step 7 keystone PR).",
    ),

    # Lines 586-588: either a re-export shim or a documented breaking change
    (
        "  stable public surface; relocating to `aeat.core.errors` requires\n"
        "  either a re-export shim or a documented breaking change with a\n"
        "  migration window.",
        "  stable public surface; relocating to `aeat.core.errors` is handled\n"
        "  via hard-cutover: all callers updated to new canonical paths in the\n"
        "  Step 7 keystone PR.",
    ),

    # Lines 999-1016: large block describing re-export shim plan for aeat.core.errors
    (
        "- **Re-export shim at `aeat/errors.py`** (or\n"
        "  `aeat/core/errors/__init__.py`) re-exports every public symbol from\n"
        "  its new home. Existing consumers continue to work unchanged.\n"
        "- The 8 formulas exceptions ALREADY have a canonical alternative\n"
        "  home: `aeat.domain.formulas` re-exports them via `aeat.domain.formulas.__init__`.\n"
        "  The shim adds redundancy but is justified by the public-API\n"
        "  contract.\n"
        "- Shim removal is a **separate downstream decision** after a\n"
        "  documented deprecation window.\n"
        "\n"
        "Feeds the ADR public-surface table:\n"
        "- `from aeat.core.errors import AeatError` � preserve via shim.\n"
        "- `from aeat.core.errors import FormulasError` (and the other 7) �\n"
        "  preserve via shim; canonical home becomes `aeat.domain.formulas`.\n"
        "- `from aeat.core.errors import McpLaunchError` � preserve via shim;\n"
        "  canonical home becomes `aeat.entrypoints.mcp` (or `entrypoints/mcp`).\n"
        "- `from aeat.core.errors import FilingFixtureError` � preserve via shim;\n"
        "  canonical home becomes `aeat.domain.testing`.",
        "- **Hard-cutover**: all callers at old `aeat.core.errors` paths updated to\n"
        "  new canonical homes in the Step 7 keystone PR. No backward-compat\n"
        "  re-export layer introduced.\n"
        "- The 8 formulas exceptions ALREADY have a canonical alternative\n"
        "  home: `aeat.domain.formulas` re-exports them via `aeat.domain.formulas.__init__`.\n"
        "\n"
        "Feeds the ADR public-surface table:\n"
        "- `from aeat.core.errors import AeatError` � hard-cutover to `aeat.core.errors`.\n"
        "- `from aeat.core.errors import FormulasError` (and the other 7) �\n"
        "  hard-cutover; canonical home becomes `aeat.domain.formulas`.\n"
        "- `from aeat.core.errors import McpLaunchError` � hard-cutover;\n"
        "  canonical home becomes `aeat.entrypoints.mcp` (or `entrypoints/mcp`).\n"
        "- `from aeat.core.errors import FilingFixtureError` � hard-cutover;\n"
        "  canonical home becomes `aeat.domain.testing`.",
    ),

    # Line 1066: re-export shim preserves aeat.core.errors contract
    (
        "re-export shim preserves the `aeat.core.errors` public-API contract.",
        "hard-cutover: all callers updated to new canonical paths; the `aeat.core.errors` "
        "public-API contract is satisfied by the module remaining at its canonical dotted path.",
    ),

    # Lines 1696-1697: __init__.py (re-export shim) for persistence.storage
    (
        "Plus `errors.py` (shared error hierarchy) + `__init__.py` (re-export\nshim).",
        "Plus `errors.py` (shared error hierarchy) + `__init__.py` (public-surface re-exports).",
    ),

    # Lines 1743-1750: persistence.storage public-API contract block
    (
        "- After split: re-export shim preserves the `aeat.adapters.persistence.storage` import.\n"
        "- 5 CORE-LEAK promotions create new `aeat.core.*` public surfaces;\n"
        "  re-export shims at old `aeat.adapters.persistence.storage` paths during deprecation\n"
        "  window.\n"
        "- `_resolve_master_key_provider` is de-facto public (12+ external\n"
        "  consumers). **Recommendation**: rename to\n"
        "  `resolve_master_key_provider` (drop underscore) at move time.\n"
        "- `Base`, `KEYRING_SERVICE`, `KEYRING_USERNAME` preserved via shim.",
        "- After split: all callers updated to new canonical paths in the Step 7 keystone PR;\n"
        "  hard-cutover model — no re-export layer at old `aeat.adapters.persistence.storage`.\n"
        "- 5 CORE-LEAK promotions create new `aeat.core.*` public surfaces;\n"
        "  all consumers at old paths updated in the same change-set.\n"
        "- `_resolve_master_key_provider` is de-facto public (12+ external\n"
        "  consumers). **Recommendation**: rename to\n"
        "  `resolve_master_key_provider` (drop underscore) at move time.\n"
        "- `Base`, `KEYRING_SERVICE`, `KEYRING_USERNAME` preserved at canonical paths "
        "via hard-cutover.",
    ),

    # Lines 2478-2479: LLM re-export shim
    (
        "- `aeat.adapters.outbound.llm` `__all__` exports 23 symbols. Re-export shim\n"
        "  preserves the `from aeat.adapters.outbound.llm import ...` contract.",
        "- `aeat.adapters.outbound.llm` `__all__` exports 23 symbols. Hard-cutover:\n"
        "  all callers updated to new canonical paths in the Step 7 keystone PR.",
    ),
]


print("=== vault shim sweep (research) ===")
apply_replacements(RESEARCH, replacements)
print("=== done ===")
