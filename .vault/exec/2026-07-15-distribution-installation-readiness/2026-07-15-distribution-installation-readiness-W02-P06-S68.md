---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S68'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Verify English and Spanish MCP product descriptions in plugin, marketplace, MCPB, and client-display metadata while preserving English-only model-facing descriptions

## Scope

- `dev/packaging/verify_distribution_identity.py`
- `src/cadrumo/agent/_workspace.py`
- `packaging/mcpb/manifest.json`

## Description

- Materialise the production Claude plugin and marketplace trees in an isolated
  directory and read their client-display description fields.
- Read the MCPB short and long product descriptions without changing the source
  manifest or generators.
- Require one explicit English section and one explicit Spanish section in every
  user-facing MCP product-description field.
- Record separate capability, safety, privacy, on-host storage, human confirmation,
  and never-files-live verdicts for each language.
- Exclude model-facing tool, prompt, resource, and argument descriptions from the
  localization target.
- Exercise the verifier through direct production imports and its command-line entry
  point.

## Outcome

The verification implementation passes focused Ruff and seven focused real-behavior
tests. The production command exits `1`, as required for the current distribution, and
writes a retained report whose SHA-256 is
`8ac51513f603545fcaf26142efd0388508413aac65ac1be5050a6feea81c3fdc`.

The report inventories five real client-display fields: the generated Claude plugin
description, generated marketplace description, marketplace-served plugin description,
and the MCPB `description` and `long_description` fields. Every field contains
unlabelled English copy, no explicitly labelled English section, and no Spanish section.
The MCPB long description carries all six claims in English; the other shorter surfaces
carry only subsets. No field has English/Spanish claim parity, so the product-description
verdict is false.

No translation wording has been approved by this verification-only step, so keyword
similarity cannot make a description pass. Compliance requires an exact, separately
product-reviewed pair for the specific surface and field; the approved-pair inventory is
currently empty. Tests prove that natural `Inglés:` and `Español:` labels parse while a
deliberately contradictory bilingual sample remains noncompliant.

The English-only model-facing boundary is observed rather than declared. The verifier
inventories 1,625 real tool, prompt, resource, and argument descriptions, requires every
row to be nonempty and free of product-language section labels, and byte-compares the
canonical inventory digest
`5eaa233019daecfffc215ec482fa36dfdc4763a03b412c00f615cfd45496d9a0`.

The inspection did not change any identifier, description, generator, manifest, or
artifact. Model-facing operational descriptions remain English-only and outside this
verification target.

## Notes

This row remains unchecked. The accepted identity decision explicitly makes this step
verification-only and requires a failed bilingual result to remain open for a separately
approved translation and artifact migration. The retained report lives under the ignored
distribution-readiness evidence tree; its command status and digest are recorded above.

A formal review initially found a semantic false-pass, an undocumented language-label
grammar, and a declared-but-unobserved model-facing boundary. The implementation now
requires exact product-review approval, supports localized label forms, inventories the
real operational copy, and adds direct success-path and contradiction coverage. The
rolling audit retains those findings and records a passing final remediation review with
no remaining S68 implementation finding.
