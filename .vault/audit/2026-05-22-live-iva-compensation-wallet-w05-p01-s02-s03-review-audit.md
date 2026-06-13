---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p01-s02-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p01-s03-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s01-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s02-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s03-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s04-exec]]'
---

# `live-iva-compensation-wallet` Code Review

W05-P01-S02-S03-CR-001 | PASS | No critical/high issues found

Reviewed the W05.P01.S02 and W05.P01.S03 repair attribution changes for safety,
privacy, and test quality. The likely-origin classifier uses namespace
classification, safe key-context metadata, and active-key digest confirmation
only. It does not decrypt payloads, reverse HMAC natural keys, or print profile
UUIDs. Replacement-evidence requirements are metadata-only constants and are
rendered in CLI text and JSON without taxpayer identifiers, filing identifiers,
wallet amounts, or natural secure-object keys.

The focused tests use real SQLite engines, real `SecureObjectRepository`, and
real `EphemeralMasterKeyProvider` key changes to produce unreadable rows. The
tests assert behavior through public CLI output for privacy-sensitive rendering
and through application reports for classification invariants. No mocks, fakes,
monkeypatches, skips, xfails, or mirrored business calculations were introduced.

Residual risk: the next step must still implement summarized attribution output
for large unreadable-row sets and the later remediation planner must consume the
replacement-evidence requirements before any quarantine path can be considered.

W05-P01-S04-CR-001 | PASS | Summary-first attribution preserves privacy and usability

Reviewed the W05.P01.S04 CLI change. Default attribution output now omits
per-row `unreadable_rows` from text and JSON, carries an explicit
`row_detail_mode`, and prints a `--details` hint. The summary still exposes the
replacement-evidence requirements required for preserve-first remediation.
The detail mode remains metadata-only and is covered by the public CLI privacy
contract for active profile UUIDs, taxpayer ids, period tokens, wallet payload
text, and private natural keys.

No critical/high issues found. Residual risk moves to W05.P02: the dry-run
remediation planner must consume these requirements before any quarantine or
rebuild outcome is presented.

W05-P02-S01-CR-001 | MEDIUM | Fixed during review: repair decision ids were only shape-validated

The initial W05.P02.S01 implementation required `decision_id` to be a lowercase
SHA-256-shaped string, but did not bind that id to the decision content. Because
the underlying secure-object store is an upsert store, a future caller could
have supplied a sha-shaped id unrelated to the target namespace, outcome, or
replacement-evidence requirements. That would weaken the audit trail for
preserve-first remediation decisions.

Mitigation applied in the same review loop: `decision_id` is now derived from
the decision content, including target namespace, target digest, outcome,
decision time, actor, reason, likely origin, replacement-evidence requirements,
and verified evidence references. The model rejects mismatched ids, and the
repair integrity suite now covers the rejection path through public model
construction.

W05-P02-S01-CR-002 | PASS | No critical/high issues found after mitigation

Reviewed the durable repair decision model and encrypted repository after the
content-bound id fix. The record still does not authorize mutation:
`mutation_authorized` is hard-typed to `False`, non-preserve outcomes require
replacement-evidence requirements, and saved rows use the AUDIT-class encrypted
secure-object repository namespace. Tests use real SQLite storage and real
`SecureObjectRepository` encryption; they verify encrypted roundtrip behavior,
decision-time listing, mutation refusal, non-preserve evidence requirements,
and content-bound ids without mocks, fakes, monkeypatches, skips, or xfails.

Residual risk: W05.P02.S02 must add the dry-run `aeat config repair plan`
surface, and W05.P02.S03 must prevent any quarantine/rebuild presentation unless
the required replacement evidence is explicitly present.

W05-P02-S02-CR-001 | PASS | Dry-run remediation planner is non-mutating and metadata-only

Reviewed `aeat config repair plan` for unsafe storage mutation, AEAT live
mutation, privacy leakage, and misleading authorization semantics. The command
builds its output from unreadable-row attribution only, reports
`planned_mutations=0`, and every namespace item carries `mutation_allowed=false`.
It does not call delete, quarantine, rebuild, repair-decision save, or any live
AEAT client. CLI output and JSON are metadata-only and reuse the same redacted
namespace classification and replacement-evidence requirements as attribution.

The public CLI test creates a real active profile and a real unreadable encrypted
wallet row, captures raw secure-object rows before and after the command, and
asserts the row set is unchanged. It also verifies that taxpayer ids, periods,
profile UUIDs, and payload text are absent from text and JSON output. No mocks,
fakes, monkeypatches, skips, xfails, or mirrored business calculations were
introduced.

No critical/high issues found. Residual risk moves to W05.P02.S03: quarantine
and rebuild outcomes still need explicit replacement-evidence gates before they
can appear as anything more than preserve-first planning guidance.

W05-P02-S03-CR-001 | PASS | Destructive remediation outcomes require verified evidence references

Reviewed the W05.P02.S03 decision-model hardening for premature quarantine,
unsafe rebuild, and misleading authorization. `RepairRemediationDecision` now
rejects `quarantine` and `rebuild` outcomes unless
`verified_replacement_evidence_refs` is present. This is stricter than
namespace-level replacement-evidence requirements: the requirements identify what
must exist, while the verified references record that the operator has named the
replacement evidence before destructive remediation can even be represented as a
decision. `export_required` remains available as the non-mutating evidence
collection state, and `mutation_authorized` remains hard-typed to `False`.

The regression constructs real Pydantic decisions through the public helper and
asserts that rebuild without verified evidence is rejected. The focused suite
also re-verifies encrypted decision storage, CLI privacy, and non-mutating
planner behavior. No mocks, fakes, monkeypatches, skips, xfails, or mirrored
business calculations were introduced.

No critical/high issues found. Residual risk moves to W05.P02.S04: critical
submission receipt and filing-history namespaces still need an explicit
engineer-override/ADR prohibition so destructive quarantine stays disabled even
when replacement evidence exists.

W05-P02-S04-CR-001 | PASS | Protected filing and submission namespaces cannot be quarantined

Reviewed the W05.P02.S04 classification and decision-model change for unsafe
destructive remediation. `RepairNamespaceClassification` now exposes
`destructive_quarantine_allowed` and `destructive_quarantine_policy`; critical
submission records, justificante receipt metadata, remote filed-declaration
evidence, local filing history, and unknown namespaces are marked as not
quarantineable without a later engineer override ADR. `RepairRemediationDecision`
rejects `quarantine` for those namespaces even when replacement-evidence
requirements and verified evidence references are present.

The dry-run planner surfaces the quarantine policy in text and JSON while still
reporting `planned_mutations=0` and per-item `mutation_allowed=false`. The
regression constructs a protected justificante quarantine decision with verified
evidence and verifies that model validation rejects it. The focused CLI/privacy
suite still verifies no row mutation and no taxpayer/profile/payload disclosure.
No mocks, fakes, monkeypatches, skips, xfails, or mirrored business calculations
were introduced.

No critical/high issues found. Residual risk moves to W05.P03: calculation and
export/readiness surfaces must consume degraded secure-object confidence and
block filing-grade outputs when affected evidence remains unreconciled.
