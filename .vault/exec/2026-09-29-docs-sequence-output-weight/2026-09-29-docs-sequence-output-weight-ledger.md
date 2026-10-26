---
tags:
  - '#exec'
  - '#docs-sequence-output-weight'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:542bc88588e8b8237f57846c1e1f8f4fbeb1b281504741250eb2c7f728272a82'
related:
  - "[[2026-09-29-docs-sequence-output-weight-plan]]"
---

# `docs-sequence-output-weight` ledger

## Changes

- `S01` `M` `dev/docs/sequences/golden_store.py`
- `S01` `M` `dev/docs/sequences/compare.py`
- `S01` `M` `dev/docs/sequences/checks.py`
- `S01` `M` `dev/docs/sequences/cli.py`
- `S01` `M` `dev/docs/sequences/tests/test_golden_frame_stream_coherence.py`
- `S01` `A` `dev/docs/sequences/tests/test_setup_frame_goldens.py`
- `S01` `A` `dev/docs/sequences/tests/test_reader_frame_output_advisory.py`
- `S01` `M` `dev/docs/tests/test_docs_build.py`
- `S01` `verify:` `pytest dev/docs/sequences/tests -m '' (255 passed)` -> `pass`
- `S01` `by:` `opus-high`
- `S02` `M` `dev/docs/sequence_directive.py`
- `S02` `M` `dev/docs/tests/test_sequence_directive.py`
- `S02` `verify:` `pytest test_sequence_directive.py test_docs_build.py -m '' (46 passed)` -> `pass`
- `S02` `by:` `opus-medium`
- `S03` `M` `docs/_sequences/contracts/explanation/how-renta-is-assembled/renta-assembly-provenance.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/file-at-aeat/file-at-aeat-chain.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-calendar/filing-calendar-agenda.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-calendar/filing-calendar-backlog.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-calendar/filing-calendar-calendar.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-calendar/filing-calendar-catalogue.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-readiness/filing-readiness-dependencies.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-address-by-id.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-chain.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-exact-ids.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-other-target.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-visible-target.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-work-list.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/irpf-lifecycle/irpf-lifecycle-agenda.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/irpf-lifecycle/irpf-lifecycle-position.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/irpf-lifecycle/irpf-lifecycle-q1.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/irpf-lifecycle/irpf-lifecycle-q2.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/iva-lifecycle/iva-lifecycle-q1.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/iva-lifecycle/iva-lifecycle-wallet.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-100/modelo-100-dependencies.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-100/modelo-100-inspect-inputs.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-first-quarter.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-inspect-boxes.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-ledger-period.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-revision.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-wallet.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-349/modelo-349-inspect.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/modelo-390/modelo-390-inspect.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/quickstart/quickstart-agenda.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/quickstart/quickstart-classify.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/quickstart/quickstart-transactions.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/review-calculation-values/review-values-bindings.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/review-calculation-values/review-values-inspect.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/review-calculation-values/review-values-iva-wallet.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/review-calculation-values/review-values-review-saved.seq`
- `S03` `M` `docs/_sequences/contracts/how-to/troubleshooting/troubleshooting-period-grammar.seq`
- `S03` `verify:` `dev.docs.sequences check --coherence on 15 pages` -> `pass`
- `S03` `by:` `opus-medium`
- `S04` `M` `docs/_sequences/**/*.json (205 goldens)`
- `S04` `M` `dev/docs/tests/test_golden_records_no_crash.py`
- `S04` `verify:` `python -m dev.docs.sequences check` -> `pass`
- `S04` `verify:` `pytest dev/docs/tests (7 modules) + dev/docs/sequences/tests -m '' (355 passed)` -> `pass`

## Notes

- `S04` profile-setup-delete fingerprint.digest re-recorded: declared nondeterministic GOLDEN_MASK_PATHS field
