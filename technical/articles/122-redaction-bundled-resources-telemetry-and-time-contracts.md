# Redaction, bundled resources, telemetry, and time contracts

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-122` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 17 core modules totaling 2,958 physical lines, 125,522 bytes, and 29,345 measured `o200k_base` proxy tokens. I read all six assigned pages, including the complete redaction engine, bundled-resource resolver, telemetry gate/schema/HTTP sink, and shared time contracts. This is static inspection only; nothing was transmitted, no resource package was installed or executed, and no current legal/authority material was verified.

## Redaction and bundled resources

The redaction API has separate flat-string, structured-data, log/error, and public-CLI profiles. Its rules cover Spanish NIF/NIE/CIF and prefixed NIF-IVA, IBANs, URLs, JWT and opaque bearer tokens. Identity/IBAN matches use checksums or authority-backed structural gates where shape alone collides with ordinary text; a process-scoped identity-admission binding lets the host supply those authority tables without pulling domain registries into core. When the gate is missing or cannot answer, the fallback admits on lexical shape, choosing possible over-redaction over a missed identity. Gated scans re-read shorter token-bounded candidates after a refusal so a neighboring word does not consume an identity; timestamps and UUIDs are protected from patterns that could corrupt them. Redaction rule catalogue (`src/cadrumo/core/redaction/rules.py`) Authority admission binding (`src/cadrumo/core/redaction/tax_identity_admission.py`) Refusal-and-re-read scan (`src/cadrumo/core/redaction/rules.py`)

`redact_structured` returns fresh dict/list/tuple structures and applies rules to string values and string keys, preserving collisions with suffixed keys rather than silently overwriting entries. CLI redaction adds key-aware placeholders for profile IDs, bucket IDs, and object keys, with an explicit reveal option limited to profile/bucket identifiers; it continues to redact tax identities, URLs, tokens, and object keys. Sensitive-name classification folds camel case, acronyms, punctuation, and case before matching shared credential/identity terms. Unknown rule names fail closed instead of silently dropping a policy arm. Structured recursive redaction (`src/cadrumo/core/redaction/rules.py`) CLI output profile (`src/cadrumo/core/redaction/rules.py`) Sensitive-key matching (`src/cadrumo/core/redaction/rules.py`) Unknown-rule refusal (`src/cadrumo/core/redaction/rules.py`)

These outputs are pseudonymized, not anonymized. Tax identities use deterministic SHA-256 prefixes containing only eight hex digits, which keeps stable correlation but permits dictionary guessing over a constrained identity space. The long-lived CLI redaction cache also retains each short input string in plaintext alongside its redacted result: it is bounded to 16,384 strings of up to 512 characters, but persists until eviction or process exit. That is a memory-residency consideration for TUI/MCP hosts and crash dumps. Hash-prefix output (`src/cadrumo/core/redaction/rules.py`) Plaintext CLI string cache (`src/cadrumo/core/redaction/rules.py`)

`bundled_data` abstracts package resources as `Traversable` values, can materialize a scoped path or process-lifetime path, and resolves corpus PDFs/spreadsheets from either the command package or the companion `cadrumo_data` namespace. It enumerates every companion namespace portion and resolves copies by logical `_data`-relative location, avoiding assumptions that neighboring files live beside one another when packaging splits by suffix. Missing companion binaries return `None` at this low-level seam for the catalog-integrity layer to adjudicate. These APIs expect code-authored relative segments; this module does not validate arbitrary caller-supplied path components. Package resource API (`src/cadrumo/core/resources/bundled_data.py`) Companion binary resolution (`src/cadrumo/core/resources/bundled_data.py`) Primary/companion corpus resolution (`src/cadrumo/core/resources/bundled_data.py`) Logical-root copy lookup (`src/cadrumo/core/resources/bundled_data.py`)

## Optional telemetry

Remote telemetry is default-off and opt-in at several independent layers. Emission requires gestor mode off, deployment opt-in on, a non-`OFF` tier, and acknowledgment for that invocation. The dispatcher defaults to a no-op sink; a real HTTP sink must be explicitly constructed, and a missing endpoint remains inert. It POSTs only the typed payload with a short timeout and swallows HTTP transport errors without logging payload contents. Four-way consent gate (`src/cadrumo/core/telemetry/consent.py`) No-op default and dispatch (`src/cadrumo/core/telemetry/emit.py`) HTTP sink (`src/cadrumo/core/telemetry/http_sink.py`)

The payload schema has a closed metric registry and strict frozen model with counters, timings, success, error-kind, timestamp, command, and a workspace hash. Unknown metric keys are refused; registered keys marked non-remote are dropped. The workspace hash is a deterministic SHA-256 of the resolved local storage-root path, without reading profile files. Payload allowlist model (`src/cadrumo/core/telemetry/schema.py`) Metric allowlisting (`src/cadrumo/core/telemetry/schema.py`) Workspace identifier (`src/cadrumo/core/telemetry/workspace.py`)

Two local contract gaps weaken that privacy story. First, `CRASH_ONLY` promises to exclude timing data, but the consent gate treats every tier other than `OFF` identically and the payload builder/dispatcher apply no tier-based timing filter. The current registry marks the `diagnostics.llm_run` duration as remotely allowed, so a caller can pass it under `CRASH_ONLY` and have it sent if the other consent checks pass. No production caller is in this chunk, so call-site reachability remains to be checked; the tier policy itself is not enforced here. Crash-only tier promise (`src/cadrumo/core/telemetry/tier.py`) Gate only distinguishes OFF (`src/cadrumo/core/telemetry/consent.py`) Duration is remotely allowed (`src/cadrumo/core/telemetry/schema.py`)

Second, `error_kind` is described as a short closed label but is only constrained to `str | None` with a 64-character maximum; no enum or pattern allowlist enforces the closed-label claim. `build_telemetry_payload` passes it straight into the payload. A careless producer could therefore put an identifier, path, or other user data in the only free-text-like field and transmit it after the consent gate. The `command` field is also an unconstrained non-empty string, and unknown commands with no counters/timings are allowed by the builder; callers should be audited for stable code-authored values. Unrestricted error-kind field (`src/cadrumo/core/telemetry/schema.py`) Payload builder (`src/cadrumo/core/telemetry/schema.py`) Unknown-command empty-metric behavior (`src/cadrumo/core/telemetry/schema.py`)

The workspace hash is stable and unsalted. Although it does not read profile data, a conventional local storage path may have low enough entropy to guess and hash, and the stable value enables cross-run linkage. It is pseudonymous rather than demonstrably non-identifying. The HTTP sink also does not impose an HTTPS scheme itself; whether the Settings/configuration boundary enforces transport security is outside this chunk. Path-derived workspace hash (`src/cadrumo/core/telemetry/workspace.py`) Endpoint POST (`src/cadrumo/core/telemetry/http_sink.py`)

## Time contracts and assessment

The time package supplies UTC-aware validation, explicit coercion for sources that truly provide naive timestamps, an opt-in ContextVar frozen clock, Madrid civil-date calculation, and inclusive date-range validation. The frozen clock rejects naive/non-UTC instants and refuses to activate under the live-test opt-in. These are strong shared boundaries, though the module's statements about statutory/AEAT time authority are code documentation rather than independently validated legal findings. UTC validation (`src/cadrumo/core/time/utc.py`) Madrid civil date (`src/cadrumo/core/time/clock.py`) Scoped frozen clock (`src/cadrumo/core/time/clock.py`) Inclusive date range (`src/cadrumo/core/time/date_range.py`)

The strongest implementation controls are fail-closed rule resolution, checksum-backed redaction gates with conservative fallbacks, nested structured scrubbing, multi-source package-resource resolution, and an explicit default-no-op remote telemetry architecture. Prioritized follow-up is to enforce tier semantics at payload construction/dispatch, make `error_kind` a closed schema value and `command` registry-bound, confirm HTTPS policy, assess workspace-hash linkability and plaintext cache residency, and test redaction against ordinary identifiers/document references and output-format invariants. No tests or telemetry call sites are in the assigned files, so runtime coverage and actual remote-transmission reachability remain unverified.

## Complete assigned-file coverage

- redaction/__init__.py (`src/cadrumo/core/redaction/__init__.py`) — lines 1–61
- redaction/rules.py (`src/cadrumo/core/redaction/rules.py`) — lines 1–1,438
- redaction/tax_identity_admission.py (`src/cadrumo/core/redaction/tax_identity_admission.py`) — lines 1–72
- resources/__init__.py (`src/cadrumo/core/resources/__init__.py`) — lines 1–10
- resources/bundled_data.py (`src/cadrumo/core/resources/bundled_data.py`) — lines 1–288
- telemetry/__init__.py (`src/cadrumo/core/telemetry/__init__.py`) — lines 1–43
- telemetry/consent.py (`src/cadrumo/core/telemetry/consent.py`) — lines 1–65
- telemetry/emit.py (`src/cadrumo/core/telemetry/emit.py`) — lines 1–94
- telemetry/errors.py (`src/cadrumo/core/telemetry/errors.py`) — lines 1–35
- telemetry/http_sink.py (`src/cadrumo/core/telemetry/http_sink.py`) — lines 1–135
- telemetry/schema.py (`src/cadrumo/core/telemetry/schema.py`) — lines 1–292
- telemetry/tier.py (`src/cadrumo/core/telemetry/tier.py`) — lines 1–43
- telemetry/workspace.py (`src/cadrumo/core/telemetry/workspace.py`) — lines 1–43
- time/__init__.py (`src/cadrumo/core/time/__init__.py`) — lines 1–26
- time/clock.py (`src/cadrumo/core/time/clock.py`) — lines 1–139
- time/date_range.py (`src/cadrumo/core/time/date_range.py`) — lines 1–71
- time/utc.py (`src/cadrumo/core/time/utc.py`) — lines 1–103
<!-- /preserved:article -->
