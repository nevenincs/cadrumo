---
tags:
  - '#adr'
  - '#sync-control-surface'
date: '2026-08-08'
modified: '2026-10-29'
body_schema: 'body-v1'
body_hash: 'sha256:98fa82a3474c359ed73b3ff5a648093e64fbcf4c3f05a2b19e885666b6abdfd4'
related:
  - '[[2026-08-08-sync-control-surface-reference]]'
  - '[[2026-07-25-censal-profile-autofill-adr]]'
---

# `sync-control-surface` adr: `Dry-run is a flag on both sync surfaces, and its payload differs by write shape` | (**status:** `accepted`)

## Problem Statement

Two surfaces in this application synchronise with a system outside it, and
neither offers the operator any control over the sweep. The Google Sheets
calculation export writes a modelo workbook to Drive; the filed-history sweep
pulls previously filed declaraciones from AEAT into the local observation store.
For neither surface, at CLI or TUI, is there scope selection beyond a coarse
key, a preview of what the run would do, a report of what it changed, progress
while it runs, or a way to stop it. Nothing anywhere in the tree records that a
sync ran at all.

Both write destructively. The Sheets adapter clears every managed tab range and
then rewrites it. The filed sweep is an unconditional upsert that can replace a
previously captured casilla value. Each already computes, somewhere, the
information a preview would need — and each computes it too late to help.

## Considerations

- The Sheets apply path is a whole-surface batch clear followed by a batch
  update. It is idempotent at the spreadsheet level — re-applying the same plan
  updates the same spreadsheet rather than creating a duplicate — but it is
  destructive at the cell level, and foreign content is refused rather than
  merged.
- The filed sweep is **not** append-only, contrary to the framing this decision
  was commissioned under. The capture path documents a re-capture as an
  unconditional upsert keyed on modelo, ejercicio, period and expediente. This
  matters: the difference between the two surfaces is not append-versus-overwrite,
  it is *what the overwrite can destroy*.
- The filed sweep already computes the divergence a re-capture would introduce,
  and already surfaces it as a warning `Notice`. It computes it AFTER the upsert
  has landed. The operator is told what changed, never what would change.
- The Sheets `verify` verb computes a three-way local/Sheets/AEAT parity report
  with typed divergence rows. That machinery is not attached to `export`.
- The censo cotejo is the mature in-tree precedent: preview by default, commit
  behind `--apply`, unadopted values persisted as typed divergence rows in a
  replaced namespace, a standing warning while any divergence is open, and one
  lifecycle event per apply-commit.
- Prior rulings already establish the vocabulary. The
  `inventory-management-cli-design` record requires preview/apply semantics on
  mutating commands whose overwrite effects need review; the
  `cli-workflow-redesign-list-vs-query-leaf-semantics` record permits a sibling
  preview leaf where a flag does not fit. A `--dry-run` flag on a mutating verb
  is the established spelling across the ledger, borrador and config-repair
  surfaces.
- Nothing in the tree records a last-sync mark for any surface. What exists is
  per-record ingest stamps — a captured-at per observation, an exported-at per
  export record — and, for Sheets, an exported-at developer-metadata key written
  into the remote spreadsheet and then deliberately excluded from the staleness
  comparison.
- Google Sheets is a one-way export mirror and never an authority. Nothing read
  back from it may become a fact.

## Considered options

- **Adopt the cotejo shape wholesale: preview by default, `--apply` to commit,
  on both surfaces.** Rejected. The cotejo defaults to preview because it
  reconciles two competing authorities over the same facts — AEAT's certificate
  against the operator's own answers — and a silent adoption would overwrite a
  human's declaration. Neither sync surface has that property: the spreadsheet
  is a mirror the application exclusively owns, and the observation store is a
  cache of AEAT's own record. Defaulting an `export` verb to doing nothing makes
  the flag ceremonial, and a ceremonial flag trains operators to type `--apply`
  without reading, which erodes the guard where it is real.
- **A sibling `preview` leaf on each surface.** Rejected for these two. The
  sibling-leaf shape fits where the preview answers a different question from
  the mutation; here it answers exactly the same question with the write
  suppressed, and two verbs would drift.
- **Dry-run with one uniform payload across both surfaces.** Rejected. A uniform
  payload would have to be the intersection of a cell-level spreadsheet diff and
  a record-level observation diff, which is nothing useful. Declaring one shape
  for both would make the weaker surface's preview a decoration.
- **`--dry-run` on both, with a payload declared per surface.** Chosen.

## Constraints

- Sheets preview describes a new immutable publication from one local snapshot,
  including destination, included records, exclusions and findings. It does not
  read existing review cells or notes. Destination admission is a separate
  scoped metadata check; an offline inventory cannot claim live admission.
- Progress reporting has no channel. The CLI contract is a single terminal JSON
  envelope with a notices list; there is no streaming surface, and inventing one
  is a decision about the envelope itself rather than about sync.
- The Sheets clear and update are two separate API calls with no transaction
  spanning them.

## Implementation

**Dry-run is a `--dry-run` flag on the mutating verb of each surface, defaulting
to false.** The run executes normally up to the point of the outbound write,
emits the same envelope it would have emitted, and returns without writing. The
envelope carries the dry-run state as primary result data, never as a notice, so
a caller cannot mistake a preview for a commit.

