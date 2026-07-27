---
tags:
  - '#audit'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
  - "[[2026-07-27-conformance-cli-adr]]"
---

# `conformance-cli` audit: `fact lifts and boundary gate`

## Scope

Mandatory code review of the four landed conformance-cli commits: `2b93b08f0` and
`623d925b0` (external-oracle grounding lift into
`src/cadrumo/domain/calculations/registry/_external_grounding.py` and
`src/cadrumo/core/_external_oracle_corpus.py`, with the re-pointed gate),
`9c64ec0d99` (fichero-BOE required-set extraction into
`src/cadrumo/application/filing/_export.py`), and `43d7ab1e60`
(`src/cadrumo/tests/test_dev_path_isolation.py`). Reviewed against the accepted ADR,
the plan, and project rules. All reviewed files re-verified unchanged at HEAD
`bbc05fcdef`; peer WIP existed on `_schema.py` and `_schema_base.py` (the P01
governance stamp) but touched nothing under review.

Verification actually run by the reviewer: the three re-pointed and new gates (23 + 3
passed), both grounding honesty directions mutation-flipped independently against the
real registry, the required-set relaxation reproduced numerically against the live
M130 and M390 registry, `apidocs scaffold --check` clean, `ruff check` clean on all
five files, and the pre-existing import-hygiene gate run for cross-check.

Verdict: REVISION REQUIRED. Both high findings were remediated in-campaign
(`075aacb041`, `a28293ce04`); the remaining findings are tracked as plan Steps.

## Findings

### required-set-oracle-collapse | high | The fichero-BOE extraction removed the only test that could detect a relaxation of the required-set predicate

CONFIRMED, reproduced. `required_applicable_casilla_ids`
(`src/cadrumo/application/filing/_export.py:1005`) became the callee of both the
production gate `assert_export_mirrors_manifest` (`_export.py:1124`) and the two tests
that pin it (`tests/test_export_completeness_gate.py:77`,
`tests/test_fichero_boe_completeness_parity.py:110`). Subject and oracle collapsed into
one function, so the tests could no longer detect a change in its semantics.

Failure scenario, measured against the live registry: relaxing the predicate to
`schema.formula is not None` (dropping the `or schema.required` clause) shrinks M130's
required-applicable set 12 to 11, dropping casilla `02` (schema-required, formula-less).
`test_thin_fixed_width_draft_panics_before_writing` picks
`sorted(required_applicable & valued)[0]`; before the extraction the test's mirrored
copy produced the full 12-element set and picked `02`, so the relaxed production gate
would not panic and `pytest.raises(FilingExportError)` would fail, catching the
relaxation. After the extraction the test picks from the relaxed set, gets `03` (a
formula casilla), the gate panics, and the test passes. Net effect: M130 casilla `02`
silently leaves the pre-write completeness gate, a fixed-width fichero can be written
with that slot blank behind a valid SHA-256 digest, and nothing in the filing suite
reds. Precisely the failure `modelo-export-mirrors-official-structure` exists to prevent.

The recorded mutation proof (`return frozenset()` producing three failures) did not
cover this: an empty return kills the fixture floors rather than flipping an assertion.
It proved the function was called, not that its semantics were pinned.

REMEDIATED in `075aacb041`. A registry-grounded partition reads `formula` and `required`
off the `CasillaCollection` directly, never calling the function under test; each
predicate clause is pinned separately with named anchors whose qualification is re-read
from the registry. Both relaxation directions now flip real assertions (4 failures and
5 failures respectively, against a 15-passed control).

### dev-path-literal-hole | high | The metadata-loophole check could not see the only realistic form the violation would take, and a green test pinned the hole open

CONFIRMED. `_looks_like_dev_path` (`src/cadrumo/tests/test_dev_path_isolation.py:210`)
fired only on string constants starting with `dev/`, `./dev/`, or `../dev/`, and
`test_path_literal_scanner_does_not_fire_on_path_join_usage` (`:534`) asserted as a
deliberate ruling that a `PROJECT_ROOT` join was not a violation.

That join is the form a real violation takes. A bare `open("dev/baseline.json")` is
CWD-relative, would fail for any invocation outside the repo root, and would not survive
one test run. The working form is a `PROJECT_ROOT`-anchored join, and `PROJECT_ROOT` is
exported from `src/cadrumo/core/paths.py`, which the gate itself imports at line 44. A
shipped module could therefore read a `dev/`-rooted baseline, break for every
wheel-installed user, and leave both this gate and `dev/import_hygiene_scan.py` green.
Also missed for the same reason: f-string composition, `os.path.join("dev", ...)`, and
the Windows-separator form. The ADR's stated purpose for this check was therefore unmet
for the realistic case, and the pinned non-firing test made it worse than an omission: a
future author closing the hole would first have to delete a green test that read as a
deliberate scope ruling.

