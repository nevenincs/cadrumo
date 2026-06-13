---
tags:
  - '#audit'
  - '#docs-educational-surface'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-02-docs-educational-surface-audit]]"
  - "[[2026-06-01-docs-educational-surface-adr]]"
---



# `docs-educational-surface` audit: `Modelo 303 calculate verified working; user-doc 130 flow execution-verified`

## Scope

Verification pass over the user-documentation corpus, triggered by two
questions: (1) is Modelo 303 `calculate` actually broken, as the userdocs
kickoff brief asserted (`NameError: IvaRate`), and (2) do the commands the
user docs cite actually run and produce the documented outputs. The corpus
itself (landing page, quickstart, profile-setup, tutorial, how-to recipes,
import, reconcile, filing-calendar, troubleshooting, explanation, glossary,
README map) was authored and reviewed in the preceding campaign; this audit
adds execution verification against the live CLI in an isolated storage root
(`AEAT_LOCAL_STORAGE_ROOT`), so shared profile state was never touched.

## Findings

### F1 (resolved) Modelo 303 is NOT broken; the `NameError: IvaRate` was fixed

The kickoff brief's claim that 303 `calculate` is broken is stale. Evidence:

- `IvaRate` is defined in `src/aeat/domain/invoices/_enums.py` and the
  iva-to-invoices import cycle that produced the `NameError` was resolved by
  the lazy-binding fix (commit subject `fix(iva): lazy-build
  IvaRate->IvaRateKind/IvaCategory dicts to break iva<->invoices cycle`).
  The `IvaRate = object` line in `src/aeat/domain/iva/_invoice_classification.py`
  is an intentional `TYPE_CHECKING` cycle-break, not a defect.
- `aeat app modelo describe 303` resolves cleanly (revision
  `2023-y-siguientes`, 115 casillas, 8 bindings, 13 formulas).
- `aeat app modelo work calculate` on a 303 work unit runs the engine and
  refuses with instructive, law-grounded validation gates, not a crash:
  first the unset ledger-aggregation / `compensacion-pendiente-anteriores`
  bindings, then a requirement to initialise the IVA compensation wallet
  (`aeat app modelo iva-wallet seed`, citing LIVA art. 99.5, Ley 37/1992,
  `first_period_zero`). These are correct domain preconditions for a quarterly
  IVA self-assessment, not bugs.

Conclusion: 303 is a functional, sophisticated path. A fully green 303
worked-output example was not produced here only because the IVA-wallet seed
period semantics need one more step; the engine itself is healthy.

### F2 (verified) The Modelo 130 user-doc flow executes end-to-end with correct figures

Running the quickstart / tutorial 130 flow in the isolated storage root:

- `work create --modelo 130 --year 2024 --period 1T --revision 2019-y-siguientes`
  returns a work-unit id (confirming the revision-id correction landed in the
  prior campaign; `2009-y-siguientes` does not exist for 130).
- `work calculate` with `--casilla 01=12000 --casilla 02=4000` and the
  `irpf.previous_year_economic_activity_net_income` binding persists a draft
  and computes `casilla 07 = 1600.00`, which exactly matches the tutorial's
  documented worked example (12000 - 4000 = 8000; 20% = 1600), plus
  `casilla 19 = 1500.00` final result.
- `work verify` grants `verificado_completo` (`completeness_status = complete`,
  `missing_required_casilla_count = 0`, `finding_count = 0`).
- `export` correctly enforces a precondition (the declarant `identity.name`
  / `identity.surnames` must be set, which the interactive profile wizard
  collects but `--quiet --accept-defaults` skips) - verified-correct gating,
  not a bug.

### F3 (transient, peer-owned) Two shared-branch breakages observed during verification

Not caused by the documentation and not in this campaign's scope to fix
(per the worktree-safety and swarm rules); recorded for awareness:

- `export` triggers full registry validation, which currently fails on an
  in-flight Modelo 151 registry edit (`m151-impatriado-calculation` missing
  legal refs `rd-439-2007:art-113` and referencing unknown application links
  `modelo-151-review/-approval/-reconciliation/-workflow`). This blocked the
  final fichero-BOE file write for the otherwise-verified 130 work unit.
- Earlier in the session the CLI command tree briefly failed to resolve on a
  `ModuleNotFoundError: No module named 'aeat.core.profile'` (a `SetupAnswers`
  relocation whose importer lagged); it cleared when the peer relocation
  committed. A duplicate key at `pyproject.toml:447` continues to block
  `uv run`, so the CLI was driven through the venv interpreter directly.

## Recommendations

- Treat the "303 is broken" caveat in the userdocs kickoff brief as obsolete.
  No user doc asserts 303 is broken, so no documentation change is required;
  the quickstart and tutorial sensibly use Modelo 130 (fewer preconditions:
  no IVA wallet) and the `how-to` index already carries a full 303 recipe.
- The user-doc command flow for Modelo 130 is verified accurate; leave it as
  authored. A 303 worked-output example may be added once the IVA-wallet seed
  step is captured end-to-end and the peer Modelo 151 registry edit lands.
- Re-run the docs conformance gate and the `-n -W` build to re-confirm green
  once the peer Modelo 151 registry edit and the `pyproject.toml` duplicate
  key clear.

## Codification candidates

None. The one durable lesson this pass reinforces - re-verify a brief's
"known blocker" against the live CLI before letting it constrain the docs,
because in-flight refactors make such caveats go stale - is already covered by
the existing "ground every command against the live CLI" principle in the
documentation rules and the calculation-grounding rule. No new project-shared
rule is warranted.