**The payload differs by write shape, and the difference is declared, not
incidental.**

For Sheets, the authorized 2026-10-05 outbound-review amendment replaces the
overwrite contract with new-version publication. Preview describes the selected
revision, baseline, ledger/evidence inventory, missing data and target root.
Re-export creates a new document and preserves existing user work. Public
verify is retired; bounded developer acceptance does not supply a general
remote-cell diff route.

For the filed sweep — an unconditional upsert over records the operator may
already have calculated against — the preview answers *which previously captured
values would change*: exactly the casilla set the post-hoc recapture divergence
already computes, moved in front of the write instead of behind it.

**Scope selection follows the payload.** Each surface's dry-run enumerates the
units it would touch, and the mutating verb accepts a scope narrowing over that
same enumeration, so the preview and the commit cannot describe different
worlds. The filed sweep's existing `discover` leaf is that enumeration and is
kept. A result limit is not a scope, it is a truncation, and a truncated sweep
must say so in a notice rather than reading as complete coverage.

**Last-sync provenance is a local typed record, not a remote stamp.** Each sync
surface persists, on completion, a typed sync-run record in the encrypted
profile bucket carrying the surface, the resolved scope, the completion instant,
the unit counts and the divergence count. It is written on both success and
partial failure, because "the sweep ran and half of it failed" is the state an
operator most needs to see. The remote developer-metadata exported-at key is
explicitly NOT this record: it lives in an artefact the application does not
own, it is already excluded from the staleness comparison, and a mirror cannot
be the provenance authority for the thing that writes it.

**Cancellation is ruled as interruption-safety, not as a cancel control.** Each
sweep must leave a consistent store when interrupted. The filed sweep already
satisfies this — each observation is its own atomic upsert. The historical Sheets clear/update path does not. Its replacement records
partial/uncertain publication and reconciles only that in-flight publication,
without clearing or rewriting an earlier published review copy.

## Rationale

The knockout against the cotejo shape is that preview-by-default guards against
overwriting *a human's own declaration*, and neither sync surface can do that.
Copying the shape because it is the mature precedent would import its ceremony
without its reason, and a flag operators learn to pass unread is worse than no
flag, because it looks like a control in every audit.

The knockout for a per-surface payload is that both surfaces already compute the
right diff and both compute it at the wrong time. The Sheets parity report is
attached to the wrong verb; the filed sweep's divergence set is computed after
the write it should have gated. Neither needs a new differ — they need the
existing one moved. Declaring one shared payload would have thrown that away to
buy a symmetry the surfaces do not have.

The last-sync ruling is the one place this record adds a genuinely new
structure, and it does so because the alternative already in the tree is a stamp
written into a Google spreadsheet. A mirror the operator can edit, and that the
application refuses to read as authority, cannot also be where the application
remembers what it did.

## Consequences

- An operator gains the ability to see what a sweep would destroy before it
  destroys it, on both surfaces, through one flag spelled the same way.
- The filed sweep's dry run returns before persistence, and its recapture
  divergence is computed in front of the write
  (`src/cadrumo/application/live/filed_capture_accumulator.py:155`). The filed
  sweep writes the typed sync-run record `SyncRunRecord`
  (`src/cadrumo/application/storage/sync_runs/records.py:173`) on success and
  on partial failure (`src/cadrumo/application/live/filed_data_capture.py:705`),
  and the Sheets export records its own run on success and failure
  (`src/cadrumo/application/storage/calc_sheets/export_service.py:124`).
- **The Sheets torn-write window is a live defect, not a future concern.** An
  interruption between the clear and the update empties the operator's workbook
  today. It is named here because this record's cancellation ruling depends on
  it, but it is independently worth fixing and should not wait for the rest.
- The premise that the filed sweep is append-only is incorrect and is corrected
  here. Any earlier reasoning that relied on it — including the framing this
  decision was commissioned under — should be re-read against the upsert.
- CLI progress reporting is deliberately unruled. It needs a decision about
  whether the CLI envelope grows a streaming channel, which is a contract-level
  question this record has no standing to answer. Desktop progress is ruled by
  the 2026-10-29 amendment below.

## Amendment 2026-10-05 - outbound review

The product owner's Session 01 instruction authorizes the scoped wording changes above, governed by 2026-10-05-google-outbound-review-adr. Earlier descriptions of then-current behavior remain historical evidence, not permission to retain retired routes. Other commitments remain in force. This amendment records architecture, not completed implementation or live acceptance.

## Amendment 2026-10-29 - the desktop AEAT sync page

Accepted by the owner on 2026-10-29 with `2026-10-29-desktop-aeat-sync-adr`. The desktop's stop control stops a run between items: the in-flight capture settles and nothing further starts. It interrupts no operation, so the interruption-safety ruling stands. Progress for the desktop is item-level, refined by the operation's own observation events where it emits them; the CLI envelope is unchanged. Last-sync provenance for every AEAT area is served by `live.sync.status`: the filed sweep's typed sync-run record where one exists, otherwise the latest stored capture's own instant. Dry run on the filed sweep remains the only AEAT dry run; it reads AEAT and saves nothing.
