---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S05'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
  - "[[2026-07-25-test-harness-honesty-false-green-gates-audit]]"
  - "[[2026-07-25-test-harness-honesty-adr]]"
  - "[[2026-07-09-size-budget-refactor-adr]]"
---

# Refresh the module size-budget pins that are documented as having no headroom while sitting far above actual, since a stale ceiling permits silent regrowth up to the gap and the gate reports green throughout

## Scope

- `src/cadrumo/tests/test_data_size_budget.py`

## Description

The Step row names the shipped-data BYTE budget module. The finding it cites is
about per-module and per-callable LINE-limit overrides, which that module does
not carry: it measures summed file bytes under the bundled data tree and has no
pin table. The real owner of the described defect is
`src/cadrumo/tests/test_codebase_size_budgets.py`, with a sibling subset in
`src/cadrumo/entrypoints/cli/tests/test_cli_module_size.py`. Work was executed
against the real owners; the named module was read and left untouched.

- Measure every pin against its subject and record the gap.
- Add `src/cadrumo/tests/_size_budget.py` as the single measurement, policy, and
  baseline substrate, re-exported through the test package facade.
- Add `dev/audit/size_budget.py` as the generator and reporter, mirroring the
  sibling complexity ratchet's committed-baseline convention.
- Generate `dev/audit/size_budget_baseline.json` and seed its prose-only note
  section from the load-bearing half of the retired comments.
- Rewrite the codebase gate to read the generated table and enforce both
  directions of the band.
- Project the CLI sibling gate's limits from the same table instead of a second
  hand-maintained copy.
- Correct a dangling symbol reference in the complexity auditor's docstring.

## Outcome

Measured at the recorded commit, aggregate positive slack was 9139 lines across
the module pins and 699 across the callable pins. The three worst production
entries were the overview calendar module pinned 1667 against an actual 947, the
registry applicability module 2156 against 1656, and the modelo
verification-actions module 1750 against 1394; the widest callable pin was the
M100-from-M130 projection at 290 against 146. Thirteen module pins and six
callable pins had fallen below the default limit entirely, so those overrides
were dead weight granting unbounded room. The largest single window permitted
1261 lines of regrowth.

The limits are now generated rather than hand-written, because the comments were
what decayed rather than the mechanism. The ratchet became two-sided: growth past
a limit fails as before, and a limit drifting further above its subject than the
declared slack tolerance now also fails, so staleness self-reports instead of
silently permitting. The headroom policy is declared once in code and never
restated in prose that can rot: a limit is the measured size plus five percent,
the tolerated slack is ten percent of the limit, each with a small absolute
floor. Zero-headroom pinning was the predecessor's stated policy and is what
generated the churn, since in a tree with many concurrent authors it reds on the
next landing and is hand-raised, and the hand-raise is where the prose went
stale. Aggregate declared module headroom is now 1689.

Replaying the retired pin table through the new check reports seventeen stale
modules and nine stale callables that the previous gate passed silently.

Regeneration is structurally unable to launder a live offender. The accepted
size-budget decision rejected raising a ceiling in place of refactoring and
deliberately left real offenders failing loudly, so limit generation clamps any
subject already over its prior ceiling to that ceiling; raising past a broken
ceiling requires an explicit growth-acceptance flag. The four modules over budget
before this change stay red at byte-identical limits, one of them a deferred
peer-owned offender named in that decision.

Discrimination was proved by measurement rather than inspection. A real
thirteen-hundred-line module placed in the scanned tree made the real gate fail
naming that module and its exact count, and was then removed. Stale detection was
driven against the real measured corpus with an inflated limit and reported the
exact permitted regrowth window. Both ratchet directions, the dead-weight case,
the vanished-subject case, the corpus floor, and the anti-laundering clamp each
carry a permanent positive control that drives the production scanner over a real
on-disk tree. The corpus floor fired for real during development, catching a
count taken over the wrong population.

Both gates collect eighteen tests, of which sixteen pass and two carry the
pre-existing offender signal unchanged. Full-tree collection is clean at 14389
tests. Lint, format, and type checks pass on every authored file, and the
generated API stub tree reports no drift.

## Notes

The gate is committed RED on four modules. This is the pre-existing state, not a
regression: the same four exceeded the same limits before this change, and the
governing size-budget decision states that the gate continuing to fail loudly on
unextracted offenders is the correct and intended signal. Making it green would
have required absorbing real growth, which is the defect class this campaign
closes. The four are the modelo reconcile module, the core config module, the
registry ledger-bindings module, and the CLI config package root.

One override was tightened on a module carrying live peer WIP: the CLI config
payloads module lost its pin because it now measures below the default. The peer
edit was verified to be SHRINKING that module rather than growing it, so the
tightening runs with the owner's direction rather than against it. Twenty other
modules already live within sixty lines of the default with no override, so this
is the ordinary condition rather than special treatment.

Semantic code search was measured degraded for this session, reporting itself
available while serving a truncated index. Discovery was carried by exhaustive
targeted search over the concept vocabulary plus direct reads of the owning
packages' facades and module docstrings, which is how the second gate carrying
duplicate pins and the governing prior decision were both found. The vault index
was healthy and was used for decision recall.

Not fixed, and left for owners: the four offenders above need cohesive-sibling
extraction, and the Step row's cited file path names the wrong module.
