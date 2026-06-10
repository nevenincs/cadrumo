---
tags:
  - '#research'
  - '#live-justificante-reconcile'
date: '2026-06-10'
related:
  - '[[2026-04-25-aeat-verify-adr]]'
  - '[[2026-04-25-aeat-verify-research]]'
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace live-justificante-reconcile with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `live-justificante-reconcile` research: `live-sourced justificante reconciliation`

The operator-facing modelo reconciliation surface only accepts a justificante PDF
that the operator has already downloaded by hand and points at with a filesystem
path. Yet the application can authenticate to the AEAT sede electrónica read-only
and already contains an end-to-end routine that pulls the authentic, AEAT-signed
justificante PDF programmatically. The two halves are not connected: the live
pull is orphaned from the reconcile pipeline. This research characterises the gap,
the constraints that shaped the current split, and the candidate ways to bridge it,
so an ADR can choose a direction.

## Findings

### 1. Two disconnected tracks

**Reconcile is deliberately local-only.** The reconcile application service
`modelo_reconcile` in `src/aeat/application/modelo/_reconcile.py` takes a
`ModeloReconciliationCommand` whose `source_path` is a `pathlib.Path`. Its
docstring states the invariant explicitly: it "never contacts AEAT and never
invokes `require_live_read`." It calls `parse_justificante(command.source_path)`
from `src/aeat/adapters/inbound/justificante/_parser.py`, diffs the parsed
record's `modelo` and `ejercicio` against the work unit, and emits a
`MODELO_RECONCILED` bucket event. The CLI verbs `reconcile` and
`reconcile-from-justificante` in
`src/aeat/entrypoints/cli/_modelo_reconcile_cli.py` only expose
`--from-justificante PATH` / `--from-declaration PATH`, and their help text
repeats "Local-only; never contacts AEAT."

**The live pull exists and is complete.** `capture_justificante` in
`src/aeat/adapters/outbound/aeat/sede/_walker.py` performs the full read-only
chain: authenticated session, navigate the Mis Expedientes procedure tree,
resolve the per-filing CSV handle, GET the raw PDF body, and return a
`SedeCapture`. `SedeCapture` in `src/aeat/adapters/outbound/aeat/sede/_schema.py`
carries `expediente`, the CSV `ref`, the raw `pdf_bytes`, and `pdf_sha256`. Every
sede record carries `mode: Literal["read"]`.

### 2. The orphan, and a docstring that documents the intended-but-missing wiring

`SedeCapture`'s own docstring declares it is "Produced by `capture_justificante`;
consumed by the reconciler." But no reconciler consumes it. A repository-wide
search for `SedeCapture` and `capture_justificante` finds references only inside
the `sede` adapter package itself and in `.vault/` documents — there is **no**
consumer in `src/aeat/application/` or `src/aeat/entrypoints/`. The design intent
was recorded; the bridge was never built. From the operator's seat this reads as
a regression: the app can fetch the receipt but forces a manual download anyway.

What *is* wired from the live sede surface, for contrast: `walk_expedientes_tree`
feeds the workflow engine's "already-filed probe" (it only *lists* expedientes,
never captures the PDF), and `walk_declarations_register` /
`capture_filed_declaration_observation` feed casilla *observations* into the
calculate / previous-filing path — a different consumer than reconcile.

### 3. Constraints that shaped the split (and that any bridge must respect)

- **The parser is path-only.** `parse_justificante` accepts a `Path` and reads
  bytes through `extract_text(resolved_pdf_path, backend)`. Feeding the live
  `pdf_bytes` requires either materialising them to a file first or adding a
  bytes-accepting parse entry point. The parser also redacts caller-controlled
  filesystem paths out of its error messages — a privacy behaviour a bytes path
  must preserve.
- **Reconcile must not silently become a live caller.** The local-only invariant
  is intentional and load-bearing: live reads go through `require_live_read` and
  the `AEAT_LIVE_TESTS_ENABLED` opt-in gate. Coupling the existing local service
  to live auth would erode that boundary. A live capability belongs in a distinct
  surface that owns the live gate.
- **Read-only safety envelope already exists.** The sibling `verify` adapter
  (`src/aeat/adapters/outbound/aeat/verify/__init__.py`, `verify_csv`) shows the
  established pattern: a named read capability (`aeat-csv-verifier-read`) with
  allow-listed browser action patterns, opt-in only. A live justificante capture
  rides the same read-only, no-write envelope and does **not** touch
  `aeat-safety-legal-gates` (no submit/mutate).
