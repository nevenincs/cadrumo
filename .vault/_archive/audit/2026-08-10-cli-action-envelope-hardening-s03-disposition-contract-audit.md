---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:fa8a72cbaa08d50c1fe800cb44727c10180b57118510930a2b7aa1a34008c1a4'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S03 disposition contract review`

## Scope

Formal review of W01.P01.S03's disposition representation and real-census
tests. The review covered direct reuse of S01 identity, strict and versioned
TOML parsing, deterministic diagnostics, exact-one reconciliation, exclusion
grounding, default-ledger failure behavior, absence of count gates, and whether
tests exercise production behavior without mirroring census logic.

## Findings

### s03-disposition-contract | medium | Persisted-contract failure modes lack regression tests

The implementation fails closed for the reviewed cases, but the six-test suite
does not pin several load-bearing behaviors of the persisted disposition
contract. There is no test for unsupported schema versions or unrecognized
top-level, metadata, and row fields; deterministic aggregation and ordering of
multiple diagnostics; a duplicate emitted by the census input; a mismatched
exclusion symbol; exclusion grounding on a non-excluded row; or the missing
default ledger and command-line failure path. These are precisely the drift and
operator-diagnostic behaviors that make the ledger safe to check in. Direct
malformed and coverage probes confirmed the current implementation behaves
correctly, but those probes are not durable regression protection.

Resolution: closed on re-review. Production-importing tests now reject an
unsupported schema version and unknown fields at the top, metadata, and row
scopes; prove stable sorted aggregate diagnostics across repeated loads; reject
duplicate census input; reject a wrong exclusion symbol and grounding attached
to a non-excluded row; and prove both the checked-in loader and CLI entry point
fail closed for a missing ledger. The assertions name semantic failure classes
and identities without pinning the current census count or reproducing census
logic.

No implementation defect was found in the reviewed contract. `CandidateKey`
copies all five S01 identity fields directly from `CandidateRecord`; validation
rejects missing, duplicate, stale, and duplicate-census identities without an
exact-count gate; exclusions bind both the candidate alias and enclosing
symbol; TOML fields and schema version are closed; and diagnostics are deduped
and sorted deterministically. The absent default ledger fails closed and is
consistent with the module's explicit statement that the next campaign step
populates it.

Validation evidence: Ruff format check reported both files already formatted;
all six targeted real-census tests passed; Ruff passed; basedpyright reported
zero errors, warnings, or notes. A direct HEAD probe reconciled 1,265 real
candidates to 1,265 unique dispositions, solely as an observed diagnostic and
not a count gate. Removing one row produced its exact missing identity,
duplicating one produced its exact duplicate identity, and replacing one key
produced both stale and missing identities. A malformed TOML probe reported the
unsupported version, unknown fields at all three levels, invalid role, and
missing fields in deterministic sorted order. The missing default file produced
one explicit read failure.

Remediation validation: all nine targeted real-census tests passed. Ruff format
check reported both files already formatted, Ruff passed, and basedpyright
reported zero errors, warnings, or notes. No S03 findings remain open.

## Recommendations

Add focused production-importing tests for the omitted strict-schema,
diagnostic-order, duplicate-census, exclusion-shape, and default-ledger/CLI
failure cases. Assert semantic identities and diagnostic categories rather than
today's census total, and continue using the real S01 census rather than a
mirrored scanner or candidate model.

This recommendation is implemented and verified.
