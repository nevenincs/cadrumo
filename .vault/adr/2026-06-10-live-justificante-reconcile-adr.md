---
tags:
  - '#adr'
  - '#live-justificante-reconcile'
date: '2026-06-10'
modified: '2026-08-15'
body_hash: 'sha256:03bbd39b742ad0058c1e383565f2be33e913af35b939c5423b289646b89130fe'
related:
  - '[[2026-06-10-live-justificante-reconcile-research]]'
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
  - '[[2026-09-02-live-justificante-reconcile-csv-authenticity-wiring-research]]'
---
# `live-justificante-reconcile` adr: `live-sourced justificante reconciliation bridge` | (**status:** `accepted`)

## Problem Statement

The operator-facing modelo reconciliation surface only accepts a justificante PDF
that the operator has already downloaded by hand and points at with a filesystem
path (`modelo_reconcile` in `application/modelo/_reconcile.py`, fed by the
`reconcile` / `reconcile-from-justificante` CLI verbs). Yet the application can
already authenticate read-only to the AEAT sede electrónica and contains a
complete end-to-end routine — `capture_justificante` in
`adapters/outbound/aeat/sede/_walker.py` — that resolves a work unit's expediente,
follows the CSV handle, and downloads the authentic AEAT-signed justificante PDF
into a typed `SedeCapture` (`pdf_bytes`, `pdf_sha256`). The two halves are not
connected: a repository-wide search finds `capture_justificante` / `SedeCapture`
referenced only inside the `sede` adapter and `.vault/` documents — no
application or CLI consumer. `SedeCapture`'s own docstring even declares it is
"consumed by the reconciler", documenting wiring that was never built. From the
operator's seat this is a regression: the app can fetch the receipt but forces a
manual download anyway. This ADR records the decision, derived from the research,
to bridge the orphaned live capture into the reconcile flow.

## Considerations

The decision space and the user-approved choice:

- **Bridge shape — persist-then-reconcile (chosen) vs stream-bytes.** The chosen
  shape introduces a new live-gated capture service that pulls the justificante,
  persists its `pdf_bytes` into the active bucket as an encrypted secure object
  stamped with an official source kind, and then lets the existing local
  reconcile run against the persisted artefact. The rejected alternative
  (`stream-bytes`) would add a `LIVE_SEDE` source kind to `modelo_reconcile`
  itself, capture in-memory, diff, and persist nothing — which breaks the
  deliberate local-only invariant of `modelo_reconcile`, discards the authentic
  PDF, and leaves the official-evidence gate unsatisfied.
- **CLI placement — new live verb (chosen) vs flag on `reconcile`.** The capture
  verb lives in the live command family (alongside `aeat app live expedientes
  capture` and `aeat app live notifications capture`), keeping the live-gate owner
  distinct from the local `reconcile` verb. A `--from-sede` flag on `reconcile`
  was rejected as it blurs the local/live boundary at the operator surface.
  **(CLI NAMING SUPERSEDED by `2026-06-10-cli-pull-file-standard-adr`.** The
  capture verb is renamed `aeat app live justificante pull`, and the reconcile
  sources become a `reconcile pull` / `reconcile file --file` subgroup. The
  separation principle here is preserved; only the verb/flag naming is
  superseded. The application layer is unchanged.)**
- **A mature pattern already exists.** `application/live/` is a package of
  read-only live snapshot services (`ExpedientesService`, `NotificationsService`,
  `CensoService`, `Borrador100`) built on the shared `_snapshot_base`
  abstraction. Each persists encrypted, content-addressed snapshots into a
  `SecureObjectRepository` scoped to the active bucket, behind
  `_AeatAccessGate.require_live_read()`, exposed by an `_app_live_*_cli.py` verb.
  The new feature is a new sibling service, not a greenfield design.
- **The official-evidence gate is the second beneficiary.** The cross-period
  clean-state gate (`application/calculations/_cross_period_clean_state.py`)
  raises `MISSING_JUSTIFICANTE_VERIFICATION` unless upstream evidence carries an
  official `source_kind`. `_OFFICIAL_SOURCE_KINDS` already contains
  `aeat_sede_live_capture`. A live-captured PDF persisted under that kind both
  feeds reconcile and clears the dependent-period filing gate — a
  hand-downloaded, transiently-parsed PDF does neither.