- **Official-evidence gate is the natural beneficiary.** The cross-period
  clean-state gate in
  `src/aeat/application/calculations/_cross_period_clean_state.py` raises
  `MISSING_JUSTIFICANTE_VERIFICATION` unless an upstream observation carries an
  official `source_kind`. `_OFFICIAL_SOURCE_KINDS` already enumerates
  `aeat_sede_justificante`, `aeat_sede_live_capture`, and `aeat_csv_register`. A
  live-captured PDF persisted under one of those kinds would satisfy the gate that
  a hand-downloaded PDF (parsed transiently, never persisted) does not. The
  companion rule on non-official local evidence (the `app_filing` carve-out)
  confirms the official/non-official distinction is safety-critical.
- **An existing persistence pattern to mirror.** `import_external_filing_evidence`
  in `src/aeat/application/modelo/_external_import_actions.py` already persists an
  externally-filed return with an `ExternalEvidence(kind=..., reference_id=...)`
  stamp (`ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF`) and supersedes the prior
  filing. A live-capture bridge can follow this shape rather than inventing a new
  persistence path.

### 4. Diff coverage is shallow today (orthogonal, but bounds the value)

`modelo_reconcile` only diffs `modelo` and `ejercicio` because the justificante
PDF exposes only header totals, not per-casilla values; full per-casilla diffs
need the modelo-specific declaration parser that has not shipped (the
`--from-declaration` path raises `ReconciliationDeclaracionSourceUnsupportedError`
today). Live-sourcing the justificante does not deepen the diff — it removes the
manual download step and produces a persistable official artefact. The two
concerns are independent; this feature should not block on the declaration parser.

### 5. Candidate directions

- **Option A — persist-then-reconcile (capture writes an official evidence
  artefact, reconcile runs unchanged).** A new live application service +
  `aeat`-scoped CLI verb authenticates (owning `require_live_read`), resolves the
  expediente for a work unit, calls `capture_justificante`, persists `pdf_bytes`
  into the bucket as `ExternalEvidence` under an official `source_kind`
  (`aeat_sede_live_capture`), then the existing local `modelo_reconcile` runs
  against the persisted artefact. *Pros:* preserves the local-only reconcile
  invariant verbatim; produces a durable artefact that also clears
  `MISSING_JUSTIFICANTE_VERIFICATION`; reuses `import_external_filing_evidence`'s
  pattern; the live gate lives only in the new service. *Cons:* writes a PDF into
  the bucket (storage + lifecycle), needs an expediente-resolution step keyed from
  the work unit (modelo + period + ejercicio).
- **Option B — stream-bytes into reconcile (new `LIVE_SEDE` source kind).** Add a
  source kind to `modelo_reconcile` that triggers `require_live_read`, captures,
  and feeds bytes to a bytes-accepting parser, persisting nothing. *Pros:* minimal
  surface; one verb. *Cons:* breaks the documented local-only invariant; couples
  the local service to live auth; leaves the official-evidence gate unsatisfied
  (nothing persisted); the captured authentic PDF is discarded after the diff.
- **Option C — CSV verification only (use the `verify` adapter).** Verify the
  justificante's CSV against the sede verifier without pulling the PDF. *Pros:*
  lightest live touch. *Cons:* proves the receipt is authentic but yields no
  parsed values to reconcile against the work unit; complementary to, not a
  substitute for, A.

### 6. Preliminary recommendation

Option A. It is the only candidate that (a) keeps the deliberate local-only
reconcile boundary intact, (b) turns the orphaned `capture_justificante` into a
durable official-evidence artefact that simultaneously closes the cross-period
`MISSING_JUSTIFICANTE_VERIFICATION` gap, and (c) reuses the existing
external-evidence persistence and read-only live-safety patterns rather than
inventing new ones. The expediente-resolution-from-work-unit step is the main new
logic to design. Option C is a worthwhile follow-on (CSV authenticity proof
stamped onto the captured artefact); Option B is not recommended.

### 7. Open questions for the ADR

- **Expediente resolution.** How does the bridge map a work unit (modelo, period,
  ejercicio, tax id) to the right expediente in the Mis Expedientes tree? Is
  `find_expediente` / `walk_expedientes_tree` filtering sufficient, or is operator
  disambiguation needed when multiple filings match?
- **Persistence shape.** Where do the captured `pdf_bytes` live — a secure-object
  in the bucket alongside `ExternalEvidence`, keyed by `pdf_sha256`? Does this
  reuse `import_external_filing_evidence` or sit beside it?
- **Source-kind choice.** `aeat_sede_live_capture` vs `aeat_sede_justificante`
  for the persisted observation's `source_kind` — both are official; which
  semantics fit a capture-for-reconcile vs a capture-for-prefill?
- **CLI placement.** A new verb under the live/`aeat` command family (it contacts
  AEAT) vs an opt-in flag on `reconcile` that delegates to the live service while
  the service itself stays the live-gated owner.
- **Idempotency.** Re-capturing the same expediente should not duplicate evidence;
  `pdf_sha256` is the natural content address for dedupe.
- **CSV authenticity (Option C fold-in).** Should the captured artefact also carry
  a `verify_csv` authenticity result, or is that a later increment?
