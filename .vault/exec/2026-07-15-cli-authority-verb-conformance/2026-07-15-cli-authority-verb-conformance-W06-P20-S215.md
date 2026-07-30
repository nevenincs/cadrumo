---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S215'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Confirm certificate custody, ledger evidence, portable export, hashing, namespaces, filed capture, LLM review, registry projection, and duplication execution each have one canonical owner and no parallel writer, resolver, parser, or command path

## Scope

- `src/cadrumo/`
- `dev/audit/`

## Description

- Re-measure at HEAD rather than inheriting an earlier inventory, then confirm each of the nine consolidated clusters has exactly one canonical owner and no parallel writer, resolver, parser, or command path, applying the substitutability pre-filter before flagging any site.
- Run the three clusters that carry an explicit structural single-ownership gate: the hashing-adoption AST recurrence gate, the non-vacuous namespace-registry adoption gate, and the truthful duplication-runner/health-report gate.
- Name the canonical owner per cluster by exact search, and confirm no second authority survives.

## Outcome

Verified at HEAD `6868f4f824e1e037753f98089499b3bbcaf527a3`.

Corpus: 1411 production and 3744 total `.py` files under `src/cadrumo`, plus 17 under `dev/audit`.

Structural single-ownership gates: `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/core/tests/test_hashing_adoption.py src/cadrumo/application/tests/test_namespace_registry_adoption.py src/cadrumo/tests/test_dev_audit_report.py` — `18 passed in 195.20s`.

Canonical owner per cluster, confirmed sole authority at HEAD:

- certificate custody: `SecureStorageCertificateSecretBackend` in `application/auth/_certificate_secret_backend.py`, the sole concrete implementation of the `CertificateSecretBackend` port; the certificate keyring backend, selector, and factory are deleted (proven by the backend suite's post-cutover surface assertions), master-key OS-keyring custody left independent.
- ledger evidence: the atomic invoice-only linkage writer plus `attach_manual_transaction_evidence` in `application/ledger/_actions_manual.py`; the generic manual-field update refuses every evidence field, so evidence mutation has one door.
- portable export: `application/user_profile/_bundle_export.py`, the sole durable export orchestration service; both portable-transfer and subject-access purposes route through it.
- hashing: `core/hashing.py` (`sha256_hex` / `hash_file`); the AST recurrence gate refuses any new reducible one-shot SHA-256 body.
- namespaces: `adapters/persistence/storage/_namespace_registry.py`; the adoption gate (re-floored under S278) proves every production namespace literal is registry-declared.
- filed capture: `application/live/_filed_observation_persistence.py`, the sole owner of latest-record selection, history ordering, and calculation-observation writes.
- LLM review: `application/ledger/_llm_review_workflow.py`, the one typed review workflow; CLI-owned review branching was removed.
- registry projection: `domain/calculations/registry/_queries.py`; the relation-prefill resolver `resolve_relations_from_local_store` is shared by the pull and calculate paths (one aggregation path).
- duplication execution: `dev/audit/duplication.py`, the sole platform-neutral jscpd runner consumed by the health report.

## Notes

Substitutability pre-filter applied: no site in these nine clusters is a promotable parallel authority. The four cross-cutting duplicates the swarm (S204) surfaced — the M100 casilla accessor, the evidence-covers-snapshot copy, the FTS or-group builder, and the filing export-field overlap predicate — sit OUTSIDE these nine clusters and are being retired by a peer under S288-S291; the journal-repository substrate extraction is constraint-shape divergent (extraction, not replacement) and still in flight, so its picture may move. Those are tracked separately and do not reopen the nine consolidated clusters. Corpus is quoted rather than only the result, because a zero-finding sweep over the wrong corpus is the cheapest dishonest close; the owners here were named by exact search over the stated corpus and the three gate-backed clusters carry a passing structural gate.
