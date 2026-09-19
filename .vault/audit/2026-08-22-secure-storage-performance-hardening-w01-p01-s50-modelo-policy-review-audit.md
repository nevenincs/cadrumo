---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:a4e0d5617f7861a95c3cfe6b0f1ad569fa879deed2fd43646de68415f83f7c98'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `W01 P01 S50 modelo policy review`

## Scope

Independently audit the complete live `aeat app modelo` subtree after callback-local execution-policy enrollment. Trace maximum reachable authorities, side effects, write routing, destructive and handoff judgments, group invocation parity, future-node coverage, and planted downgrade behavior against the real implementations. Confirm that the legacy keyed risk table remains only as a temporary S52 migration dependency and is not used as the new policy authority.

## Findings

### proportional-capabilities | high | Coarse presets over-declared calculation and custody

The first pass assigned calculation and encrypted-fact authorities to registry-only discovery, local encrypted reads, and local cryptographic verification. This would have defeated command-proportional loading. Resolved by splitting direct registry, registry-plus-profile, encrypted local, calculation, filing, interactive, browser, crypto-only, crypto-plus-secure-read, and crypto-plus-secure-write policy shapes and by exhaustively partitioning every live modelo path in the gate.

### reconcile-browser | high | Reconcile pull omitted its Playwright browser authority

The first pass described `reconcile_pull_verb` as network-only even though its live capture path opens the declarations register through Playwright. Resolved with a browser, network, registry, and encrypted-facts policy carrying browser, network, and local-state effects while keeping `live_write` false because AEAT access is read-only.

### crypto-taxonomy | high | The capability taxonomy could not represent local cryptography honestly

The original taxonomy forced Ed25519 and X25519 verification into either state-free or custody-bearing classifications. Resolved with an import-light `crypto` capability that implies no storage authority. Crypto verification now declares only crypto; commands reading encrypted recipient or key state add encrypted-facts explicitly; commands mutating replay, key, journal, or imported feedback state additionally use the profile-bound route.

### semantic-gate-teeth | high | Presence-only coverage did not detect policy downgrades

The initial gate proved only that every node had a policy and sampled a few paths. Resolved with an exact live path-to-policy-family partition, direct field assertions for registry, browser, crypto, encrypted-facts, side effects and write routes, plus planted unclassified, browser, registry, crypto and profile-route downgrades.

### dead-preset | low | An unused local-read preset remained after policy splitting

Resolved by deleting the speculative preset before landing.

## Recommendations

All review findings are resolved. Preserve callback-local policy as the sole new authority. At S52, delete the complete legacy keyed risk table, its exports, consumers, and table-specific tests after those consumers use live-node policy; do not retain an alias, compatibility shim, or fallback.
