---
tags:
  - '#plan'
  - '#file-size-optimisation'
date: '2026-09-29'
tier: L1
related:
  - '[[2026-09-29-file-size-optimisation-sequence-golden-storage-adr]]'
modified: '2026-09-29'
body_schema: body-v2
body_hash: 'sha256:aba9268fcb28623ca7f129b5d9b057abec094e97d0e7eaa341cfa77a841dc4ff'
---

# `file-size-optimisation` plan

Replace the committed sequence golden bodies with per-frame fingerprints and render docs from verified, regenerated transcripts.

## Description

Approved 2026-09-29. Basis: the operator reviewed the measured options and directed "execute option 1", which is the decision recorded in `2026-09-29-file-size-optimisation-sequence-golden-storage-adr`.

The committed `docs/_sequences/**/*.json` goldens change from full recorded output to a fingerprint per frame: kind, argv, exit code, captures, envelope source, and the SHA-256 and byte size of the form the check compares. The full transcript becomes a record in the gitignored development cache. It is written by refresh and by a clean check, and it is rendered only when its fingerprint equals the committed golden. The governing decision is the ADR above; the evidence is `2026-09-29-file-size-optimisation-research`. D1, D4 to D7 and the output weight amendment of `2026-07-13-docs-cli-sequences-adr` stay as they are. No other costly decision is involved.

## Steps

- [ ] `S01` - Store each golden as a per-frame fingerprint (schema 3) and keep the full transcript as a gitignored record verified against it; compare, check and refresh work on records; `dev/docs/sequences/golden_store.py, record_store.py, compare.py, checks.py, cli.py, tests/`.
- [ ] `S02` - Render cli-sequence directives only from verified records, and make the build gate, verdict cache and deploy produce or require them; `dev/docs/sequence_directive.py, sequence_build_gate.py, sequences/verdict_cache.py, dev/deploy/docs_static_site.py, dev/docs/tests/`.
- [ ] `S03` - Regenerate all goldens through the refresh CLI and pass the sequence check and the owning tests; `docs/_sequences/`.
- [ ] `S04` - Record the golden storage amendment on the governing docs sequences decision and link it; `.vault/adr/2026-07-13-docs-cli-sequences-adr.md`.

## Parallelization

None. S01 and S02 share the engine's types and rewrite one coupled surface, so one writer takes them in order. S03 rewrites every golden and runs after both. S04 follows S03, so the amendment records the shipped behaviour.

## Verification

- The owning tests in `dev/docs/sequences/tests/` and `dev/docs/tests/` pass. They include a detector case in which a changed output with an unchanged argv and exit code fails the check. They also include refusal of a schema-2 golden and refusal to render a record whose fingerprint disagrees with the golden.
- `python -m dev.docs.sequences check` passes on the regenerated goldens.
- No committed golden stores an envelope, text or stderr body. The committed tree shrinks from 12.0 MB and is measured after regeneration.
- A docs build renders the sequence pages from records, and a build with no records present regenerates them before rendering.
