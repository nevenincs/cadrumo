---
tags:
  - '#reference'
  - '#irnr-registry-token-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:8abd0ca176bcee05de94d2783debf86c8ab811cc7af46ba820ebef306a58727c'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
---
# `irnr-registry-token-remediation` reference: `registry token authority path`

The audit followed the centralized domain-contract refactor through the opaque core token types, the governed fact catalogue, the compiled convenio projection, and adjacent Modelo 210 consumers.

## Summary

`TipoRentaIrnr`, `ConvenioOverrideKind`, and `M210PayerMode` are identity-only string types in `src/cadrumo/core/irnr.py`; core does not own their membership. `TipoRentaIrnr` membership and the official-code projection resolve from fact 0080 through `resolve_tipo_renta_irnr_catalogue` and `require_tipo_renta_irnr` in `src/cadrumo/domain/calculations/registry/irnr_tipo_renta.py`. `M210PayerMode` membership, default, and code-35 applicability resolve from the same governed fact through `resolve_m210_payer_mode` in `src/cadrumo/domain/transactions/m210_income_classification.py`.

`ConvenioOverrideKind` tokens come from the selected `irnr.convenio.override` fact through `resolve_convenio_override` in `src/cadrumo/domain/calculations/registry/convenio.py`. The resolved override owns the semantic predicates `is_exempt`, `has_flat_rate`, `has_ceiling_rate`, and `delegates_to_domestic_tariff`; the convenio row/projection boundary owns required-versus-forbidden rate validation. Tests must use those authority paths or compiled catalogue rows, never enum members, enum iteration, direct token construction, or a copied value-set fixture.

The refactor left two production inconsistencies: string-backed fact rates were refused instead of strictly projected to `Decimal`, and one unsupported-kind error referenced an undefined local name. The Art. 24.6 expense branch also compared a raw hard-coded income token; its semantic token must resolve from fact 0080 like the pension and real-estate branches.
