---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3741e8d755eab36649a8d937721054e2eb7a6a36c393951a8716ad3c5c4049ef'
step_id: 'S10'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and add descriptor input to certificate-secret storage through the shared capability and hard-cut secret in favor of certificate_passphrase

## Scope

- `src/cadrumo/entrypoints/cli/_config/_certificate.py`

## Description

- Ground certificate-secret transport in the accepted ADR, research, live handler, canonical selector/reader, and closed command inventory.
- Register `_CertificateSecretSetSecrets` as the strict `certificate` variant with only `certificate_passphrase`.
- Route both `--secrets-stdin` and `--secrets-fd` through canonical selection and bounded reading before certificate-domain mutation.
- Add the descriptor declaration to the certificate secret-set command specification without changing sibling authentication commands.
- Prove the retired `secret` field refuses, secret representations remain redacted, and both channel flags occur once in canonical order.
- Remediate the formal review by exercising both canonical channels through `certificate_secret_set`, including conflict-before-mutation, descriptor closure, legacy-field refusal, and non-disclosure assertions.

## Outcome

Certificate passphrase storage now shares the global scalar-secret transport contract. Both explicit channels converge on one registered strict model, conflict selection occurs before the application service is imported or called, interactive prompting remains the only absent-channel route, and the retired generic field has no alias or compatibility path.

The post-landing handler tests close the review's medium proof gap: stdin and fd reach the expected application boundary, the handler closes a consumed descriptor, conflict leaves the descriptor unread and storage untouched, legacy input cannot mutate storage, and neither success metadata nor refusal representations contain the supplied value.

Focused unit, certificate boundary, secure-input, metadata, registration-projection, Ruff, compilation, import, and structural Vault checks passed. The canonical type checker reports pre-existing `_certificate.py` diagnostics outside this step's diff; no new diagnostic is attributable to the changed declarations or handler branch.

## Notes

The first pytest invocation used repository-default xdist and a Windows worker crashed before execution; rerunning the focused lane serially produced a complete green result. The broader integration file has two existing command-identity-envelope failures unrelated to certificate input, while its certificate refusal test passes. Full cross-command subprocess proof remains assigned to the later runtime-matrix steps. The formal audit scaffold remains open for the supervising reviewer because all agent slots were occupied before this commit.

fd 0 stays at the canonical reader seam in this unit lane because replacing process-global stdin around a direct handler test would add fragility without proving new certificate wiring. The later subprocess matrix owns the end-to-end fd 0 proof.
