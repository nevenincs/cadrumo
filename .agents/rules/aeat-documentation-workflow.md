---
name: aeat-documentation-workflow
trigger: always_on
---

# AEAT documentation workflow

## Rule
Every change to user-facing or technical documentation must follow the `vaultspec-documentation` skill lifecycle, write incrementally in document-by-document steps, maintain simple taxpayer-general terminology, and verify command syntax against the live CLI and Sphinx build gates.

## Why
Ensuring user-facing docs are simple, technically accurate, and logically cross-linked prevents operator error and documentation rot. The dual-agent workflow isolates context collection from drafting to eliminate process noise and temporary assumptions from final documentation.

## How

### 1. VaultSpec Documentation Framing (`vaultspec-documentation`)
- **Lifecycle:** All documentation processes MUST follow the phases defined in the `vaultspec-documentation` skill:
  - **Phase 1-3:** Wireframe, Refinement (zero-context subagent), and User Approval.
  - **Phase 4-5:** Context Gathering (single-section focus) and Drafting (isolated section-by-section drafting).
  - **Phase 6-7:** Technical Review (cross-referencing codebase/conformance) and Editorial Review (zero-context prose-style review).
  - **Phase 8:** User Approval (final).
- **Dual-Subagent Pattern:**
  - **Researcher:** Gathers codebase context, help commands, and CLI output structures without writing draft files.
  - **Author:** Writes or updates the markdown pages using *only* the gathered research context.
  - **Editor:** Reviews the final pages against newcomers' clarity, tone, and link integrity.

### 2. Simple Language & Story-Driven Content
- **Simple, Non-Demanding Tone:** Do not present all options or complex parameters at once. Walk through concrete scenarios step-by-step.
- ** taxpayer Generalization:** Use general terminology like NIF, CIF, DNI, NIE, or NII rather than referring to a single group (e.g. autónomos).
- **Narrative Progression:** Guide the user from basic profile setup and transaction imports to calculations and reconciliations using clear, story-driven examples.
- **Cross-linking:** Involve the user gradually in complex topics by cross-referencing to how-to guides and CLI references.

### 3. Verification & Compliance Gates
- **Command Conformance:** Verify all documented commands against the live Click/Typer tree using `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`.
- **Sphinx Build:** Verify all cross-references and formatting using the nitpicky build gate `pytest dev/docs/tests/test_docs_build.py`.
- **No Self-Praise:** Keep descriptions objective, factual, and free of self-congratulatory or boastful phrasing.
- **Wiki-links:** Chat responses must use absolute `file://` scheme links with forward slashes for code and files; user-facing docs use relative markdown links.
