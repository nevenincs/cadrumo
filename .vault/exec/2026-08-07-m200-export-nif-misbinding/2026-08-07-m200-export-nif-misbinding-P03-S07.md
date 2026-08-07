---
tags:
  - '#exec'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f578431fe9a3c35fc9051b1c2d66d84fc901c3f74ef3da93459d412c06f8a3e6'
step_id: 'S07'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
---

# Scaffold a research document recording the unwired grupo mercantil block and the unswept broader draft-attribute, casilla, and binding semantic-mismatch sweep as open questions for a future ADR

## Scope

- `.vault/research/2026-08-07-m200-grupo-mercantil-wiring-research.md`

## Description

- Scaffold a research document through the owning verb and record the two follow-ups the closing decision scoped out.
- Measure declared widths per draft attribute across the whole registry to test whether the broader class is really unswept.
- Record the second live divergence that measurement surfaced, and what the standing goal still asks for that the fix excludes.

## Outcome

The document exists at
`.vault/research/2026-08-07-m200-grupo-mercantil-wiring-research.md`, scaffolded
through the owning verb and linked to the governing decision record, its plan, and
its reference.

It records more than the two follow-ups it was opened for, because measuring the
corpus to characterise the unswept class found a live instance of it. Modelo 200's
first emitted record binds a 4-character filing year to a 17-byte slot, and 17 is
the width of the whole envelope-open tag that sibling modelos compose from six or
seven fields. The real export's first bytes are the year followed by spaces, and
its last bytes are blank where a sibling modelo renders a closing tag, so Modelo
200's fichero appears to carry neither envelope tag. The document states what this
needs before anyone acts: the published design for the page-000 record, which the
sheets already read do not cover.

It also writes down, beside the narrowing, what the standing goal still asks for
that the closing change excludes, namely a correct filing for a group member. The
fix traded affirmatively-wrong data for an honest absence, which is an improvement
and not correctness, and the entire descriptive block still ships blank for every
group filer.

Three smaller residuals are recorded so they are not lost: the field id that still
names a binding it no longer carries, the fact that the shipped gate deliberately
abstains over the divergence above together with what gating it would cost, and
that a foreign parent's tax identifier cannot reuse the declarant identifier type
at all, because that type enforces the Spanish checksum.

## Verification

    uv run --no-sync vaultspec-core vault check placeholders
    ok placeholders: clean

    uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-08-07-m200-export-nif-misbinding-plan.md
    (no output; clean)

The vault check fix pass reconciled the document's body hash and modified stamp.

## Notes

Width divergence is a weak proxy for the class and the document says so: it finds
a slot of the wrong SIZE and is blind to a slot of the right size and the wrong
MEANING. The sweep the decision record opened is still not performed, and the
document does not imply otherwise.
