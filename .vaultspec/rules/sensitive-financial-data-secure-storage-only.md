# Sensitive financial data uses secure storage only

## Storage and transport

- Taxpayer, credential, banking, ledger, invoice, filing, and evidence payloads are stored only through the project's approved encrypted persistence boundary.
- Do not write sensitive payloads to source files, fixtures, logs, exceptions, command history, caches, plaintext databases, temporary files, generated references, vault documents, or agent transcripts.
- Persist evidence as encrypted bytes with integrity and provenance metadata. A filesystem path or remote URL is not a secure stored copy.
- Secrets come from the approved secret boundary and are never committed, echoed, serialized with domain data, or passed in command-line arguments when a safer channel exists.
- Off-host transfer requires the explicitly approved encrypted integration and the minimum necessary fields. Do not upload real financial data to search, AI, analytics, paste, or debugging services.

## Execution safety

- Tests use synthetic or irreversibly anonymized data. A production-shaped fixture must still contain no real identity or secret.
- Logs and user-visible diagnostics expose stable identifiers and remediation, not raw payloads. Redaction happens before serialization or transport.
- Local development and automated agents must never submit, amend, sign, or otherwise write a live AEAT filing. Live remote behavior is read-only unless the operator gives explicit transaction-specific authorization through the product's guarded workflow.
- Cleanup of decrypted material is fail-safe and verified. If a workflow cannot guarantee secure lifetime and disposal, it must refuse the operation.

Verification covers encryption at rest, redaction, temporary-material cleanup, secret handling, and refusal of unauthorized live writes.
