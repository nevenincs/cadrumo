---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b9ee403bb10e1e836005dcaf053b9d1eb5dae64f0c86a47d6c3927bf7a5ea3c7'
step_id: 'S66'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Collapse the THREE hand-rolled hex-64 declarations this Wave's premise did not count, each re-declaring the exact literal pattern that core/_hex.py's own docstring names as the thing every such concept must alias instead. The Wave was planned against a reference measurement of TWO duplicates. Measured against the finished tree after all five relocations landed, the real count is SIX. Three are now closed -- the two the reference named plus one found inside domain/modelos/_verification_report.py during the relocation and absorbed there. Three remain and had no row anywhere in this plan, so closing the Wave on its original rows would have left its own stated goal unmet with a checkbox saying otherwise. Rowed as ONE row rather than three because it is one concept at three sites with an identical remedy, and three rows invite three partial closures. TERRITORY, since two fall outside this campaign's modules and the implementation may be routed elsewhere -- application/evidence/_ids.py declares BundleId and EvidenceId, domain/attachments/_ids.py declares AttachmentId, and application/modelo/_m145_communication_records.py declares a record id inline rather than in an ids module. The remedy for each is the one this Wave already proved five times over: alias from the canonical primitive, delete the local pattern constant, and repoint every consumer in the same commit. The release condition is a tree-wide collect with zero ERROR lines, not a checker pass, because a cross-package importer is invisible to both a symbol grep and a type checker and that blind spot is what made this Wave ship a P0 twice

## Scope

- `src/cadrumo/application/evidence/_ids.py`
- `src/cadrumo/domain/attachments/_ids.py`
- `src/cadrumo/application/modelo/_m145_communication_records.py`

## Description

- Re-resolve the row's three named sites against HEAD before touching anything, because the row's own text admits its reference measurement counted two where the truth was six.
- Alias each surviving hand-rolled hex-64 declaration from the canonical primitive and delete the local pattern constant.
- Apply the substitutability pre-filter to every remaining occurrence of the shape before calling any of them promotable.

## Outcome

**Closed by a peer before this lane reached it, and closed WIDER than the row.** `1bc56757f6`
swept six files where the row named three, picking up `_bucket_deletion_contracts.py`,
`_config_reset_models.py` and `bucket_maintenance/_contracts.py` alongside them. Two of the
row's three named modules were subsequently deleted outright, by `fdf575ccc3` and
`9bbdc4d44c`. The third now aliases from the canonical primitive directly.

**THIS RECORD IS RECONSTRUCTED POST-HOC AND ITS AUTHOR DID NOT DO THE WORK.** Written
2026-08-11 by the identity lane from the landed commits and a HEAD sweep.

Measured at HEAD: **zero re-declarations of the hex-64 shape survive in production code.**
The canonical declaration is the only one.

**THE SUBSTITUTABILITY PRE-FILTER CHANGED THE ANSWER AND IS THE REASON THIS ROW SHOULD NOT
HAVE BEEN SWEPT FURTHER.** Three occurrences of the literal shape remain in production and
**none of them is promotable**, so each is documented here rather than collapsed:

- `src/cadrumo/core/_hex.py` - the canonical home itself. Not a violation; it is the target.
- `src/cadrumo/application/modelo/_export.py` - a prefixed digest reference, 71 characters,
  constrained to a literal prefix followed by the 64 hex digits. The canonical alias is
  **not** a superset: it would reject every valid value this type accepts. A different
  concept that happens to embed the same sixty-four characters.
- `src/cadrumo/application/modelo/_selectors.py` - an alternation admitting a 12-character
  short form **or** the full 64. The canonical alias is strictly **narrower**, so promoting
  it would refuse the short form, and the short form is real and in use - the same census
  found short-form calculation revision id parameters being passed.

A fourth occurrence lives under a `tests/` directory as a fragment inside a storage-path
grammar, not as a field type, and is outside production scope.

## Notes

**Had this row been executed as written, it would have been actively harmful.** Its remedy -
alias from the canonical primitive and delete the local pattern constant - applied to the two
surviving occurrences would have rejected every valid prefixed digest reference and refused
the legitimate short-form selector. That is the failure mode where a row is honestly complete
and the tree is worse than before it ran, and neither the checkbox nor the record would have
said so. The pre-filter is what separates a true duplicate from a constraint-shape
divergence, and it costs one reading of each declaration.

**A method note about the sweep that found them.** The first instrument returned zero
production sites - the answer expected, and wrong. The grep dialect treated an escaped brace
as a literal, so the pattern could not match anything anywhere. It was caught only by running
the control first: does this regex find the shape in the canonical module, where it must
exist? It did not, which exposed the instrument rather than the tree. A broken regex reports
a clean tree and never a dirty one, so this class of error is invisible unless a control is
run deliberately.

The row's release condition - a tree-wide collect with zero ERROR lines rather than a checker
pass - was not exercised by this lane, because no commit of this lane's exists to collect.
The closing commits are the peer's.