## Constraints

- **The local-only reconcile invariant is load-bearing and must survive.**
  `modelo_reconcile` documents that it "never contacts AEAT and never invokes
  `require_live_read`". The new live capability MUST live in a separate
  live-gated service; `modelo_reconcile` is consumed unchanged against the
  persisted artefact.
- **The justificante parser is path-only.** `parse_justificante` accepts a
  `pathlib.Path` and reads through `extract_text(path, backend)`, and it redacts
  caller-controlled filesystem paths out of its error messages. Reconciling
  persisted bytes therefore requires either (a) materialising the secure-object
  bytes to a transient readable file for the existing path-only parser, or (b)
  adding a bytes-accepting parse entry point. This ADR selects (a) for the first
  increment — a transient, redaction-safe temp materialisation owned by the live
  service — to avoid widening the inbound parser surface; (b) is a viable later
  refactor and is non-blocking.
- **Read-only safety envelope.** Every sede record carries `mode:
  Literal["read"]`; the capture follows the established named read-capability
  pattern (cf. `aeat-csv-verifier-read`) and performs no submit/mutate, so it
  does not touch the `aeat-safety-legal-gates` prohibition. It rides the existing
  `AEAT_LIVE_TESTS_ENABLED` opt-in via `require_live_read`.
- **Parent-feature stability.** This ADR depends only on already-shipped,
  exercised surfaces: `capture_justificante` + `SedeCapture` (the aeat-verify
  feature), the `_snapshot_base` lifecycle, the `SecureObjectRepository`
  persistence layer, and `_OFFICIAL_SOURCE_KINDS`. No frontier or
  outside-training-cutoff technology is involved. The only genuinely new logic is
  expediente-resolution-from-work-unit and the justificante snapshot payload
  model.
- **Expediente resolution caveat.** `find_expediente(session, modelo, ejercicio)`
  returns the first expediente matching `(modelo, ejercicio)` — it does not
  disambiguate by period. For multi-period modelos (quarterly 1T–4T) the resolver
  MUST narrow further (by period / presentation date) or surface an operator
  disambiguation rather than silently reconciling against the wrong quarter's
  receipt. This is the primary design risk the plan must address.

## Implementation

A new live snapshot service `JustificanteCaptureService` is added under
`application/live/` as a stateful `SnapshotService` sibling of `Borrador100`,
keyed on the `(modelo, filing_year, period)` axis so a re-filed period's fresh
capture supersedes the prior ACTIVE one through the shared lifecycle machinery. A
strict `PersistedJustificanteCapture` payload model carries the bucket id, the
content-addressed `snapshot_id` (derived from `pdf_sha256`), the expediente and
CSV reference, the captured `pdf_bytes`, the lifecycle state, and the official
`source_kind` `aeat_sede_live_capture`. Persistence reuses the
`SecureSnapshotRepository` so the payload is stored as an encrypted, classified
`Envelope` in the active bucket — no new persistence machinery.

The capture flow: `require_live_read()` gates entry; the work unit resolves to an
`(modelo, filing_year, period)` triple; the period-bearing declarations register
is cross-referenced against the procedure tree by `expediente_id`
(`resolve_period_expediente`) to locate the period-correct expediente;
`capture_justificante` downloads the `SedeCapture`; the service builds and
persists the snapshot, deduplicating on `pdf_sha256` so a repeat capture of the
same receipt is idempotent. In the same flow the service then stamps the official
evidence onto the filing record (best-effort: a no-op when the period has no
current in-app filing record, so a capture of a not-yet-recorded period still
succeeds and persists the snapshot). The stamp parses the captured PDF into a
domain `Justificante`, registers it keyed by the capture's CSV (the gate's
evidence `reference_id`), updates the filing record to carry `AEAT_LIVE_CAPTURE`
external evidence plus `aeat_accepted`, and emits a `MODELO_LIVE_EVIDENCE_STAMPED`
bucket event. Because `aeat_live_capture` is a justificante-verified evidence
kind, the stamped receipt satisfies the cross-period
`MISSING_JUSTIFICANTE_VERIFICATION` gate.

