---
name: sensitive-financial-data-secure-storage-only
trigger: always_on
---

# Sensitive financial data uses secure storage only

## Storage and transport

- Private taxpayer, credential, banking, ledger, invoice, filing and associated evidence payloads are stored only through the project's approved encrypted persistence boundary.
- Public AEAT/BOE publications, public registry definitions and synthetic fixtures are not private taxpayer evidence merely because they concern taxation. They may use the repository's canonical source/corpus storage. Check content for embedded private data; never use this distinction to reclassify a real filing or secret as public.
- Do not write sensitive payloads to source files, fixtures, logs, exceptions, command history, caches, plaintext databases, temporary files, generated references, vault documents, or agent transcripts.
- Persist private evidence as encrypted bytes with integrity and provenance metadata. A filesystem path or remote URL is not a secure stored copy.
- Secrets come from the approved secret boundary and are never committed, echoed, serialized with domain data, or passed in command-line arguments when a safer channel exists.
- Off-host transfer requires the explicitly approved encrypted integration and the minimum necessary fields. Do not upload real financial data to search, AI, analytics, paste, or debugging services.

## Execution safety

- Tests use synthetic or irreversibly anonymized data. A production-shaped fixture must still contain no real identity or secret.
- Logs and user-visible diagnostics expose stable identifiers and remediation, not raw payloads. Redaction happens before serialization or transport.
- Local registry source replacement and authority publication are not AEAT filing submissions. They require the authorization and verification for their own workflow. Writing or signing a real remote filing requires explicit transaction-specific authorization through the product's guarded workflow; ordinary development authorization does not permit it.
- Cleanup of decrypted material is fail-safe and verified. If a workflow cannot guarantee secure lifetime and disposal, it must refuse the operation.

Verification covers encryption at rest, redaction, temporary-material cleanup, secret handling, and refusal of unauthorized live writes.
