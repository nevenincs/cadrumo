---
tags:
  - '#adr'
  - '#modelo-enum-hardening'
date: '2026-06-10'
modified: '2026-09-07'
body_hash: 'sha256:a773367c06b4e796e1e1f800956e244a81e68b932a5b68a874a7955c8c098098'
related:
  - '[[2026-06-10-modelo-enum-hardening-research]]'
---

# `modelo-enum-hardening` adr: `Modelo identifiers as a registry-bound core enum; regulatory values centralised` | (**status:** `accepted`)

## Problem Statement

Production code referenced AEAT modelo identifiers as bare three-digit strings, while regulatory values such as rates, thresholds, caps, and filing years were embedded in feature modules. This made identifier mistakes difficult to catch and allowed regulatory facts to drift outside their owning registry or configuration authority.

The original remediation also introduced authored exception inventories: `NON_REGISTRY_MODELOS`, detector allowlists, campaign-owner carve-outs, and an embed-adjudication ledger. Those structures describe development state rather than product truth. They can conceal drift and must not become production or quality-gate authorities.

## Considerations

Modelo identifiers are a closed domain value set and belong in `cadrumo.core` as a `StrEnum`. Registry loadability, filing support, and regulatory values are separate concerns owned by the validated registry and its typed records.

A modelo's absence from the registry does not itself prove that it is retired, unsupported, or out of scope. Genuine suppression or retirement is a legal lifecycle fact and may be retained only when derived from a typed, cited authority. It must not be represented by subtracting a hand-maintained exception set from the enum.

Quality detectors must report the live tree mechanically. They may exclude syntax that is structurally outside their subject, such as docstrings or type-only literals, but they must not carry inventories of accepted findings, campaign ownership, implementation status, or deferred work.

## Constraints

The enum must remain behaviour-compatible at identifier boundaries because its members are `str` instances. Registry validation remains the authority for whether a modelo can be loaded.

No production module may depend on `dev/` machinery. No production authority may derive from a development ledger, classification, baseline, allowlist, or campaign-owned code list.

A retired modelo may continue to be refused or routed according to its legally grounded lifecycle record. Its behavior must not depend on membership in `NON_REGISTRY_MODELOS` or on the absence of a registry directory.

## Implementation

`cadrumo.core.Modelo` is the typed identifier vocabulary used at production boundaries. Registry-backed behavior is derived directly from the validated registry authority; lifecycle behavior for suppressed forms is derived from typed, cited regulatory evidence.

Regulatory values live in registry/config authorities and are resolved through typed bindings. Modelo-specific feature modules do not embed filing years, monetary constants, rates, thresholds, or regulatory prose as executable policy.

The former Modelo embed adjudication TOML, campaign-owner carve-out, and classification/ownership machinery are deleted. `dev.registry.analysis.modelo_embed_scan` now derives its census directly from the source tree, and `dev.quality.modelo_regulatory_embeds` enforces a zero target. Detector-teeth tests plant representative decimal, filing-year, and regulatory-prose defects and prove that each is reported.

Identifier and regulatory-literal detectors likewise operate on structural syntax and live authorities. A finding is resolved in its owning mechanism; it is never silenced by adding an exception entry.

## Rationale

The enum provides a typed identifier boundary without conflating identity with registry support. The registry and legal lifecycle records remain the authorities for product behavior.

Mechanically derived zero-target detectors cannot drift through stale adjudication entries or accepted residue. Removing authored development metastate ensures that a newly introduced embed or unsupported branch becomes a visible defect whose remedy is a production or registry change.

## Consequences

Gains: typed modelo identifiers, registry-grounded loadability, legally grounded retired-model behavior, centralised regulatory values, and quality gates whose result is derived entirely from the live tree.

Costs: a detector finding cannot be waived locally. False positives must be removed by improving the detector's structural semantics, and genuine regulatory facts must be moved to their owning typed authority.

A new registry-backed modelo is introduced through its registry definition and typed identifier. A suppressed modelo is represented only through cited lifecycle evidence. Neither path requires `NON_REGISTRY_MODELOS`, an allowlist, or another hand-maintained development classification.

## Codification candidates

- **Rule slug:** `modelo-identifiers-use-core-enum`.
  **Rule:** Production code MUST carry AEAT modelo identifiers through `cadrumo.core.Modelo`; registry support and lifecycle behavior MUST derive from their typed authorities, never from a hand-maintained exception inventory.
- **Rule slug:** `modelo-detectors-have-no-authored-exceptions`.
  **Rule:** Modelo quality detectors MUST derive findings mechanically from the live tree and enforce zero unresolved findings; baselines, allowlists, campaign ownership, and adjudication ledgers are forbidden.
