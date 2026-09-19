---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:bfa0083d5e26d3eb2441acda06acf50677d5d19273389eacaec1172e0ab0879e'
related: []
---

# `registry-authority-artifact-boundary` audit: `artifact runtime`

## Scope

The W02.P03.S03 artifact-only runtime authority path was audited before closing the runtime switch.

## Findings

### artifact-runtime | critical | Package resources do not yet contain a published authority

The runtime reader requires the artifact and verification resource but neither is present in the package data tree. The staged tests prove reader behavior only; a live authority probe refuses before any authority-consuming workflow can run.

### artifact-runtime | high | Artifact-local source root breaks corpus-backed workflows

The artifact authority uses its own directory as `source_root`, while citation and inspection consumers resolve bundled corpus material through the authority source root. The package corpus is elsewhere, so those workflows would resolve the wrong location after publication.

### artifact-runtime | high | Co-located verification key is replaceable with the artifact

The reader obtains its public key from the same mutable package-resource directory as the signed artifact. Replacing both permits an attacker-controlled authority signed by an attacker-controlled key. The trust anchor must not be replaced as part of authority publication.

## Recommendations

- Publish the actual signed artifact and release trust material only after the shared corpus validates.
- Use the package data root for source-backed runtime workflows and exercise citation resolution.
- Bind the verification key through a non-publishable release trust anchor and prove forged artifact plus substituted sidecar is refused.

### artifact-runtime | critical | No publisher credential can produce a trusted release artifact

The compiled trust anchor has no matching development or release signing credential in the checked repository configuration or process environment, and the package has no authority artifact. A live runtime read therefore cannot succeed. Creating and committing a private key would violate the intended release trust boundary.

- Provide the externally managed Ed25519 private key that corresponds to the compiled trust anchor through the release secret mechanism, then publish from a corpus-valid candidate and run the non-monkeypatched installed workflow.