A new CLI verb in the live family — `aeat app live justificante
{capture,list,view}` — mirrors `_app_live_expedientes_cli.py`: `capture` takes
the work-unit selectors, calls the service, and renders a typed envelope.
Reconciliation is the second step on the existing local surface: the local
`aeat app modelo reconcile` verb gains a `--from-capture <snapshot-id>` source
that resolves the persisted capture and runs the unchanged local
`modelo_reconcile` against it (the live service materialises the stored
`pdf_bytes` to a transient readable path for the path-only `parse_justificante`).
`--from-capture` is local-only — it reads the already-persisted artefact and never
contacts AEAT — so it is distinct from the rejected `--from-sede` flag (which
would trigger a live pull from `reconcile`); the capture and reconcile services
stay separate so the local-only boundary holds. CSV authenticity via the existing
`verify_csv` surface is recorded as a deferred increment that can stamp an
authenticity result onto the captured snapshot. That increment has since
landed: the stamp lives in `application/live/justificante.py`, alongside the
capture it annotates. The `application/live/_verify.py` path named here never
existed under that name; the module is `application/live/verify.py`, and it is
scoped to NIF-IVA and TGVI, so it was not a safe home for this.

## Rationale

The persist-then-reconcile shape is the only candidate that keeps the deliberate
local-only reconcile boundary intact, converts the orphaned `capture_justificante`
into a durable official-evidence artefact that simultaneously closes the
cross-period evidence gap, and reuses three proven patterns
(`_snapshot_base`/`SecureSnapshotRepository`, `_app_live_*_cli.py`,
`import_external_filing_evidence`) rather than inventing new machinery — as the
research concluded. Siting the work in `application/live/` inherits the
read-only-by-construction guarantees and the `require_live_read` gate the whole
package already enforces, which is why the decision is low-risk despite touching
a live AEAT surface.

## Consequences

- **Gains.** Operators stop hand-downloading receipts to reconcile; the captured
  authentic PDF becomes durable, content-addressed, official evidence that also
  unblocks dependent-period filing; the long-documented but missing
  `SedeCapture`-to-reconciler wiring is finally honoured.
- **Difficulties.** The expediente-resolution-by-period gap is real work, not a
  given — naive `find_expediente` would reconcile a quarterly work unit against
  the wrong quarter. Persisting `pdf_bytes` adds storage and a lifecycle
  (supersession/discard) to manage. Materialising bytes to a transient path for
  the path-only parser is a deliberate seam that must preserve the parser's
  path-redaction privacy behaviour.
- **Pathways opened.** A typed live-capture snapshot for justificantes invites
  the deferred CSV-authenticity stamp (Option C), a capture→reconcile convenience
  chain, and eventually a deeper per-casilla reconcile once the modelo-specific
  declaration parser ships (orthogonal, not blocked here).
- **Pitfalls.** Do not let the reconcile service acquire a live branch; do not
  stamp the capture as official under a non-`_OFFICIAL_SOURCE_KINDS` value (it
  would silently fail to clear the gate) nor invent a new official kind without
  adding it to that frozenset; do not bypass `require_live_read`.

## Codification candidates

- **Rule slug:** `live-captures-persist-before-consuming`.
  **Rule:** A live read-only AEAT capture whose artefact feeds a local-only
  consumer (reconcile, calculate, verify) MUST persist the artefact as a
  bucket-scoped encrypted secure object under an official `source_kind` first and
  let the local consumer read the persisted artefact — never give the local
  consumer a live branch.

  *(Candidate only; promote via the codify phase after the review surfaces it as
  a durable cross-session constraint. The existing `application/live/` package
  already embodies this implicitly; this feature is the first to wire a live
  capture into a previously local-only consumer, which is what makes the
  constraint worth stating explicitly.)*
