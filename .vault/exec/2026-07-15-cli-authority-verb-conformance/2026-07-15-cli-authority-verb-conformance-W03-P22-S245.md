---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S245'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove duplicate namespace and custody declarations from Clave, LLM cache and usage, bundle, attachment, and secure-storage consumers without conflating certificate custody with master-key keyring custody

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/`
- `src/cadrumo/adapters/outbound/llm/`
- `src/cadrumo/application/evidence/`
- `src/cadrumo/domain/attachments/`
- `src/cadrumo/adapters/persistence/storage/`

## Description

- Verify independently that the split namespace authority the sibling deferred on was in fact resolved.
- Confirm the Clave, session-store, LLM, evidence-bundle and attachment consumers all bind to registered definitions.
- Classify the remaining product-prefixed literals in the storage tree and establish that none of them is a secure-object namespace.
- Confirm the certificate keyring backend is gone while master-key keyring custody remains intact and separate.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

The sibling step this mirrors was marked closed while its own text read as deferred, pending an adjudication of whether namespace authority was split between the core constants module and the storage registry. That adjudication has landed, and it was checked here rather than taken on trust. The Clave diagnostics namespace constant is absent from the core constants module, and the Clave page flow now sources both the sensitivity and the schema version off the registered definition at its write site, with the diagnostics support module taking the namespace string off the same definition. The split is closed and the registry is the surviving authority.

The rest of the cited consumers were already bound. The browser session store reads the namespace, the sensitivity and the schema version off its definition at every call site, including the existence check, the save, the list, the delete, and the former-path migration probe. The LLM cache, usage and run-telemetry stores each derive their namespace, version and sensitivity from their own registered definitions. The evidence bundle service binds its three class variables to a registered definition. The attachment store binds both its blob and manifest namespaces the same way and derives its logical paths from them. No consumer in these trees restates a namespace, a sensitivity member, or a schema version.

The storage tree still holds a substantial number of product-prefixed literals, and every one was classified before concluding. They are cryptographic domain-separation values, not namespaces: additional-authenticated-data byte strings for the envelope cipher, the encrypted columns, the blob payload and its wrapped key, the master key, the persisted session and the recovery key, plus key-derivation context strings for the column lookup, the secret store's lookup and value witness, and the per-store rotation contexts. These are versioned crypto context labels whose values participate in key derivation and authentication, so folding them into the namespace registry would change decryption rather than centralise metadata. They are correctly outside this step. Two further hits were docstring examples of the general form of such a context.

The custody distinction the step warns against conflating is intact. The certificate keyring backend is absent from the tree, consistent with the governing decision's unconditional hard cut, and no certificate-keyring selector, factory branch or backend survives. Master-key custody is untouched and remains its own separate implementation, holding the master key, the persisted profile session and the recovery-key wrap. The two were not merged, and nothing here moved either.

Run at the current commit as part of a thirty-four test run covering the registry suite and both namespace adoption gates: all passed. No change was needed or made.

## Notes

Semantic code search was degraded and reported itself healthy, with an empty degraded-reasons list, so the Clave adjudication was confirmed by grepping the core constants module for the retired constant and reading the page-flow write site directly, rather than by searching for the concept. The distinction between a namespace literal and a crypto context literal is exactly the kind of judgement a degraded search cannot support, since both are product-prefixed strings that a keyword sweep returns together; separating them required reading each declaration's use.

The step's scope cites the whole storage tree, which is also the registry's own home, so a naive literal sweep over that path returns the registry's sixty-six declarations plus every crypto context and reads as a large violation set. The registry's own module has to be excluded and the crypto contexts classified before the tree can be judged. That is worth recording, because the same sweep run without those two exclusions would produce a false finding.
