---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S29'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Bind MCPB contents signing identity and bootstrap to the immutable cohort

## Scope

- `packaging/mcpb/build.py`

## Description

- Inspect the official MCPB 2.1.2 signing command and verifier implementation.
- Sign a copy of the retained cohort-bound MCPB with an ephemeral development
  certificate and run the official verifier against the resulting bytes.
- Compare signature trust, archive-member integrity, and deterministic cohort
  identity requirements with the accepted protected-publication boundary.
- Delete the ephemeral private key, certificate, and experimental signed bundle.
- Record the trusted publisher inputs and post-signing client proof still required.

## Outcome

- The official signer appended a PKCS#7 signature block to the completed unsigned
  MCPB. The bundle grew from 170,102,293 to 170,103,747 bytes while retaining the
  same six ZIP members.
- The official verifier did not accept the self-signed development identity and
  reported `Extension is not signed`. This bundle therefore cannot substantiate a
  public Cadrumo publisher claim.
- MCPB 2.1.2 verification requires an operating-system-trusted certificate chain
  with code-signing extended key usage. No trusted Cadrumo signing credential or
  approved publisher fingerprint is available in repository scope.
- Signing time is included in the signature, so the immutable cohort must retain
  the deterministic unsigned digest separately from the promoted signed-delivery
  digest, signer fingerprint, certificate chain, and exact MCPB CLI version.
- The only production-capable path is a protected publication job using an
  externally held trusted code-signing key, followed by official signature
  verification, expected-publisher fingerprint enforcement, signed-bundle client
  installation, and the real tax oracle.
- The narrow research record
  `2026-07-17-mcpb-signing-publisher-research` retains the version-bounded primary
  source locators, alternatives, and trust-boundary findings.

## Notes

- No private key, certificate, or experimental signed bundle was retained.
- The existing MCPB remains accurately marked unsigned. No production signing or
  publisher claim was added to source, artifacts, or user documentation.
- Step S29 remains unchecked. It cannot pass until the trusted publisher identity
  exists and the exact signed delivery is installed and completes the tax-work
  oracle; a format-valid self-signed signature is not a substitute.
- RESOLVED BY DECISION (2026-07-18): the accepted `mcpb-signing-publisher`
  ADR rules the MCPB ships unsigned — an open-source, no-income project does
  not procure a paid code-signing identity; the published release SHA-256 plus
  the in-bundle per-wheel digest pins are the declared integrity channel, and
  user documentation owns the unverified-publisher expectation. The signing
  policy this step binds to IS the unsigned posture, so the row closes as
  decided rather than as a deferral.
