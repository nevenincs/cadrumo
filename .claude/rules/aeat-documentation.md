---
name: aeat-documentation
trigger: always_on
---

# AEAT documentation

## User-facing documentation

- Write concise, outcome-oriented documentation in the user's language. State prerequisites, exact commands, observable results, failure behavior, and recovery where those facts matter.
- Use the product name Cadrumo consistently. Use AEAT names, Spanish domain terms, and command tokens exactly as the product exposes them; do not invent synonyms for canonical concepts.
- Keep each fact in one authoritative home. Link to that home instead of duplicating command inventories, schemas, legal claims, or status across documents.
- Generated API and CLI references are owned by their generators. Change the source or generator, regenerate, and verify the diff; never hand-edit generated reference files.
- Examples must be safe, runnable, and free of credentials, taxpayer data, machine-specific paths, and stale campaign state.

## Evidence and licensing

- Legal and filing claims cite the applicable official source. Technical claims identify the live code or generated reference that establishes them.
- External research is paraphrased and license-clean. Do not copy substantial text, diagrams, or examples whose reuse rights are unclear.
- Reviews check terminology, command accuracy, links, safety, and consistency with the live product. No document requires a particular number or topology of reviewers.

## Repository separation

User documentation must not explain internal Vaultspec workflow, agent roles, plan steps, audit identifiers, or rule slugs. Architecture and implementation records belong in the vault; production and user documentation remain self-contained.
