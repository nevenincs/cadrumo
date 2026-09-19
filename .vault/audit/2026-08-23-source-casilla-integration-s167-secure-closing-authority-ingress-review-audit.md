---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e4a3484257537e86b67696a5af339c58e92123bab3537128c6b0c43117cef88a'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `s167 secure closing authority ingress review`

## Scope

Independent review of S167 encrypted authority persistence, replay and conflict behavior, bounded CLI channels, schema parity, localization, and confidentiality across command output, errors, logs, and later inventory mutations.

## Findings

### s167-secure-closing-authority-ingress-review | high | resolved divergent records could overwrite admitted authority

The guarded repository mutation now admits only an absent record or an exact canonical-fingerprint replay. A changed decision, physical observation, evidence digest, or prior-closing source raises a typed conflict and leaves the encrypted original unchanged.

### s167-secure-closing-authority-ingress-review | high | resolved ordinary payloads exposed nested authority facts

Ordinary ledger projections now remove the complete authority object and expose only canonical fingerprints. Tests use evidence, actor, command, timestamp, and digest canaries across the authority result, errors, captured logs, and a later movement response.

### s167-secure-closing-authority-ingress-review | high | resolved command behavior lacked an executable proof

The final real-runner matrix exercises movement-derived and physical authority through stdin, a one-shot descriptor including closure, invalid UTF-8, conflicting or absent channels, recursive duplicate keys, oversized input, malformed and incomplete shapes, replay, divergent refusal, and fingerprint-only envelopes.

### s167-secure-closing-authority-ingress-review | medium | resolved validation errors could carry source values to logs

Top-level bounded parsing is value-free, and nested canonical domain validation is caught at the CLI boundary and translated without rendering Pydantic input values. An inconsistent activity coordinate is mutation-tested against both output and captured logs.

### s167-secure-closing-authority-ingress-review | medium | resolved transport schema and locale drift

Ledger and list-row payloads now share canonical inventory schema version 3, the retired `closing_stock` input field is absent, the display-only preview is named `derived_closing_value`, and every new help and refusal key exists in all four supported locales at its requested namespace.

### s167-secure-closing-authority-ingress-review | pass | final secure ingress is complete

Final review reported zero critical, high, medium, or low findings. Sixteen integration tests, 75 focused tests, two locale gates, Ruff, the type checker, and diff hygiene were clean.

## Recommendations

Proceed to S168 using the persisted ledger-owned record and canonical resolver; do not rebuild authority, continuity, or conflict semantics in projection code.
