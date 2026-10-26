---
tags:
  - '#reference'
  - '#iva-compensation-history'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:7189178ed9662185d4bc05e320f8798f3ed9c9a880bacf57d9c3355d4b28a4e0'
related:
  - "[[2026-09-12-modelo-history-dependency-inversion-reference]]"
---

# `iva-compensation-history` reference: `dependency inversion`

## Summary

`src/cadrumo/application/calculations/iva_compensation_history.py` owns the
Modelo 303 history policy, state derivation, and carry-forward projections. It
now depends on the focused
`src/cadrumo/application/calculations/iva_compensation_history_ports.py`
capability, whose required operations are period load/save/list, atomic secure
write preparation, and same-store identity for observation co-commit.

The encrypted implementation lives in
`src/cadrumo/adapters/persistence/profile/iva_compensation_history.py`. That
adapter binds `SecureBoundRepository` and the registered IVA-history namespace,
then translates storage failures into the application-owned
`IvaCompensationHistoryPersistenceError`. The application module no longer
imports storage path-safety, namespace, or repository implementation details.

The shared outer composition binds one history adapter to each calculation,
filing, and IVA-wallet-seed port bundle in
`src/cadrumo/entrypoints/adapter_composition.py`. The live-state composition
and wallet CLI bind the same adapter against their already-selected secure
backend. Calculation previous-filing resolution, local filing observation
co-emission, wallet seed/correction/balance, and live wallet reconciliation all
receive the capability explicitly; no application caller constructs a default
repository.

The boundary preserves one-store atomicity by checking the supplied history
capability against the observation repository's secure backend before a filed
observation/history co-commit. Adapter DTOs and storage exception classes stop
at the outer adapter boundary.
