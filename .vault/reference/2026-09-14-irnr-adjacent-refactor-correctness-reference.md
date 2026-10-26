---
tags:
  - '#reference'
  - '#irnr-adjacent-refactor-correctness'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:bdf1e7b10e49836c4a594dde7a14a6bb786247b7ad3fe522e702c53fbbcdb8a5'
related:
  - "[[2026-09-14-irnr-registry-token-remediation-authority-path-reference]]"
---
# `irnr-adjacent-refactor-correctness` reference: `adjacent refactor authority and failure classification`

The continuity campaign reconstructed all forty recorded failures from the captured exploratory log before rerunning any selection. The failures belong to eight reporting clusters but six failure signatures.

## Summary

The seven detail-row membership failures include six calls that reach a committed no-op gate and one Modelo 349 rectification fixture blocked by an unscoped registry query. The three mirror failures are not mirror serialization defects: they fail while constructing the same rectification row. The six Modelo 210 grouping failures likewise reach `_registry_detail_catalogue`, whose `describe_modelo(..., as_of=...)` calls violate the current filing-year-scoped query contract. These are implementation regressions from incomplete registry-authority migration.

Row-kind ownership belongs in the existing dated `detail-m349-m210-catalogues` governed fact, not in a Python class-to-modelo map. It is distinct from `detail_bearing_modelos`: Modelo 210 annual grouping rows are evidence-only and do not make Modelo 210 a repeated-export-row modelo. Consumers resolve the row-kind owner from the governed fact at the work unit filing coordinate. Modelo 349 rectification periods resolve against `describe_modelo_for_scope` using the row's ejercicio and periodo, while Modelo 210 grouping validation receives an explicit filing-period coordinate from its work unit.

The two formula failures are stale tests following the canonical formula rename from `m210-tipo-gravamen-2025-resolve` to the revision-owned `m210-tipo-gravamen-resolve`. Compilation and unresolved outcomes already retain the selected formula's identity, so tests must derive it from the selected revision instead of maintaining another constant.

The four persistence failures are fixture drift at the secure profile boundary. `UserProfileRecord` now requires schema identity and authority context; creation must use `create_user_profile_record`, hydration must use `decode_user_profile_record`, and `ProfileRecordSession` must carry the matching decode context from one pinned authority generation. A context-free constructor or session default would bypass the accepted security contract.

All sixteen convenio application failures occur before convenio behavior because the fixture retained deleted `IVARegime.GENERAL` member access. `IVARegime` is an opaque token whose membership and default come from fact 0098 through `default_iva_regime` and `resolve_iva_regime_catalogue`. This is stale test data, not a convenio runtime regression.

The currency failure compares two different fact identities: the M347 consumer resolves the authored `m347-counterparty-declaration-threshold` fact with canonical unit `eur`, while the development probe retained a retired generated declaration projection whose unit was `EUR`. The probe must address the authored fact directly; normalizing or copying the returned scalar would conceal the authority mismatch.

The deadline failure is a stale expected fixture. The active 2025 Modelo 210 revision owns a type-02 window opening on 2026-04-01, as corrected and grounded in its deadline declaration; the 2026 successor opens on 2027-04-01. Revision selection is already correct and application logic must not replace the registry date.

Every failure was exposed by the adjacent centralization sequence rather than introduced by the completed IRNR token remediation. The remediation order is: restore explicit scoped row authority; migrate secure-profile fixtures and opaque IVA test tokens; reconcile formula/probe/deadline identities; then validate the combined recorded selection and original IRNR gates.
