---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:21e1fdd032aaae3a9a718a3d40e264b8aac95f00bd9680cb98b1a8d9b3d16226'
step_id: 'S47'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

## Outcome

The diagnostic message cap now truncates instead of refusing, and the headroom gate
lands alongside it. Commit `4277ecc160`.

The Step was posed as a choice between two mechanisms. Both were correct, and the
reason is severity asymmetry: a crash stops a filing, a shortened advisory degrades a
message. A defence against the severe failure cannot rest on a gate that must FIND
twelve advisory factories with varied signatures across two modules -- particularly
after an AST sweep in this same campaign under-counted join sites by a factor of 3.5.

Once the type is total, the gate's known weakness stops being a correctness hole and
becomes a quality one. That inversion is what makes the pairing right rather than
belt-and-braces.

## What the mechanisms each carry

The `field_validator` on `CalculationSourceDiagnostic.message` truncates an over-long
message rather than raising, making the blocking failure impossible by construction.
The original constraint was fail-closed on a fail-open channel: only
`unrouted_observation` diagnostics carrying a `binding_source` are ever persisted, so
these `source_issue` advisories were being refused by a constraint guarding a store
they never reach, while `Notice.message` -- their real destination -- is uncapped.

The headroom assertions cover exactly the messages sized by taxpayer-controlled data,
keeping truncation a floor rather than a licence. A message that reaches the truncator
has already lost words an operator was meant to read.

## The Step's real finding

The headroom assertions failed on arrival. The withheld advisory sat at 497 of 512 --
fifteen characters, correct to a million descendants and one clause from re-crashing.

Trimmed to fifty-six characters of headroom while preserving both load-bearing points:
that an over-three adopcion or acogimiento is withheld for a missing ENTRY date rather
than a birth date, and that the remedy is remove-then-add rather than add.

## Reached and rejected

Raising the 512 cap was considered and rejected with reasoning rather than dismissed.
It does not remove the class -- any cap can be crossed by data-scaled content, so it
moves the threshold and buys one clause.

But the instinct that something was wrong with the copy was right, and it points
elsewhere. Nearly five hundred characters of prose is a diagnostic carrying REMEDY
DETAIL, and remedy detail belongs on the notice context: structured, already the
sanctioned home for provenance, and read by an agent operator rather than skimmed.
That is the durable reduction and it is contract-shaped rather than another round of
prose trimming. Opened as `S49` rather than folded in, because it is a copy-and-contract
change across every advisory in the surface.

## Measurement correction

The maternidad descendant-id bound caps at 23 characters even at a million descendants,
not the ~96 that had been in circulation. The ~96 belongs to the sibling module's
helper, which renders full fact paths. Two bounds with very different worst cases; the
earlier floor arithmetic in this campaign used the sibling's figure against the
sibling's advisories, which is why it held.

## Verification

Sixteen gate tests pass. 631 unit and 7 integration run explicitly, both marker lanes
named rather than assumed.

One honest non-result, recorded rather than erased:
`test_work_calculate_input_bundle_rejects_ambiguous_reused_printed_number` failed once
in a combined run, then passed in isolation, as a module, and on a re-run of the
identical combination at 631 passed. Not reproduced, and not claimed fixed.