REMEDIATED in `a28293ce04`.

### grounding-gap-observed-not-gated | medium | The attribution gap is typed and recorded, but nothing asserts on it

CONFIRMED by execution. `load_bundled_external_oracle_inventory` returns one
`UnattributedOraclePayload` (the M303 prorrata payload, gap
`payload_name_lacks_modelo_and_filing_year`), and the audit returns 90 rows, 9 checked
revisions, 58 declared groundings, 0 findings, coverage 0.0460, 0 unmatched evidence. No
test reads `unattributed_payloads` for size or content, and no test reads
`unmatched_evidence` at all. `test_every_bundled_oracle_payload_is_accounted_for`
asserts only that evidence united with unattributed equals what is on disk, which the
fold satisfies by construction. It is a real drift detector for a re-introduced skip or
a dropped corpus directory, but structurally incapable of failing on a growing gap set:
a second year-less payload landing tomorrow reaches no revision and nothing reds. The
screen-not-gate posture is ADR-sanctioned, but no screen consumes the field yet, so
`unmatched_evidence` currently has zero readers.

### dev-gate-second-authority | medium | Half the boundary gate duplicates a shipped, already-gated detector, and the copies have already diverged

CONFIRMED. `src/cadrumo/tests/test_import_hygiene_gate.py:524` already carries
`test_no_shipped_module_imports_the_unshipped_dev_tooling`, with four anti-tautology
proofs, delegating to `find_dev_tooling_import_violations`
(`dev/import_hygiene_scan.py:460`); it passes today alongside the new duplicate. The new
module re-implements the shipped-module test, the dev-target test, the dynamic-target
walk, and the static-import walk. The stated justification (the gate must not import
`dev.*`) does not hold: the module is a test, excluded from the wheel, and the existing
gate's docstring rules that a test tree's `dev.` import is permitted by design; both
scanners already accept an injectable root. Divergence has already begun: the
shipped-`conftest.py` case is proven at `test_import_hygiene_gate.py:623` and absent
from the new module. The ADR text asks the boundary test to extend the hygiene gate with
a path-literal assertion only; the import half was not requested.

### oracle-corpus-token-not-hydrated | medium | The core enum is documented as hydrating a stored token that nothing reads

CONFIRMED. `src/cadrumo/core/_external_oracle_corpus.py:16-21` states that the member is
byte-identical to the stored `source_kind` token so a stored token hydrates and an
unknown token is refused at the boundary. `_read_oracle_payload`
(`registry/_external_grounding.py:498`) never reads `source_kind`; the corpus is
assigned from the directory-to-enum map at line 72. A manual-oracle payload declaring
any garbage token is silently classified by its directory, and `evidence_corpora`
misreports its provenance. Same root cause: the payload is read as an untyped
`json.loads` mapping with bare `.get()` calls (lines 522-536), the `dict[str, Any]`
boundary shape the architecture-boundaries rule bars, inside an otherwise exemplary
strict-frozen module.

### second-revision-resolver-on-public-facade | medium | A period-agnostic non-raising revision resolver sits on the public facade beside the law-determined one

PLAUSIBLE; no misuse today, the hazard is prospective. `select_revision_for_filing_year`
(`registry/_external_grounding.py:385`) is exported through the registry package
`__all__`. Its docstring is honest about being deliberately period-agnostic and total,
unlike `select_revision`, which resolves a filing-year and period pair and raises when
none or several match. But the facade export places it in the same namespace with a more
inviting name for a caller holding only a filing year. The
`revision-resolution-is-law-determined` rule requires every production calculation,
verification, filing, export, and projection path to resolve through the law-determined
resolver; a calc path reaching for this one would drop the period axis and abstain with
`None` where the law-determined resolver raises. No gate polices which resolver a calc
path uses.

### gate-scope-narrower-than-adr-text | low | The gate scopes to shipped modules, the ADR ruling says the whole tree

The ADR states that `src/cadrumo/**` must never import `dev.*` nor read `dev/**` paths
at runtime. The gate scopes to wheel-shipped modules, excluding test trees, a narrowing
the executor documented and grounded in the pre-existing hygiene ruling. The narrowing is
correct on the merits: an excluded test tree's reach cannot affect an installed user, and
the hygiene gate legitimately reads a `dev/` test-debt baseline today. But the ADR text
was not amended, so record and code state different rules. Correct the ADR wording, not
the gate.

