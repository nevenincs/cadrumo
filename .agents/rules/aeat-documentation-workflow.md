---
name: aeat-documentation-workflow
trigger: always_on
---

# AEAT documentation workflow

## Rule

Every change to user-facing or technical documentation follows the
`vaultspec-documentation` skill lifecycle, is written incrementally
document-by-document, keeps terminology simple and taxpayer-general, and has its
command syntax verified against the live CLI and the Sphinx build gates.

## Why

Ensuring user docs are simple, technically accurate and logically cross-linked
prevents operator error and documentation rot. Isolating context collection from
drafting keeps temporary assumptions and process noise out of the final text.

## How

### Lifecycle

Follow the phases the `vaultspec-documentation` skill defines: wireframe,
refinement, and user approval; then context gathering (single-section focus) and
isolated section-by-section drafting; then technical review (cross-referencing
the codebase and conformance gates) and editorial review; then final approval.

**Dual-subagent pattern.** A *researcher* gathers codebase context, help output
and CLI structures without writing draft files. An *author* writes the pages
using only that research. An *editor* reviews the result for a newcomer's
clarity, tone, and link integrity. **Final wording and approval stay with the
main session** — never delegate final documentation prose to a subagent.

### Language

Write in simple, singular, imperative instruction steps: "Create taxpayer
profile.", "Import bank statement.", "Run calculation." — never "We will now set
up the taxpayer profiles." or "Let's import our transactions."

Do not present every option and parameter at once; walk through concrete
scenarios step by step. Use general terminology (NIF, CIF, DNI, NIE, NII) rather
than naming a single taxpayer group. Guide the reader from profile setup and
transaction import through calculation and reconciliation, cross-linking to
how-to guides and CLI references so complex topics arrive gradually.

Keep descriptions objective and factual — no self-congratulatory or boastful
phrasing.

### Verification

- Command conformance:
  `pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`
- Sphinx cross-references and formatting: the nitpicky build gate
  `pytest dev/docs/tests/test_docs_build.py`
- Chat responses use absolute `file://` links with forward slashes; user-facing
  docs use relative markdown links.

Companion: `aeat-user-docs-hardening` (the language rule in its shortest form).
