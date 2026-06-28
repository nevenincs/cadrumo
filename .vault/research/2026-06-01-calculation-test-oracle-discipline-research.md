---
tags:
  - '#research'
  - '#calculation-test-oracle-discipline'
date: '2026-06-01'
modified: '2026-06-01'
related: []
---

# `calculation-test-oracle-discipline` research: external oracles available for spanish-tax calculations

## Findings

### Four classes of external numeric authority exist

AEAT publishes worked examples in the annual manuals (for example
the `Manual Práctico de IRPF` for renta). Each example fixes a
profile shape and reports the expected casilla outputs to the
cent. These are the highest-authority oracle: AEAT's own
declaration of what the formula should produce. Cited inline as
`# oracle: AEAT-MANUAL-<year>-<page-or-section>`.

BOE publishes the regulations the formulas implement. Articles in
LIRPF, LIVA, LIS, and their reglamentos fix the legal formula a
calculation must satisfy. The article number plus subsection
identifies the rule that authorises the expected output. Cited
inline as `# oracle: BOE-A-<year>-<number> art. <n>`.

AEAT distributes template workbooks (for example the IRPF
"calculadora" .xlsx and the IVA pre-303 worksheets). These return
canonical results for any input the operator supplies. Cited
inline as `# oracle: AEAT-WORKBOOK-<workbook-id> sheet <name>`.

The live AEAT oracle accepts a populated profile and returns the
canonical filing surface. Replayed inputs and outputs are captured
once, signed by the operator, and committed as a fixture record.
Cited inline as `# oracle: live replay <date> <reference>`.

### Hand-computed expectations are the only oracle with zero probative value

A test that hand-computes the formula under test asks the question
"does the registry produce f(X) when given X?" where f is the same
formula the registry encodes. The test cannot fail when the
registry's encoding of f is wrong against AEAT; it can only fail
when the registry's encoding of f drifts away from the formula the
test author also encoded. The test therefore tests nothing about
AEAT correctness.

### Non-numeric test shapes are still acceptable

Graph wiring tests assert that two registry surfaces refer to the
same entity (for example, that an IVA modelo binds the IVA ledger
to the IVA filing schema). These tests have no numeric assertions
and need no oracle.

Validation-error tests assert that the registry rejects a malformed
input shape (for example, that a negative casilla value raises
`ValidationError`). The expected behavior is a typed exception;
no numeric oracle is needed.

Provenance tests assert that every CasillaObservation carries
non-empty `legal_refs` and `source_refs`. These are structural;
no numeric oracle is needed.

Schema-shape tests assert that the engine's output envelope
satisfies the strict pydantic model. Structural; no numeric oracle
is needed.

### The acceptance question

"Would this test fail if the registry formula disagreed with
AEAT?" If the answer is no, the test is tautological and must be
replaced with a structural test or a test grounded in one of the
four external oracle classes above.

## Decision

Carried in the related ADR
`2026-06-01-calculation-test-oracle-discipline-adr` and the
repo-rule `no-tautological-calculation-tests.md`. The ADR registers
a codification candidate for promotion of the inline-citation
discipline into a project rule.
