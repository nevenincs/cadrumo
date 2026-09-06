---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:b970c6bc589b2d00d26dca11ec2b709419473b8ea123d01e4cd37427aaa3ff9c'
step_id: 'S463'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Confirm a column table written inline at the call site by registering it under a synthetic name so the parameter alias and key-column rule apply unchanged, and establish from the live error registry that the five application filing error keys are declared nowhere it owns

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 141 -> 140. Full-literal residue 8 -> 7.

BLIND SPOT 11, and the last of the column-table family. One screen builds its
columns in the ARGUMENT LIST rather than binding them first. Every rule here
registers a candidate under an assignment target, so a table with no name was
invisible -- though it is the same table, handed to the same fitter, doing the
same job as its named siblings two screens away.

It is admitted on exactly the terms a named table is: registered under a
synthetic name so the parameter alias from S460 and the key-column rule both
apply unchanged, and confirmed only when that parameter's rows reach a
translator. The synthetic name is not a valid identifier, so it cannot collide
with a real target.

Teeth: two defects, each restored by copy -- stop registering inline tables,
and return shape candidates as though confirmed. The second is what proves
anonymity buys no shortcut past confirmation, and the gate carries the matching
negative: an inline table handed to a helper that only measures widths stays
out.

## Notes

TARGET 2 REMAINS OPEN at 140 extras: 125 `cli.*`, 10 `tui.*`, 5 `application.*`.
Same two failures as before this step. No new breakage.

THE FIVE `application.filing.errors.*` EXTRAS ARE ADJUDICATED, not fixed. The
live error registry declares 559 message keys across 645 codes, and none of
them is one of these five; no literal for them exists in the tree either. The
registry is fully covered in both directions -- every one of its 559 keys is
visible to the scanner and present in every catalogue -- so the authority that
owns this namespace is in good standing, and its silence about these five is
evidence rather than a gap.

Reading that registry took two corrections worth recording, because both are
the same trap as the CLI probe in S461: `ALL_DECLARED_ERROR_CODES` is a tuple
of `(class_path, ErrorCode)` PAIRS, so reading `message_key` off the element
returned nothing; and the namespace it actually uses is `errors.*`, not
`application.filing.errors.*`. A count taken from the wrong shape looks exactly
like a real answer.

Residue: 7 full-literal, 35 tail-only, 98 no-trace.

OPERATOR DECISIONS UNCHANGED. The 125 `cli.*` carry the S461 evidence; the five
`application.*` now carry the same standard of evidence from their own
registry. Two of the 10 `tui.*` are the catalogue side of the blocked
`direction` collision.
