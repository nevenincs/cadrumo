---
tags:
  - '#research'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:afd5868515f6ef615a979d278728e0a2b708513f859b85fbc228e03fc360b916'
related: []
---

# `registry-generator` research: corpus provenance

## Why this document exists

The AEAT registry is the authority every filing calculation reads. It is supposed to be a
generated artefact: an official record design goes in, a reproducible declaration comes out. This
document establishes what the shipped registry actually is today, measured rather than assumed,
so that decisions about the generator rest on the real shape of the corpus.

The short version: **the corpus is two corpora wearing one name.** One is genuinely generated and
better attested than most projects manage. The other is a careful human transcription that cites
official sources but records no derivation from them. They are roughly the same size.

## The two surfaces

| | `revisions/*/export/` | `revisions/*/export_layouts/` |
|---|---|---|
| revisions | 32 | 62 |
| fields | 15,568 | 9,962 |
| generator | yes | **none** |
| provenance manifest | 32 / 32 | **0 / 62** |
| reproducible from source | yes, verified | no mechanism |

The two are mutually exclusive: no revision carries both, and 34 revisions carry neither. Modelo
322 straddles the boundary — three generated revisions followed by one hand-authored.

## The generated half is real

This needs saying plainly, because the rest of this document is critical and the distinction
matters. For the 32 `export/` revisions the derivation claim is true in the strongest sense
available:

- The official binary is committed under `_data/corpus/aeat_official/disenos_registro/`.
- Every revision pins a `source_ref` and `source_sha256`, and **all 32 digests match the committed
  artefact on disk today** — manifest, source declaration and disk bytes agree three ways.
- The pins are verified in code by `verify_export_fragment_provenance_manifest`, called from three
  sites, and by a reproduction gate parametrised over all 32 trees in the `test-dev-ci` lane.
- Re-rendering all 32 from current inputs gives **19 byte-identical**, **11 differing only in
  serializer spelling and manifest digests with parsed content identical**, and **2 with real
  semantic drift** (both modelo 347, ledgered, where the ledger states the shipped bytes are
  correct and the inputs are wrong).

Nobody should call that surface fake.

## The authored half is a transcription

Four independent lines of evidence establish that `export_layouts/` is hand-typed:

1. **Fingerprints are perfectly binary** against the generated trees as control — comment lines
   0 vs 8,519; identifier quoting 16,250 single / 0 double vs 0 single / 10,533 double;
   `generated-` id prefix on 357 of 357 files vs none. No serializer writes 8,519 lines of
   justification prose, and quote style does not flip 100/0 across a corpus by accident.
2. **The files say so.** One layout header reads: *"Transcribed position by position from the
   bundled AEAT Diseño de Registros… Every offset and length below is read from that file; none is
   derived, inferred or rounded."*
3. **Git shows hand-sized tranches**, never a bulk generator run — one modelo arrived over six-plus
   commits in a single day with prose messages naming each tranche.
4. **The governing decision record states it**, and is accepted: *"existing manual trees remain
   unverified until regenerated and proven"*; *"Generated replacements are a hard cutover:
   superseded manual fragment trees… are deleted."*

These revisions do cite official sources, and **every citation hash-verifies** — 62 of 62. But the
citation means something different on each surface. On the generated side it is backed by a
manifest recording, field by field, which parser row produced the value. On the authored side it
is an assertion with nothing behind it. Nothing compares a hand-authored field's offset, length,
type or sign to the design row it claims to come from.

An attempt to join the authored layouts back to their designs succeeded for only 4 of 62. The
other 58 defeated the method — PDF sidecars use a different row grammar, and multi-record designs
produce ambiguous coordinate keys. That failure is worth recording precisely: **the reviewer could
not verify them, and neither can the repository.**

## The whole registry, not just exports

