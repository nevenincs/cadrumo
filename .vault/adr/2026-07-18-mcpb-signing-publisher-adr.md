---
tags:
  - "#adr"
  - "#mcpb-signing-publisher"
date: '2026-07-18'
related:
  - "[[2026-07-17-mcpb-signing-publisher-research]]"
superseded_by: '2026-08-23-external-client-boundary-adr'
modified: '2026-08-23'
body_hash: 'sha256:8192a4b174558da01f874c59747fdafe75bbaa037f1d96a107c0bdcb9537d12f'
---
# `mcpb-signing-publisher` adr: `Unsigned MCPB publication posture` | (**status:** `superseded`)

## Problem Statement

The MCPB bundle's signing requirement was an open procurement decision: the
official `mcpb` verifier accepts only operating-system-trusted code-signing
certificates, a self-signed development identity fails verification, and no
trusted Cadrumo signing credential exists in repository scope. The
distribution-installation-readiness constraint "MCPB proof enforces
signing/publisher policy" therefore blocked step S29 on a purchase the project
cannot justify.

## Considerations

Per the signing research: signing appends a detached PKCS#7 signature with an
embedded signing time, so cohort identity must otherwise track two digests;
public verification demands a paid, OS-trusted certificate with the
code-signing extended key usage; the private key would require external
custody and a protected publication job. Cadrumo is an open-source project
with no income; the certificate is a recurring cost and an identity-custody
burden that protects against a threat (bundle spoofing on redistribution
channels) the project's actual distribution model already mitigates: the
bundle is fetched from the project's own GitHub release with a published
SHA-256, and the runtime independently re-verifies every embedded wheel digest
at launch.

## Decision

The MCPB ships UNSIGNED, by operator decision (2026-07-18). The signing
policy for step S29 IS the unsigned posture: the bundle carries no publisher
signature claim anywhere; the release manifest publishes the bundle's SHA-256
as the sole integrity channel; the self-healing bootstrap and the in-bundle
digest pins remain the runtime integrity gates; user documentation states
plainly that the bundle is unsigned and that clients may display it as from an
unverified publisher. Revisit only if the project gains funding or a free
trusted code-signing path for open-source projects becomes available.

## Constraints

- No signing claim may appear in the manifest, docs, or client metadata; the
  bilingual product descriptions must not imply a verified publisher.
- The published-digest channel (release manifest SHA-256 plus the embedded
  per-wheel digests) is load-bearing and stays enforced by the cohort and
  bootstrap gates.

## Implementation

Close S29 as decided: the cohort keeps the single unsigned-bundle digest, the
readiness gate keeps binding it, and the installation guide documents the
unsigned posture and the digest-verification command a cautious operator can
run. No signing scaffolding is added (no dormant code paths per the
no-dormant-surfaces discipline).

## Rationale

An unsigned-but-digest-pinned bundle from the project's own release channel
gives an honest, verifiable integrity story without a recurring cost or a
private-key custody burden; pretending to a publisher-identity guarantee the
project cannot fund would be weaker than stating the true posture.

## Consequences

Claude clients may show an "unverified publisher" style warning on install;
documentation owns setting that expectation. The distribution ADR's MCPB
signing constraint is satisfied by this declared policy rather than a
signature. If the posture changes later, signing rides a new version and
cohort per the rollback rules, never a re-signed in-place artifact.
