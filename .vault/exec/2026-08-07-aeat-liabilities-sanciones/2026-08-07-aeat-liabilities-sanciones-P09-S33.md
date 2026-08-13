---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6ee4700cc2b55adcbf4f3933cc9857d82cd105dc23b7fb2753de1d5c57e32af0'
step_id: 'S33'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Establish whether the AEAT text layer emits the UNE 82100 NBSP or narrow-NBSP thousands separator and admit them in the anchored house pattern. RESOLVED on the empirical finding the tree already carried at adapters/inbound/pdf/_label_regex.py, which records NBSP and narrow-NBSP grouping as observed AEAT rendering and ASCII space as never emitted. Both forms were refused by the sancion reader, so a genuine AEAT document would have been refused outright. The separator taxonomy now has one source consumed by all three grammars, ASCII space stays refused, and _strip_leaders no longer destroys the separator ahead of the check. Verified by a regression pinning the accepted and refused separator forms with a mutation proof, landed in the tree's existing tests/test_sancion_parser.py rather than the row's originally-named test_sancion_parse.py, which would have been a near-duplicate file

## Scope

- `src/cadrumo/adapters/inbound/notificacion/tests/test_sancion_parser.py`

## Description

- Admit the non-breaking and narrow non-breaking thousands separators in the canonical anchored grammar, keeping ASCII space refused.
- Stop the leader-stripping helper from rewriting the separator to a space ahead of the check.
- Remove the equivalent fold in the wallet reader so the two code points cannot diverge.
- Pin the accepted and refused separator forms with mutation proofs.

## Outcome

Delivered, and resolved without a live capture.

The row asked for the separator question to be settled empirically against real documents. No sancion specimen can be obtained without an operator-authorised live capture, and fetching one is gated on the taxpayer having personally opened the notification. The tree already carried the empirical finding: the printed-amount authority records non-breaking and narrow non-breaking grouping as observed AEAT rendering per UNE 82100, and ASCII space as never emitted. The sancion reader refused both forms, so a genuine AEAT document would have been refused outright - a safe failure direction, but a functional gap, and the reader diverged from the tolerant house parser on the same input.

The widening touches only the separator class. The mandatory two-decimal comma tail is untouched, so the defect the anchored check was originally added to close - a template dropping decimals being reinterpreted as a grouped integer - stays closed. That was verified against the wallet function directly, not assumed.

One subtlety the pattern edit alone would not have fixed: the leader-stripping helper rewrote the non-breaking space to an ASCII space before the anchored check ever ran, so the widened pattern would still have refused. The fold had to go with it.

## Notes

The widening was reported as reaching the wallet reader's row cells. It did not. Those cells pass through a marker-matching normaliser that collapses all whitespace, and the whitespace class matches both non-breaking code points, so every separator was already an ASCII space before the anchored check ran. The widening was dead code on that surface until a follow-up gave the money cells a value-preserving extraction. The fold removed by this Step was real but unreachable.

The regression landed in the tree's existing parser test file rather than the near-duplicate filename the row named.
