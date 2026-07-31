---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:7f44b12a863473540e7cf688665c3e118f4f69612597986280b25fa351f9f43d'
step_id: 'S04'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

# Prefix the orientation-prompt embedded rule-resource URI (the synthetic cadrumo://rule/operating-rules leaf) so every embedded reference carries the cadrumo- prefix, and update the prompt and resource projection tests

## Scope

- `src/cadrumo/entrypoints/mcp/_prompts.py`

## Description

- Prefixed the orientation-prompt embedded rule-resource URI in `_prompts.py`: the synthetic `resource_uri(HarnessResourceKind.RULE, "operating-rules")` leaf is now `"cadrumo-operating-rules"`, so the embedded reference in `cadrumo://rule/...` carries the `cadrumo-` product prefix.
- Updated the prompt-projection assertion in `test_prompts.py` to expect `cadrumo://rule/cadrumo-operating-rules`.

## Outcome

- This is the one non-derived MCP projection identifier (a synthetic aggregate label for the concatenated operator-rules bundle, not a single rule file), so no other surface changes. The per-skill embedded SKILL URIs and the RULE/PERSONA resource stems all auto-derive from the renamed filenames and were already compliant after P01.
- Green gates: `test_prompts.py` + `test_harness_delivery.py` 32 passed; ruff check + format + ty clean on the two touched files.
- The distribution-identity verifier self-test (`test_verify_distribution_identity.py`, which still pins the pre-migration `["operating-rules"]` failure) stays red by design and is re-baselined in P04.S10; it was not touched.

## Notes

- No incidents.
