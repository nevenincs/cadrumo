# Redaction, bundled resources, and time contracts

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-122` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 9 core modules totaling 2,208 physical lines. I read all six assigned pages, including the complete redaction engine, bundled-resource resolver, and shared time contracts. This is static inspection only; no resource package was installed or executed, and no current legal/authority material was verified.

## Redaction and bundled resources

The redaction API has separate flat-string, structured-data, log/error, and public-CLI profiles. Its rules cover Spanish NIF/NIE/CIF and prefixed NIF-IVA, IBANs, URLs, JWT and opaque bearer tokens. Identity/IBAN matches use checksums or authority-backed structural gates where shape alone collides with ordinary text; a process-scoped identity-admission binding lets the host supply those authority tables without pulling domain registries into core. When the gate is missing or cannot answer, the fallback admits on lexical shape, choosing possible over-redaction over a missed identity. Gated scans re-read shorter token-bounded candidates after a refusal so a neighboring word does not consume an identity; timestamps and UUIDs are protected from patterns that could corrupt them. Redaction rule catalogue (`src/cadrumo/core/redaction/rules.py`) Authority admission binding (`src/cadrumo/core/redaction/tax_identity_admission.py`) Refusal-and-re-read scan (`src/cadrumo/core/redaction/rules.py`)

`redact_structured` returns fresh dict/list/tuple structures and applies rules to string values and string keys, preserving collisions with suffixed keys rather than silently overwriting entries. CLI redaction adds key-aware placeholders for profile IDs, bucket IDs, and object keys, with an explicit reveal option limited to profile/bucket identifiers; it continues to redact tax identities, URLs, tokens, and object keys. Sensitive-name classification folds camel case, acronyms, punctuation, and case before matching shared credential/identity terms. Unknown rule names fail closed instead of silently dropping a policy arm. Structured recursive redaction (`src/cadrumo/core/redaction/rules.py`) CLI output profile (`src/cadrumo/core/redaction/rules.py`) Sensitive-key matching (`src/cadrumo/core/redaction/rules.py`) Unknown-rule refusal (`src/cadrumo/core/redaction/rules.py`)

These outputs are pseudonymized, not anonymized. Tax identities use deterministic SHA-256 prefixes containing only eight hex digits, which keeps stable correlation but permits dictionary guessing over a constrained identity space. The long-lived CLI redaction cache also retains each short input string in plaintext alongside its redacted result: it is bounded to 16,384 strings of up to 512 characters, but persists until eviction or process exit. That is a memory-residency consideration for TUI/MCP hosts and crash dumps. Hash-prefix output (`src/cadrumo/core/redaction/rules.py`) Plaintext CLI string cache (`src/cadrumo/core/redaction/rules.py`)

`bundled_data` abstracts package resources as `Traversable` values, can materialize a scoped path or process-lifetime path, and resolves corpus PDFs/spreadsheets from either the command package or the companion `cadrumo_data` namespace. It enumerates every companion namespace portion and resolves copies by logical `_data`-relative location, avoiding assumptions that neighboring files live beside one another when packaging splits by suffix. Missing companion binaries return `None` at this low-level seam for the catalog-integrity layer to adjudicate. These APIs expect code-authored relative segments; this module does not validate arbitrary caller-supplied path components. Package resource API (`src/cadrumo/core/resources/bundled_data.py`) Companion binary resolution (`src/cadrumo/core/resources/bundled_data.py`) Primary/companion corpus resolution (`src/cadrumo/core/resources/bundled_data.py`) Logical-root copy lookup (`src/cadrumo/core/resources/bundled_data.py`)

## Time contracts and assessment

The time package supplies UTC-aware validation, explicit coercion for sources that truly provide naive timestamps, an opt-in ContextVar frozen clock, Madrid civil-date calculation, and inclusive date-range validation. The frozen clock rejects naive/non-UTC instants and refuses to activate under the live-test opt-in. These are strong shared boundaries, though the module's statements about statutory/AEAT time authority are code documentation rather than independently validated legal findings. UTC validation (`src/cadrumo/core/time/utc.py`) Madrid civil date (`src/cadrumo/core/time/clock.py`) Scoped frozen clock (`src/cadrumo/core/time/clock.py`) Inclusive date range (`src/cadrumo/core/time/date_range.py`)

The strongest implementation controls are fail-closed rule resolution, checksum-backed redaction gates with conservative fallbacks, nested structured scrubbing, and multi-source package-resource resolution. Prioritized follow-up is to assess plaintext cache residency and test redaction against ordinary identifiers/document references and output-format invariants. No tests are in the assigned files, so runtime coverage remains unverified.

## Complete assigned-file coverage

- redaction/__init__.py (`src/cadrumo/core/redaction/__init__.py`) — lines 1–61
- redaction/rules.py (`src/cadrumo/core/redaction/rules.py`) — lines 1–1,438
- redaction/tax_identity_admission.py (`src/cadrumo/core/redaction/tax_identity_admission.py`) — lines 1–72
- resources/__init__.py (`src/cadrumo/core/resources/__init__.py`) — lines 1–10
- resources/bundled_data.py (`src/cadrumo/core/resources/bundled_data.py`) — lines 1–288
- time/__init__.py (`src/cadrumo/core/time/__init__.py`) — lines 1–26
- time/clock.py (`src/cadrumo/core/time/clock.py`) — lines 1–139
- time/date_range.py (`src/cadrumo/core/time/date_range.py`) — lines 1–71
- time/utc.py (`src/cadrumo/core/time/utc.py`) — lines 1–103
<!-- /preserved:article -->
