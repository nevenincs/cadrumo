---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:47c6df214bedfe4f27b9b66eb842be0c0621463c593e24c984b43ba6b3a7b9f3'
step_id: 'S317'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Clear the NINE dead entries from the import-hygiene test-debt inventory, each a spare slot left behind when somebody fixed the reach it records: `dev/quality/import_hygiene_test_debt.json` still names `_mint_diagnostic_id` (auth clave-movil page flow), `_redact_validation_context` (wizard widgets), `_IVA_REGIME_CHOICE_VALUES` (wizard commands), `_blocking_modelo_references` (ledger actions-common), `_evaluate_import_rows` (ledger actions-import), `_URL_ADAPTER` (browser site-health, reached from BOTH the workflow models test and the workflow resume test), `_load_registry_tree_cached` (registry loader, reached from the root conftest) and `_llm_classification` (ledger, reached from the LLM vision classifier test) -- all recorded 1x and occurring 0x, which reds four assertions in `dev/tests/test_import_hygiene_gate.py`; a dead entry is not inert, it is an unused allowance a future real violation can occupy, so the ratchet silently widens. Confirm each reach is genuinely gone rather than merely renamed, delete the dead entries, resolve the family-2 delegate-wrapper exemption failure covering the two ledger actions-common forwarding wrappers and the retention floor wrapper, and run the gate to a genuine full pass -- never add an entry to make a count reconcile, since a needed addition means a live reach still exists. Note the separate standing fact this Step does NOT close: production Family-1 sits at 114 live cross-package private reaches against a hard-zero baseline, which is a campaign of its own

## Scope

- `dev/quality/import_hygiene_test_debt.json`
- `the family-2 exemption inventory`
- `and dev/tests/test_import_hygiene_gate.py run to completion`

## Changes

- `M` `dev/quality/import_hygiene_test_debt.json`
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py -n0` -> `fail`

## Notes

### The dead-entry check does NOT go green from this Step

Nine entries were reported as answering no live reach. Checking each against
the source rather than trusting the occurrence count, they turned out to be
three different situations, and only one of the three is a resolution.

Four were genuinely fixed: the private symbol was promoted to a public name and
the test rewritten to import it. Those four entries are retired.

Two recorded a reach that still exists, where only the imported symbol changed.
Both workflow tests still import from the browser package's private site-health
module; they simply import the parse helper now instead of the URL adapter
constant the entry named. Those entries were corrected to name the symbol
actually imported, which also removes them from the undocumented set.

Three recorded a reach that is completely unchanged in the source. Each still
reads as a private symbol imported cross-package. What changed is that the
target module was promoted from a private to a public name, and that alone took
them out of the scanner's view. Those three are retained deliberately, and the
dead-entry check still fails on them. Deleting them would have taken the check
green while recording a resolution that did not happen.

### Why five of the nine died without anything being fixed

The scanner decides whether an import reaches into a foreign package's privates
from the target module path alone. The imported names are recorded on the
violation it builds and are never used to decide whether there is one. So a
private symbol reached cross-package through a public module is invisible to
it.

The consequence is that renaming a private module to a public name silently
clears every private-symbol reach into it, while the coupling is untouched.
Nobody has to intend this: an ordinary promote-the-module refactor does it as a
side effect, which is exactly how three of these entries died and, with the
symbol rename, how the other two stopped matching.

This is the same shape as a field renamed to clear a name-matching check: the
matcher stops seeing it and the reality is unchanged. It is worth separating
from the more familiar failure of building something and never exercising it,
because this is not a gap in what was built - it is a way for a gate to be
walked past without anybody deciding to walk past it. Fixing the scanner is
owned elsewhere; when it lands, the three retained entries answer a live
occurrence again, which is why retaining them is the useful choice as well as
the honest one.

### What this Step does not close, measured rather than estimated

The inventory is stale in both directions and this change addresses only one of
them. After it: 32 documented entries against 127 live test-only reaches, of
which 98 are undocumented. The count ratchet and the set-equality check both
still fail, and deleting entries makes the ratchet worse rather than better.

Two standing facts, both measured, both unowned, and neither absorbed here:
98 undocumented live test-only reaches, and 114 live production cross-package
private reaches against a hard-zero baseline. The three delegate-wrapper
exemptions are a separate refactor with 2, 7 and 23 live consumers
respectively, not an inventory edit.

No entry was added to make any count reconcile. The standing instruction
against that assumed a mismatch of two or three; at a hundred it is not a
bookkeeping question, and the reaches are real.

### Provenance

The inventory change was captured by a concurrent broad commit under a subject
about refreshing the inventory. The content at the main line is correct and was
verified there afterwards: 32 entries, the two corrected symbol names present,
the three retained entries present.