### record-honesty | low | Exec records are accurate on substance, two claims overreach

The exec records for S06, S07, and S18 match their diffs; the S18 test enumeration,
module count, and excluded-tree ruling all check out, and its vacuity floor is realistic.
The S05 record's honesty about the truncated search index and the deliberate hold is
exemplary, and its peer-versus-owner triage of the scoped-suite reds is correct (two
reproduced, owned by a sanitizer campaign, untouched by this work). Overclaims: the
`source_kind` hydration claim in S05, and S08's assertion that its mutation confirmed
non-vacuity, which the first finding disproves.

### m303-prorrata-deferral | medium | Deferring was right, for a different reason than recorded, and the payload is malformed against its own corpus convention

CONFIRMED by execution. The payload carries modelo 303 and filing year 2025, but the
attribution gap is returned before the file is read, so its declared fields never
participate and the filename is the sole attribution key. Attributed properly it
resolves to the 2023-y-siguientes revision and yields: `iva.prorrata-volumen-total`
(45000.00, manual input, not reconciled), `iva.prorrata-volumen-con-derecho` (25000.00,
manual input, not reconciled), `iva.prorrata-porcentaje` (56, computed, reconciled,
clean), and casilla `44` (-217.60, manual, no formula, not reconciled).

The executor's arithmetic was right and the deferral was right, but the
characterisation matters for the follow-up: two of the three are not registry defects.
The two volume figures are the scenario's INPUTS, the prior and current-year operation
volumes the manual states as givens, correctly modelled as manual input casillas. The
payload has stuffed scenario inputs into the expected-values map that every other
bundled oracle reserves for outputs, which is why the corpus currently folds to zero
findings. Widening the attribution rule would therefore red the gate on two false
positives plus one real gap, and renaming the file alone would import a malformed
payload into the gate.

The one real item is casilla `44` (regularización prorrata por porcentaje definitivo,
cuota), which the AEAT manual derives arithmetically and which the registry models as a
manual input with no formula and no binding: a genuine no-silent-under-declaration-shape
gap, a computable regularización left to operator entry with a bundled AEAT figure
beside it that no gate consumes. Not blocking, pre-existing, and it does not produce a
wrong number (a manual input is unentered, not silently zero); prorrata regularización
is a fourth-quarter surface.

## Recommendations

Restore an independent oracle for the fichero-BOE required set by classifying casillas
off the registry collection rather than off the function under test, with each predicate
clause pinned separately, so the assertion flips when the predicate is relaxed in either
direction rather than only when it returns empty. Landed as Step S26.

Close the dev-path literal hole by extending detection to root-anchored joins,
`os.path.join`, f-string segments, and the backslash separator, and invert the test that
pins the hole open into a firing proof; confirm the widened check still finds zero real
violations before hardening. Landed as Step S27.

Give the attribution gap a reader before the CLI phase closes: surface unattributed
payloads and unmatched evidence as report and coverage rows in screen posture, with a
shrink-only floor asserting the gap count does not grow. Tracked as Step S29.

Make the `source_kind` hydration claim true by parsing each oracle payload through a
strict typed model carrying modelo, filing year, corpus, and expected values, and
cross-check the hydrated corpus against the directory the file was found in; that
removes the module's only untyped boundary and makes an unknown token a loud refusal as
documented. Tracked as Step S28.

Split the scenario inputs out of the M303 prorrata payload's expected-values map and
rename it to carry its filing year, so its one genuine expected figure enters the
honesty relation. Tracked as Step S30. Separately, model M303 casilla `44` as a computed
regularización grounded in LIVA articles 105 and 106, with the manual figure as its
external-oracle expectation. Tracked as Step S31.

Two questions are architecturally significant and a follow-on ADR must rule on them
rather than an executor settling them. First, boundary-detector ownership: whether the
dev boundary is enforced by one authority (the hygiene scanner, with the path-literal
check added as a new family) or by two deliberately independent ones; the current state
is neither, being one authority silently forked. If independence is chosen, the
duplication must be declared, the shipped-conftest case mirrored, and a divergence gate
added comparing both detectors on the live tree. Second, whether the filing-year
grounding resolver belongs on the public registry facade at all, or should stay
module-private or be renamed so it cannot be mistaken for the law-determined path; the
absence of any gate policing resolver choice on calculation paths is itself worth a Step.
Tracked as Step S32, which also amends the ADR boundary wording to name wheel-shipped
modules.