Export layouts are the visible part of a larger pattern. Across all 128 revisions there are
**19,630 TOML files, of which exactly 357 (1.8%) are generator output.** Every other family —
casillas (14,171 files), formulas, bindings, applicability, deadline windows, parameters,
verification expectations, constructs — is authored. The only writers into the registry are the
export-tree pipeline and a generated `export_refs` overlay on 1,524 casilla files.

## Why the migration stalled at 14 modelos

The cutover is real and executing — one commit added 58 generated files and removed 66 authored
paths. It has not stopped for lack of will. **It stalled because the generator relocates
hand-authoring rather than removing it.**

To generate one tree, a human must first author a semantic map and an exhaustive render profile
bound to the exact source digest. Only 17 modelos have profiles; 173 profile files hold 1,188
rules carrying 575 distinct hand-written decision identifiers. The declared migration backlog is
**one** target.

The cost is concentrated, not eliminated. And it is load-bearing for correctness: **2,277 of the
2,279 correctly-signed fields in the entire corpus (99.9%) trace to one of just 48 hand-written
sign rules.**

## A new regulation lands hand-authored by default

This is the finding with the longest half-life. The scaffold command for a new modelo revision
writes ten placeholder files including `export_layouts` — **`export` is not scaffolded at all** —
and the contributor checklist directs the author to write the fixed-width layout by hand.

Measured burden for a single revision: one modelo required **6,039 fields typed by hand**; another
1,220. The median authored revision is 40–180 fields.

Given that AEAT issues new designs yearly and revises within periods, the default path produces
hand transcription at a rate no review process can absorb.

## The corpus can go stale without anyone noticing

A live drift detector exists: it re-downloads every current official URL and compares bytes and
digests, flagging newly indexed or unindexed documents. It is **maintainer-invoked and wired to
nothing** — no test, no recipe, no workflow.

Every offline gate checks committed bytes against digests derived from those same committed bytes.
So if AEAT republishes a design tomorrow, nothing here notices. **60% of the corpus (147 of 247
artefacts) was retrieved four months ago**, and at least one design is itself stamped
*"actualizado"* with a date after its original publication — AEAT revises in place. This is a live
exposure, not a theoretical one.

## What this means for the feature

1. The generator is not the weak link — **the authoring default is**. A design that makes
   generation the scaffolded path, and hand-authoring the exception requiring justification,
   changes the trajectory more than any single fix.
2. Generation currently **trades one hand-authored surface for another** (profiles and semantic
   maps). That trade is worthwhile only if the authored input is smaller, reviewable, and itself
   checked against the design. Today the sign rules are none of those things at scale.
3. **Citation is not derivation.** The corpus already distinguishes the two in practice; the
   declarations do not distinguish them in form. A revision should be able to state which it has.
4. The staleness gap is cheap to close and currently open.

## Confidence

VERIFIED: all counts and digest checks; the reproduction sweep; the fingerprint comparison; the
scaffold and checklist behaviour; the drift detector's wiring status. Two reviewers independently
corrected first-pass errors during this work — one retracted a claim that six revisions were
sourceless after finding they declare a dictionary and schema pair rather than a record design.

INFERRED: that the 58 unverifiable authored revisions are faithful transcriptions. That was not
confirmed and no mechanism in the repository can confirm it.

## Findings

- The registry ships two export surfaces: 32 generated revisions under `export/`, each carrying a
  provenance manifest, and 62 hand-authored revisions under `export_layouts/` carrying none.
- Provenance is real on all 32 generated revisions; no revision is sourceless.
- 2,279 correctly-signed fields (99.9% of the signed population) trace to a small set of
  hand-written rules rather than to a derivation from the official column.
- The migration to generation stalled at 14 modelos, and a new regulation lands hand-authored by
  default because the scaffolding path produces only the authored surface.
- The captured corpus can go stale against republished official sources with no gate noticing.

## Sources

- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/export/_generation.provenance.json`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/export_layouts/`
- `dev/registry/newmodelo/manager.py`, `dev/registry/newmodelo/checklist.py`
- `dev/corpus/sync_aeat_record_design_corpus.py`
