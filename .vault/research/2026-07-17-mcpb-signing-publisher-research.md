---
tags:
  - '#research'
  - '#mcpb-signing-publisher'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
---

# `mcpb-signing-publisher` research: trusted, cohort-bound MCPB signing

This research resolves whether a public Cadrumo MCPB can be signed reproducibly,
how its publisher identity is verified, and where signing belongs relative to the
immutable distribution cohort. It grounds `W02.P06.S29` without treating an
untrusted development certificate as production evidence.

## Findings

### The official format signs the completed unsigned bundle

`@anthropic-ai/mcpb@2.1.2` implements `mcpb sign` by creating a detached PKCS#7
SHA-256 signature over every byte of the completed unsigned MCPB, then appending a
versioned `MCPB_SIG_V1` block after the ZIP end-of-central-directory record. The
signature includes a signing-time attribute. The unsigned ZIP remains readable and
its members are unchanged, but the delivered file has a new digest and is not a
byte-for-byte deterministic rebuild. Locators:
`https://github.com/modelcontextprotocol/mcpb/blob/main/CLI.md`,
`https://github.com/modelcontextprotocol/mcpb/blob/main/src/node/sign.ts`, and
`@anthropic-ai/mcpb@2.1.2`.

Consequently, cohort identity must bind two distinct objects: the deterministic
unsigned content digest and the promoted signed delivery digest. The promotion
record also needs the publisher certificate fingerprint, certificate chain, signing
tool version, and the cohort identifier whose unsigned content was signed. A claim
that the signed bytes themselves are reproducible would be false because signing
time is part of the signature.

### Public verification requires a trusted code-signing identity

The official verifier does more than confirm that the PKCS#7 signature matches the
bytes. On Windows it builds an operating-system certificate chain with online
revocation and the code-signing extended-key-usage OID
`1.3.6.1.5.5.7.3.3`; on Linux it delegates chain validation to
`openssl verify -purpose codesigning`. A certificate that is neither trusted nor
issued for code signing cannot establish the public publisher claim. Locator:
`@anthropic-ai/mcpb@2.1.2`, installed `dist/node/sign.js` corresponding to the
official source above.

A real execution against the retained MCPB proved that the CLI can append a
signature while still refusing to classify a one-day self-signed development
certificate as signed: `mcpb sign` succeeded, the file grew from 170,102,293 to
170,103,747 bytes, the six ZIP members remained unchanged, and `mcpb verify`
reported `Extension is not signed`. This exposes a material mismatch between the
CLI prose describing self-signed warning states and the current 2.1.2 verifier's
chain-first behavior. The temporary key, certificate, and signed test bundle were
deleted after the observation; none is a release credential or retained artifact.

### Signing is a protected promotion, not an assembly input

The immutable cohort must be assembled and behavior-tested before any private-key
operation. A protected release authority can then sign exactly those unsigned bytes,
verify the resulting signature with the official pinned verifier, demonstrate that
the signed file still contains the cohort-bound unsigned payload, and run the real
client installation and tax oracle against the signed delivery. This preserves the
accepted single-publication-authority boundary while preventing a signature from
blessing untested or subsequently modified content. Internal locators:
`2026-07-15-distribution-installation-readiness-adr`,
`packaging/mcpb/build.py`, and `dev/packaging/smoke_mcpb.py`.

The private key must remain outside the repository, bundles, logs, and general build
workers. The public leaf certificate and intermediate certificates may accompany
the release evidence. The release authority must compare the verified leaf
fingerprint with an explicit publisher allowlist; successful chain validation alone
does not prove that the signer is the Cadrumo publisher selected by this project.

### Options

1. **Trusted code-signing certificate in the protected publication job — retain.**
   Use an externally held code-signing key, supply the public chain, pin the official
   MCPB CLI version, record unsigned and signed digests, verify the expected publisher
   fingerprint, then install and tax-test the signed artifact. This is the only option
   that satisfies the public publisher, immutable-cohort, and real-install claims.
2. **Self-signed certificate — reject.** It is suitable only for format experiments,
   is not a public publisher identity, and current 2.1.2 verification did not accept
   the observed signed bundle.
3. **Remain unsigned and describe the limitation — retain only as an honest fallback.**
   This permits continued unsigned assembly testing but cannot close `W02.P06.S29`
   or support a signed public-release claim.

### Unknowns and boundary

No trusted Cadrumo code-signing certificate, private-key service, or approved
publisher fingerprint is currently present in repository scope, so this research
does not claim that signing can run locally today. It did not evaluate commercial
certificate providers or choose a key-management vendor; those are release-authority
and procurement choices. Confidence is high for MCPB 2.1.2 format and verifier
behavior, and deliberately version-bounded because later MCPB releases may change
their trust semantics.
