---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:3aa69d5604a2372fa9a2db9dc976069b6b5562fcf0226daf0295be7fdc95d6d0'
step_id: 'S30'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Decide the antecedent for the six Modelo 123 fed casilla 0597 suffered-retencion carries, because the predicate SHAPE extends from the trabajo case and the antecedent does not. S28 declared an ADVISORY implies_nonzero predicate for casilla 0596 on all six Modelo 100 revisions, with antecedent 0012, the gross total ingresos integros del trabajo, chosen because retencion is computed on gross. Capital mobiliario ahorro has no equivalent. Its declared semantic roles are per-source components, dividendos, intereses de cuentas, letras del Tesoro, otros activos financieros, PALP and deuda subordinada o preferentes, plus a rendimiento neto and a rendimiento neto reducido. So the only single-casilla candidate is a NET figure, which carries the exact objection raised against casilla 0025 in the trabajo case: it is post-gastos and can be zero for a filer who did suffer withholding, which would suppress the advisory in the cases it exists for. The objection is milder here because deductible gastos on capital mobiliario are narrow, but that is a tax judgement about a different income class and making it by analogy to the trabajo case is the reasoning this campaign forbids. The alternative is summing the per-source components, which must be read as what it is, a NEW DERIVATION requiring its own grounding and its own casilla, not a cheaper way to get a predicate. Correction to carry into this row: both S28 and the dispatch that set it described these carries as already expressible against existing capital-mobiliario antecedents, and that is too strong. Computed capital-mobiliario casillas do exist so an antecedent is available, but none is the gross-income analogue, so expressible understates the judgement still required. Gate: the chosen antecedent is justified against the net-figure objection rather than selected for availability, the advisory holds silently for a filer with no capital mobiliario income, its text names the payer certificate rather than a capture since the taxpayer never filed Modelo 123, and if no sound antecedent exists the row records that with the reason instead of declaring a predicate over a figure that cannot support it

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100`
- `src/cadrumo/application/modelo`

## Description

- Re-derived the capital-mobiliario-ahorro casilla set from THIS revision's
  own `semantic_role` values rather than trusting the row's own
  enumeration, mirroring S28's own corrective discipline (a label search
  had missed S28's antecedent too). Found casilla 0036
  (`irpf_rendimiento_capital_mobiliario_ahorro_total_ingresos_integros`),
  a computed GROSS total summing the nine per-source components (0027
  through 0035) — the row's premise that "capital mobiliario ahorro has no
  equivalent [to 0012]" is REFUTED: 0036 is exactly that equivalent, and
  the row's own listed semantic roles simply omitted it.
- Verified 0036 and casilla 0597
  (`irpf_retencion_capital_mobiliario`, bound to the Modelo 123 fed carry)
  both exist, independently, on all six Modelo 100 revisions (2020-2025)
  before declaring anything.
- Declared the ADVISORY `implies_nonzero(["0036", "0597"])` predicate on
  all six revisions, mirroring S28's `implies_nonzero(["0012", "0596"])`
  shape exactly, grounded in `ley-35-2006:art-99`, `art-101`,
  `rd-439-2007:art-90` (already-declared provisions, matching 0597's own
  `legal_refs`).
- Found the per-predicate advisory-message mechanism S28's own record
  described (`resolve_advisory_message_default`) had been DELETED by a
  later commit (`16d7fc2682`, "superseded by locale keys") with nothing
  replacing it: every ADVISORY predicate, including S28's own 0596 one, had
  regressed to the generic "a registry advisory predicate fired for this
  revision" sentence, naming no remedy at all — this row's own gate
  ("its text names the payer certificate") was unmet for a PRE-EXISTING
  predicate too, not only the new one.
- Rebuilt predicate-specific messaging through the CURRENT mechanism
  (locale keys, not Python string defaults): a small
  `_advisory_predicate_finding` dispatch selecting one of three literal
  `message_locale_key` values at three distinct `ModeloVerificationFinding`
  constructor call sites — required by the tree's own
  `test_every_production_verification_finding_constructor_is_locale_neutral`
  gate (S24), which a first, dynamic-return-value draft broke. Two new
  locale keys (`suffered_retencion_trabajo_uncredited`,
  `suffered_retencion_capital_mobiliario_uncredited`) with real values in
  all four catalogues via `dev.locales set`, naming the correct certificate
  and modelo per family, avoiding "pull"/"capture"/"fetch".
- Restored the wording-guard property a dropped test once pinned (matching
  S28's own dropped assertions), against the current mechanism, for both
  predicate families, plus new predicate-declaration/firing/silent tests
  for capital mobiliario mirroring `test_trabajo_retencion_advisory_predicate.py`'s
  exact shape.

## Outcome

THE ROW'S PREMISE WAS PARTLY WRONG, LIKE S22'S WAS FOR S28. A sound,
gross-income antecedent for capital mobiliario ahorro exists on every
Modelo 100 revision (casilla 0036) and was independently verified rather
than assumed from the trabajo shape; the two candidate NET figures (0038,
0040) the row itself already correctly rejected. All six Modelo 100
revisions (2020-2025) now declare the suffered-retencion advisory for
casilla 0597, antecedent 0036, matching the taxonomy S28 established for
casilla 0596.

Beyond this row's own narrow ask, fixed a PRE-EXISTING regression: the
message-specificity mechanism S28 relied on had been deleted with nothing
replacing it, so S28's own 0596 predicate had silently regressed to a
generic, remedy-free message. Both predicates now carry real, distinct,
certificate-naming text in all four locale catalogues, and the gap is
closed via the current locale-key convention (not a reintroduced Python
default), keeping `test_every_production_verification_finding_constructor_is_locale_neutral`
green throughout.

Verification: registry validated against a temp-root copy (never the
shared bundled path) both immediately after the six TOML edits and again
after the code change, `authority.validate_registry()` clean, each
revision showing exactly one `capital-mobiliario` predicate id. New test
modules (24 declaration/firing/silent-holds tests for capital mobiliario,
14 wording-guard tests covering both families plus the negative-dispatch
and distinct-message controls) pass, alongside the existing 24 trabajo
tests (62 total, unchanged assertions). A real out-of-repo `MonkeyPatch`
mutation (rebinding `_BLOCKING_PREDICATE_EVALUATORS`'s `IMPLIES_NONZERO`
entry to always-holds) proved the capital-mobiliario predicate's firing
case correctly reds under the mutation and correctly restores after undo —
the same evaluator mechanism S28 already validated for trabajo, re-proven
for this predicate rather than assumed. `ruff check`, `ruff format --check`,
`ty check` clean on every touched file; `dev.locales audit` and
`scaffold --check` clean across all four catalogues, with both new locale
keys correctly auto-discovered by the AST scanner's `_LOCALE_KEY`-suffix
convention.

Broader regression sweeps: `application/modelo/tests/` (98 pre-existing
failures across a wide, unrelated mix — a shared `Justificante` CSV-pattern
test-fixture regression alone accounts for 28, the rest M145 fixed-width
export, IVA wallet reconciliation, amendment-evidence and work-registry
peer work) and the full `domain/calculations/registry/tests/` and
`application/calculations/tests/` suites from the prior rows' baselines —
none reference this row's own files, symbols, or new test modules by name
in any failure, confirmed by grepping the full logs rather than the
truncated tails.

## Notes

THE SAME LABEL-SEARCH-VERSUS-SEMANTIC-ROLE LESSON S28 RECORDED APPLIED
HERE TOO. The row's own text enumerated capital mobiliario ahorro's
semantic roles and omitted the gross total — an under-count of exactly the
kind S28's own notes warned generalises: "a registry search over localized
labels can miss a casilla that exists... A negative result from a label
search is not evidence of absence." This row's own dispatch repeated that
exact mistake one row later, which is worth carrying forward rather than
treating as row-specific.

DELIBERATELY DID NOT restore the deleted `resolve_advisory_message_default`
Python-code-default function. Commit `16d7fc2682`'s framing ("superseded by
locale keys") was directionally correct even though nothing had actually
migrated to fill that direction yet; reintroducing the deleted function
would have reopened two parallel mechanisms instead of completing the one
the codebase had already chosen. The three-call-site dispatch
(`_advisory_predicate_finding`) is the shape the S24 locale-neutrality gate
actually requires — a literal at each `ModeloVerificationFinding`
constructor call site — discovered only by running that gate red first; a
first draft returning the locale key from a helper function passed every
test I had written but failed that pre-existing structural gate, which is
exactly the kind of gate this campaign's own discipline says to run before
declaring a change complete.
