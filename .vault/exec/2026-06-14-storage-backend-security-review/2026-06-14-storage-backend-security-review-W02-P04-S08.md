---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S08'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Verify the stored payload hash and recomputed revision id on every secure-object read and fail closed on mismatch and ## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the stored payload hash and recomputed revision id on every secure-object read and fail closed on mismatch

## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Re-assess S08 against the landed H3 (S07) AEAD row-identity binding and its
  proof (S09).
- Map the candidate read-time checks: payload-hash-vs-payload, ciphertext-hash-vs-wire,
  and revision-id self-consistency (`derive_revision_id` over stored columns).
- Confirm `probe_namespace_integrity` only checks decryptability (AEAD), never the
  revision-id chain — so the chain has never been read-verified.

## Outcome

PRIMARY OBJECTIVE MET BY H3; RESIDUAL DEFERRED (hazard-laden).

The security objective of S08 — a read that fails closed on payload tampering or
row substitution — is **delivered by H3/S07**: the payload AEAD binds
`(namespace, object_key_digest, schema_version)` into the associated data, so a
tampered or swapped ciphertext fails decryption on every read path
(`_record_from_row`, `iter_records_with_failures`, `probe_namespace_integrity`).
`test_secure_object_row_substitution_fails_closed` (S09) proves it. This is the
core read-time integrity the step exists to guarantee.

The literal residual — recompute the stored **payload_hash** and **revision_id**
and fail closed on mismatch — is the approach that was tried and reverted earlier
in this campaign, and re-assessment confirms each variant carries a real hazard
that outweighs the marginal defence-in-depth over a medium finding:

- A **revision_id self-consistency** recompute (`derive_revision_id` over the
  stored lineage columns) is the only payload-independent variant (so it would not
  fire on the 14 reconciled anti-tautology corruption suites), but it depends on
  `written_at.isoformat()` round-trip fidelity. That chain has **never been
  read-verified** (`probe_namespace_integrity` only checks AEAD decryptability), so
  a lossy SQLite datetime round-trip would fail-close **valid** rows — denying a
  user access to their own data, a regression worse than the column-tamper threat
  it mitigates. Adding it safely requires an explicit round-trip-fidelity proof
  first.
- A **payload_hash-vs-decrypted-payload** or **ciphertext_hash-vs-wire** check
  fires on every anti-tautology corruption test (they re-encrypt a mutated payload
  without re-stamping the hash columns), pre-empting the domain model_validator
  assertions those tests exist to prove. Adding it requires re-stamping integrity
  metadata across all 14 suites — co-design with that contract.

The plaintext lineage columns (`revision_id`, `payload_hash`, `ciphertext_hash`,
`previous_*`) remain outside the AEAD; binding the **pre-encrypt** subset
(`payload_hash`, `previous_payload_hash`, `previous_revision_id`) into the H3 AAD
is the canonical, corruption-test-safe mechanism for that residual and is the
recommended follow-up shape (the post-encrypt `ciphertext_hash`/`revision_id`
cannot enter the AAD — chicken-and-egg — and are already covered for ciphertext
tamper by the GCM tag).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Deferred deliberately. "Data security, persistence, and storage correctness are
absolute keys" cuts both ways: a fail-closed read-gate that false-positives on
valid data is itself a severe correctness regression, so the round-trip-fidelity
proof is a precondition, not an afterthought. The step stays unchecked; the
primary read-integrity guarantee is already green via S07/S09.
