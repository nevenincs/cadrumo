---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S45'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# bind the registry prorrata percentage formula to the domain prorrata function with a parity gate over ratios that discriminate between the two roundings, closing the two-authorities condition that hid the rounding defect

## Scope

- `src/cadrumo/domain/iva/_prorrata.py`

## Description

- Close this Step against work that had already landed rather than executing it a
  second time.
- Verify at HEAD that the parity gate exists and does what this Step asked for:
  `test_registry_and_domain_agree_on_the_prorrata_percentage` binds the registry
  formula's output to the domain function's, and
  `test_selected_ratios_discriminate_between_the_two_roundings` proves the chosen
  ratios actually separate the two roundings rather than assuming they do.

## Outcome

The Step is satisfied by the rounding-correction commit, not by new work. It was
opened from a code-review recommendation while the rounding fix was already in
flight, and the executing agent implemented the parity gate as part of that fix
and then reported the overlap rather than letting a duplicate be built on top.

Verified at HEAD before closing: both test functions are present in the
registry-side rounding grounding module, and the discrimination test is the part
that matters — a parity gate over ratios that do not separate half-up from
upward rounding would pass with the defect restored, which is precisely how the
original defect survived. The executing agent also caught its own gate going
vacuous mid-authoring, rejecting a 76,5 percent candidate because half-up already
rounds a half upward, and replacing it with 76,4 percent.

The condition this Step existed to close is therefore closed: two independent
authorities computed one legally-defined quantity, and nothing bound them. They
are now bound over ratios proven to discriminate.

## Notes

Closed by the coordinator on verification of another agent's commit, so the
authorship credit belongs to the rounding-correction Step rather than here.

The Step should not have been opened. It came from a review recommendation that
was correct in substance but was written without checking whether the in-flight
fix already covered it. The cheap guard is the one the executing agent applied
unprompted: when a Step's scope overlaps work already running, verify at HEAD
before executing, and report the overlap rather than building the duplicate.

Two defects surfaced by the same investigation are tracked separately rather than
folded in here: the two revisions disagree on the zero-volume branch, where the
older one would zero every deduction for a fully-taxable trader who declared no
prorrata volumes, and the domain module's docstring cites the autoconsumo article
rather than the one that establishes the formula and the rounding.
