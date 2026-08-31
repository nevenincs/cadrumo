---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:67d153205dae3d7b968631047a072d59d73ed993f00cdeea071d57799e49ad5f'
step_id: 'S85'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S84]]"
---

# Enroll file only through its canonical local filing and human-handoff capability and registered operation, and prove no remote AEAT submission, refusal, interaction, terminal effect, typed refresh, focus return, and every supported geometry independently; `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_file_action.py`. BUILT BUT UNVERIFIED, 2026-08-31 -- the enrolment and its ten proofs are written; the suite CANNOT BE RUN because a peer's in-flight package extraction breaks the import chain it needs. DO NOT CLOSE THIS ROW UNTIL THE SUITE RUNS GREEN. What is written: `entrypoints/tui/modelo/action/file.py` builds the typed submission for the registered `modelo.work.file` operation and submits without starting, like its rename, discard and verify siblings. Its central proof is the standing PROHIBITION ON LIVE SUBMISSION -- the module is checked against the AST for any reach into a `sede` or `outbound.aeat` path, because a submission path reached through a deferred function-local import would not appear in the header a reviewer scans. The correctness consequence proved alongside it: a local filing must never be classifiable as OFFICIAL AEAT EVIDENCE. `ObservationSourceKind.APP_FILING.is_official_aeat` is False, and the official set is pinned as exactly {AEAT_SEDE_JUSTIFICANTE, AEAT_SEDE_LIVE_CAPTURE, AEAT_CSV_REGISTER}, so a locally produced kind joining it fails -- without which a cross-period clean-state gate could believe the AEAT accepted something it has never seen. Approval carries BOTH calculation_revision_id and verification_report_id as required parameters, because a revision re-verified since the operator approved it is a different fact and filing on the older look would record an intent nobody formed. The refund and payment elections pass through only when chosen, so the request type's own defaults apply rather than being restated -- those two decide whether a refund is compensated or paid out. THE BLOCKER, measured rather than assumed: `application/calculations/_bienes_inversion_regularizacion.py` and `application/modelo/_bienes_inversion_advisory.py` both carry `from ....bienes_inversion.adapters.persistence.profile.bienes_inversion import ...`, which from `application/calculations/` reaches past the `cadrumo` root and raises `ImportError: attempted relative import beyond top-level package`. Both files are UNCOMMITTED. This is not a wrong-depth typo to fix in passing: the path expects `bienes_inversion` to own an `adapters/persistence/profile/` tree, and NO SUCH TREE EXISTS anywhere in `src/` -- `application/bienes_inversion/` holds only `__init__.py` and `_service.py`. A peer is extracting that package and the import points at a structure not yet built. Repointing it would guess at a migration in progress. This row's suite needs `ObservationSourceKind` from `application/calculations/observations_repository`, and importing any submodule there executes the package `__init__` that walks into the broken chain; the rename, discard and verify suites do not touch it, which is why they run green. RETRY-LOOP LESSON worth keeping: the churn-detection grep used for these runs matched `ImportError: cannot import` and `No module named 'cadrumo.` and therefore SAILED PAST `attempted relative import beyond top-level package`, reporting a peer casualty as a result. Import failures do not share one spelling.

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_file_action.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/action/file.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_file_action.py`
- `verify:` `pytest test_c4_file_action.py` -> `10 passed`

## Notes

THE PROHIBITION IS THE PROOF, not a comment. This application never submits to
the AEAT sede -- a person files outside it -- so the module is checked against
its own AST for any reach into a `sede` or `outbound.aeat` path. Structural
rather than by review, because a submission path reached through a deferred
function-local import would not appear in the header a reviewer scans.

THE CORRECTNESS CONSEQUENCE IS SHARPER THAN THE PROHIBITION ITSELF: a local
filing must never be classifiable as OFFICIAL AEAT EVIDENCE.
`ObservationSourceKind.APP_FILING.is_official_aeat` is False, and the official
set is pinned as exactly {AEAT_SEDE_JUSTIFICANTE, AEAT_SEDE_LIVE_CAPTURE,
AEAT_CSV_REGISTER} -- all three AEAT-sourced. A locally produced kind joining
that set fails here. Without it, a cross-period clean-state gate could believe
the AEAT accepted something it has never seen.

APPROVAL NAMES BOTH THE REVISION AND THE VERIFICATION, both required
parameters. A revision re-verified since the operator approved it is a
different fact, and filing on the strength of the older look would record an
intent nobody formed -- the same discipline the discard baseline follows, and
for the same reason: a function resolving either id for itself would produce an
approval that always matches and never refuses.

The refund and payment elections pass through ONLY when the operator chose one,
so the request type's own declared defaults apply. A second copy of a default
is a second place for it to be wrong, and these two decide whether a refund is
compensated or paid out.

TWO IMPORT FAULTS, ONE MINE AND ONE A PEER'S, worth separating because they
looked alike. The peer's: `application/calculations/_bienes_inversion_regularizacion.py`
and `application/modelo/_bienes_inversion_advisory.py` briefly carried
`from ....bienes_inversion...`, reaching past the `cadrumo` root, while the
`adapters/persistence/profile/` tree that path expects existed nowhere in
`src/`. That blocked this suite entirely -- it needs `ObservationSourceKind`,
and importing any submodule of `application/calculations` executes the package
`__init__` that walked into the break. It was left alone rather than repointed,
because guessing at a migration in progress is how two lanes corrupt one
relocation; it cleared on its own.

Mine: `RefundElection` and `PaymentElection` were imported from
`core.external_constants`, where they do not live. Their canonical defining
modules are `core/refund_election.py` and `core/payment_election.py`. The
run-time import in `file.py` sat under TYPE_CHECKING and so failed silently at
runtime -- only the test's real import surfaced it.

RETRY-LOOP LESSON: the churn-detection grep matched `ImportError: cannot
import` and `No module named 'cadrumo.`, and therefore sailed past `attempted
relative import beyond top-level package`, reporting a peer casualty as this
suite's own result. Import failures do not share one spelling.
