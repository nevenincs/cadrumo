---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:51840a3816745964517d77451a524507040ed3dc2dc8daa2e435fc2dc46ce000'
step_id: 'S320'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Close the import-hygiene scanner's blind spot, which lets a module rename launder a live cross-package private reach past the gate: `find_private_import_violations` in `dev/quality/import_hygiene_scan.py` skips any import site whose target MODULE carries no private component, and never inspects `imported_names` at all -- it records them on the violation but never gates on them. So `from ...wizard.widgets import _redact_validation_context` is invisible: the module is public, the symbol is private, the reach is cross-package and unchanged. Promoting a private module to a public name therefore clears every private-SYMBOL reach into it from the gate while changing nothing about the coupling, which is the same defect class as clearing a credential check by renaming the field -- the matcher stops seeing it and the reality is untouched. Five of the nine entries S317 found dead were dead for exactly this reason rather than because anything was fixed. Gate on a private imported NAME as well as a private target module, then re-measure: expect the live counts to rise, and report the new number rather than tuning it. Prove the blind spot is closed with a site importing a private symbol from a public module, asserted invisible before and caught after, and keep a site importing a public symbol from a public module asserted clean in both directions so the widening does not swallow legitimate imports

## Scope

- `the import hygiene scanner`
- `its gate tests`
- `and a re-measurement of the live violation counts once names are inspected`

## Changes

- `M` `dev/quality/import_hygiene_scan.py`
- `M` `dev/tests/test_import_hygiene_gate.py`
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py -n0 -k "private_name or public_name or dunder or mixed_import"` -> `pass`
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py -n0` -> `fail`

## Notes

### What was closed

The scanner decided whether an import reached into a foreign package's privates
from the target module path alone. It recorded the imported names on every
violation it built and never used them to decide whether there was one. A
private symbol imported across a package boundary from a public module was
therefore invisible.

The consequence was not a missed edge case but a laundering route: promoting a
private module to a public name cleared every private-symbol reach into it from
the gate while no import changed and no coupling was removed. Nobody had to
intend it, which is what made it dangerous - an ordinary refactor did it as a
side effect, and the gate then reported the reaches as resolved.

Both shapes are now judged. A private module path is unchanged. A private
imported name is new, and it carries the same ownership exemption the module
rule already applied, asked on the other axis: a private symbol belongs to the
module that defines it, and that module's own package is the boundary it is
private within, so siblings inside that package are exempt and anything outside
is a reach.

### The new numbers, reported rather than tuned

Inspecting names makes reaches visible that were always there:

- production cross-package private reaches: **114 to 137**
- test-only reaches: **127 to 165**
- test-debt entries answering no live reach: **3 to 0**

Sixty-one sites became visible across thirty-three distinct target-and-name
pairs. No baseline and no inventory was touched to accommodate them. The rise
is the scanner reporting what it previously could not see; the coupling it
names is not new.

The largest single group is a shape the old rule could never catch: a private
SUBMODULE imported by name from its public parent package. Twenty-five sites
import one private storage submodule that way. Those were private-module
reaches all along, hiding as name imports because the recorded target was the
public parent.

The three entries deliberately retained in the preceding inventory Step now
answer live occurrences again, exactly as that Step predicted they would. That
prediction coming true is the cleanest available evidence that retaining them
rather than deleting them was the correct call.

### What the gate says now

Six assertions still fail and fifty-eight pass, five of the passes being the new
ones. The failure composition changed in a way the totals hide: the dead-entry
assertion no longer reports a single entry without a reach, and now fails
solely because reaches occur that no entry records. The inventory's staleness
has moved entirely to the undocumented side, which is the honest direction for
it to sit while the reaches themselves are unowned.

### Mutation proof

Three deliberate breakages, each confirmed to red exactly the assertions it
should, all applied by runtime monkeypatch from a plugin outside the repository:

- restoring the module-path-only rule reds the two assertions that detect a
  private name through a public module, and nothing else - this is the direct
  proof the blind spot is closed;
- widening greedily so every imported name is treated as private reds the three
  assertions that keep legitimate imports clean, proving the fix is not the
  lazy version of itself;
- removing the owning-package exemption reds the in-package assertion, proving
  that exemption is load-bearing rather than decorative.

The suite deliberately holds assertions in both directions. A rule that only
catches more is satisfied by flagging everything, so a public name through a
public module, a private name reached inside its own package, a mixed import
reported for only its private half, and a dunder used for structural
introspection are all asserted clean.

### Not addressed here

The counts this change reveals are unowned. 137 production reaches against a
hard-zero baseline and 165 test-only reaches against 32 documented entries are
campaigns rather than Steps, and nothing here narrows either. The delegate
wrapper exemptions remain a separate refactor.
