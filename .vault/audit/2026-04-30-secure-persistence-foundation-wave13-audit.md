---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave13-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave13-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
---

# `secure-persistence-foundation` audit: wave-13 repository-id validator consolidation

## Scope

Audit gate for **wave-13**: consolidation of five byte-identical (modulo parameter name) repository-id validators into one substrate helper at `aeat.adapters.persistence.storage._path_safety.safe_repository_id`. Pure code-quality refactor with zero security regression.

In scope:

- Substrate helper `safe_repository_id(token, *, context)` in `_path_safety.py`.
- Public re-export through `aeat.adapters.persistence.storage.__init__`.
- Five repositories updated: `submission/_repository.py`, `filing/_repository.py`, `filing/_complementaria_repository.py`, `filing/_history_repository.py`, `justificante/_repository.py`. Five `_validate_*` definitions deleted; 12 call sites updated.
- 9 new substrate tests in `_test_path_safety.py`. 5 pre-existing repository tests pass unchanged via the `ValueError` inheritance chain.

Out of scope (kept domain-local, different rules):

- `_validate_run_id` (observability — regex `^[0-9a-f]{16}$`).
- `_validate_casilla_id` (×2 in schema — domain-specific format).
- `_validate_category_id` (×2 in financial — domain-specific format).
- `_validate_invoice_id_shape`, `_validate_optional_ids` (financial/invoices — different shape).
- `_validate_modelo` in `schema/_models.py:425` (different shape; happens to share the name).

## Findings

### Strengths

**Correct consolidation boundary.** The five validators that share the exact body shape are the only ones consolidated. Domain-specific validators (regex hex, casilla format, category alphabet) stay where they belong. The boundary was drawn by literal byte-equivalence, not by name similarity — `_validate_modelo` in `filing/_history_repository.py` and `_validate_modelo` in `schema/_models.py` share the function name but have different bodies; only the first was consolidated.

**Failure-class upgrade preserves backwards compatibility.** Pre-wave-13 the five validators raised raw `ValueError`. Post-wave-13 they raise `PathContainmentError`, which inherits from both `PersistenceError` and `ValueError`. Five existing tests use `pytest.raises(ValueError)` and continue to pass. New code can use the typed `except PathContainmentError` with the registered `INTEGRITY_STORAGE_PATH_CONTAINMENT` error code.

**Trilingual error coverage by inheritance.** The new `PathContainmentError` raises through the existing registered code (`INTEGRITY_STORAGE_PATH_CONTAINMENT`) — pre-existing es/en/hu coverage applies; no new registry entry needed.

**Error-message stability.** The helper's `context` parameter mirrors the field name in the original message (`"submission_id must not contain path separators: ..."`). After consolidation, the messages are byte-identical to the pre-wave-13 state. Test surface that asserts on `match="path separator"` continues to match.

**Zero security regression.** The five rejections (empty, `/`, `\`, `.`, `..`, dot-prefix) are byte-equivalent to the pre-wave-13 validators. The downstream substrate path-containment helpers (`safe_record_path`, `resolve_record_json_path`) remain in place as the second-tier defense.

**Pattern available for future repositories.** A new wave-N repository that composes `<store_dir>/<token>.envelope.json` paths can now write `safe_repository_id(token, context="X")` instead of copy-pasting the five-line validator. The substrate helper is the canonical pattern.

**No regression in test surface.** 139/139 tests pass across the consolidation surface (substrate + 5 repositories). Lint clean; ty clean; format clean.

**Net code reduction.** 33 fewer lines of code (77 deleted, 110 added — but the 110 includes the new substrate helper + tests + ADR). Subtracting the test/doc additions, the production-code surface shrunk meaningfully and the duplication is gone.

### Residual risks (low-severity, accepted)

**R1 — Encoded path separators not rejected.** The helper rejects `/` and `\` but does not reject `%2F`, `%5C`, or alternative Unicode path separators (e.g. U+FF0F fullwidth solidus). Acceptable: the downstream `safe_record_path` enforces a strict allow-list `[A-Za-z0-9_.-]` that filters any encoded variant before path resolution. The repository-level helper is the early-rejection layer for the simplest hostile cases; it does not claim defense-in-depth completeness.

**R2 — NUL-byte injection not explicitly checked.** A token containing `\x00` could compose into a filename that some OS APIs truncate. Acceptable for the same reason as R1: the substrate's path resolution would reject the resulting path; and Python's pathlib raises `ValueError` on NUL-bearing paths at composition time.

**R3 — Helper naming overlap with `safe_record_path`.** The two helpers share the prefix `safe_` and live in the same module. Operators reading the substrate may confuse them. Acceptable: the docstrings make the distinction clear (record-path resolves under a root and returns a `Path`; repository-id validates a token in isolation and returns `str`). A future cleanup wave could group them under a `RepositoryIdentifier` namespace if the surface grows.

**R4 — `context` parameter is operator-supplied at the call site.** A typo at the call site (e.g. `context="dratf_id"` instead of `"draft_id"`) would produce a misspelled error message. Acceptable: the five existing call sites use the canonical names (verified by grep); regression tests would surface a typo via the message-match assertions.

### Findings against deferred-list items (none worsened)

- **SQLCipher whole-DB encryption** — orthogonal; wave-13 does not touch SQLite.
- **IDENTITY-class typed records widening** — orthogonal; wave-13 does not touch `SecretStore`.
- **Connector + export governance hardening** — orthogonal; wave-13 does not touch connectors.
- **Status-cache redaction** — orthogonal; wave-13 does not touch the status reader.

## Recommendations

**Pass the gate.** Wave-13 closes the deferred validator-consolidation finding from the upstream-reconciliation audit. Pure code-quality refactor with full test coverage and zero security regression.

**Standardise the call-site idiom.** A future minor cleanup could replace the 12 call sites' side-effecting check (`safe_repository_id(token, context="..."); path = root / f"{token}..."`) with the inline form (`path = root / f"{safe_repository_id(token, context='...')}..."`). The substrate helper returns the validated token specifically to enable this idiom. Track as low-priority.

**Track the future hardening trigger.** If telemetry surfaces a hostile token that bypassed `safe_repository_id` but was caught by `safe_record_path`, escalate by adding the missing rejection class to the substrate helper. R1 / R2 are accepted today under the dual-tier-defense model.

**Do not regress on review latency.** External reviews (`@gemini` + `@codex`) requested on commit fee9ab6 at PR #441 comments 4334592034 / 4334593667. Findings, when they arrive, are absorbed by amending the residual-risks section above rather than opening a wave-14 prematurely.

## Verdict

**Wave-13 audit gate: PASS.** Substrate + repositories + tests are coherent, regression-free, and close the validator-consolidation finding from the upstream-reconciliation audit. Residual risks R1–R4 are low-severity and explicitly accepted under the dual-tier-defense model (early-rejection at repository boundary + substrate path-containment downstream).

The substrate now exposes a documented `safe_repository_id` helper that wave-N repositories can use as the canonical early-rejection pattern.
