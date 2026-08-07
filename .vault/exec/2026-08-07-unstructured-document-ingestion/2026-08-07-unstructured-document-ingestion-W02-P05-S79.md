---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f7f94d9f744db59c147e59b8e7e69b84a0f564b225b2fa62d2b815ef902039b9'
step_id: 'S79'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Fold the compiled prompt hash and its registry revision into the LLM cache key and the provenance stamp so a cached response cannot outlive a revision change and an audit can answer under which rates a figure was read, gated by cache-key collision tests and a provenance roundtrip

## Scope

- `src/cadrumo/llm/_client.py`

## Description

- Establish that the compiled prompt already participates in the cache key rather
  than adding a second path to the same guarantee: the key derivation hashes the
  request prompt, and the compiled text carries the resolved rates inline, so a
  rate movement moves the key with nothing further wired.
- Prove that binding discriminates on the rates specifically, by nudging exactly
  the substring the rate authority produced and observing the prompt hash move --
  a control that a key merely reacting to length or to another component cannot
  pass.
- Confirm the provenance stamp both readers emit carries the filing period and
  the compiled-prompt fingerprint, and that a different rate period produces a
  different stamp while the transport half stays derived from the provider.
- Re-run the binding under the two extra fields and the corrected no-tax
  vocabulary, since both move the compiled text and therefore both hashes.

## Outcome

A response cached under one set of rates cannot be served after those rates move:
the enumerated rates are part of the text, the text is part of the key, and a
period whose law differs compiles to a different fingerprint. An audit asking
"under which rates was this figure read?" is answerable from the stamp alone,
without re-parsing prose, because the compiled artefact carries its resolved
values alongside its text rather than only baked into it.

One reading is recorded rather than assumed. The step names the registry
REVISION as the value folded in, and what is folded in is the filing period plus
a content fingerprint of the compiled text. An invoice read has no modelo, so
there is no triple for revision selection to resolve against, and inventing one
would make a stored coordinate causal in exactly the way the authority-flow rule
forbids. The fingerprint is the stronger available binding for this purpose: a
revision id changes when any part of a revision changes, whereas the fingerprint
changes if and only if the values this read actually consumed changed.

## Verification

    pytest src/cadrumo/llm/tests/test_invoice_prompt_cache_binding.py src/cadrumo/llm/tests/test_invoice_field_contract.py src/cadrumo/llm/tests/test_invoice_field_anchors.py -n0 -p no:randomly -q
    90 passed in 29.94s

Run sequentially on a cold interpreter against an isolated export of the tree.
No transport is constructed: the gates exercise a key derivation and a string
property, so they hold on a host that can run no model.

## Notes

The working copy of the llm package was unimportable throughout, because a
concurrent lane's in-flight consent work declares an error class the code
registry does not yet carry. Every run therefore executed against an isolated
export of the commit plus the files changed here, and the dispatch choke point
that lane owns was left untouched.
