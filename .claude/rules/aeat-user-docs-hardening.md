---
name: aeat-user-docs-hardening
trigger: always_on
---

# AEAT user documentation

## Language

Write user-facing documentation in simplistic, singular, imperative instruction
steps. This keeps documentation clear, prevents technical detours, and optimizes
token usage.

## How

- **Good:** "Create taxpayer profile." / "Import bank statement." / "Run
  calculation."
- **Bad:** "We will now set up the taxpayer profiles." / "Let's import our
  transactions." / "Running the calculations."

Do not present every option and parameter at once; walk through concrete
scenarios step by step. Use general terminology (NIF, CIF, DNI, NIE, NII) rather
than naming a single taxpayer group. Guide the reader from profile setup and
transaction import through calculation and reconciliation, cross-linking to
how-to guides and CLI references so complex topics arrive gradually. Keep
descriptions objective — no self-congratulatory phrasing.

## Workflow

Every change to user-facing or technical documentation follows the
`vaultspec-documentation` skill lifecycle: wireframe, refinement, approval; then
context gathering and isolated section-by-section drafting; then technical review
(cross-referencing the codebase and conformance gates) and editorial review; then
final approval.

**Dual-subagent pattern.** A *researcher* gathers codebase context, help output
and CLI structures without writing draft files. An *author* writes the pages
using only that research. An *editor* reviews for a newcomer's clarity, tone and
link integrity. **Final wording and approval stay with the main session** — never
delegate final documentation prose to a subagent.

## Verification

- Command conformance:
  `pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`
- Sphinx cross-references and formatting:
  `pytest dev/docs/tests/test_docs_build.py` (the nitpicky build gate)
- Chat responses use absolute `file://` links with forward slashes; user-facing
  docs use relative markdown links.

Companions: `aeat-docs-scaffolding-cli`, `terminology-single-declaration`.
