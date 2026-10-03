# Localization, identity validation, run traces, and date parsing

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-121` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 40 core modules totaling 5,326 physical lines, 207,061 bytes, and 46,899 measured `o200k_base` proxy tokens. I read all nine assigned pages, including the full locale renderer, Spanish identity validators, run-trace store, and date parsers. This static pass did not run the product or validate current legal, AEAT, VIES, or ISO authority material.

## Localization and catalogue freshness

`tr()` is the shared operator-facing translation function. It resolves a configured output language, routes dotted keys to locale YAML shards, applies both `%{name}` and `{name}` interpolation, and normalizes product identity references. Output-language precedence is an explicitly set Settings value, then the active profile resolver, then the Settings default; a separate pre-profile path keeps command-graph/help rendering from requiring full profile composition. Language cache keys use in-memory environment and settings-override identity plus explicit invalidation, avoiding filesystem stat calls on every translation. Language selection (`src/cadrumo/core/i18n/render.py`) Translation renderer (`src/cadrumo/core/i18n/render.py`)

Locale maps load YAML through PyYAML's safe C loader and cache flattened key/value entries by shard. A single-key miss first attempts a streaming scan; unsupported YAML constructs make that path fall back to a full safe load. Iteration or length requests load the full catalogue. Missing and scaffolded self-referential keys become humanized labels in production so missing copy does not abort a workflow, while ContextVar-controlled strict modes can raise during tests. Strict placeholder mode also catches missing interpolation values, including nested format fields; production logs an interpolation failure and returns its partially rendered value. Lazy shard cache and loader (`src/cadrumo/core/i18n/_lazy_catalogue.py`) Shard scan and fallback (`src/cadrumo/core/i18n/_lazy_catalogue.py`) Missing-key behavior (`src/cadrumo/core/i18n/render.py`) Production fallback (`src/cadrumo/core/i18n/render.py`)

`LocaleCatalogueCapture` gives callers a value, membership bit, digest, owner scope, and generation. It hashes sorted shard paths and bytes before and after a grouped lookup, retrying up to eight times if files change; comparison domains include a process-incarnation nonce and reject forked or foreign-process coordinates. This is a useful freshness coordinate, not a signature or authenticity check. There is a conditional cache-consistency gap for packaged locales: `_packaged_locale_map` caches a `LazyLocaleCatalogue`, whose loaded/scanned key cache has no content-version check, while capture fingerprints current file bytes directly. If packaged YAML is modified after a key was cached, the capture can pair the old cached translation with the digest of the new files. This matters only if in-process mutation is supported; either establish immutable-package/restart semantics or invalidate/rebuild cached maps when the observed digest changes. Fresh shard observation (`src/cadrumo/core/i18n/locale_catalogue.py`) Stable-window capture (`src/cadrumo/core/i18n/locale_catalogue.py`) Cached loaded/scanned values (`src/cadrumo/core/i18n/_lazy_catalogue.py`)

## Identity and shared parsing

Core identity types pin common IDs to canonical forms: profile IDs to UUIDv4, bucket IDs to trimmed bounded strings, content-addressed IDs and digests to hex-64, and profile labels to trimmed non-empty non-UUID strings. The Spanish tax-ID kernel keeps format tables, widths, leaders, and control partitions in an authority-supplied `SpanishTaxIdFormat`, validates that mapping for internal consistency, and shares NIF/NIE/CIF checksum logic between enum-returning and string-returning APIs. Its structural predicate is explicitly syntax-only. NIF-IVA helpers likewise distinguish a lexical shape test from country-specific structure supplied elsewhere and live existence checks, which this chunk does not perform. Bucket identity canonicalization (`src/cadrumo/core/identity/bucket.py`) Profile identity canonicalization (`src/cadrumo/core/identity/profile.py`) Authority-supplied Spanish format (`src/cadrumo/core/identity/documents.py`) Spanish document validation (`src/cadrumo/core/identity/documents.py`) NIF-IVA scope (`src/cadrumo/core/identity/nif_iva.py`)

The shared parsing utilities normalize ISO currency tokens, validate jurisdiction codes, parse Spanish boolean spellings as true/false/unknown, and distinguish optional/permissive date parsing from required strict date parsing. Unknown boolean text returns `None`, avoiding accidental conversion of garbage to `False`. `require_iso8601_date` enforces extended `YYYY-MM-DD` and a real calendar date; `parse_iso8601_date` delegates to `date.fromisoformat` without the extended-shape regex, so it accepts the broader forms Python supports. Callers that require the wire shape must use the stricter helper. Currency and jurisdiction helpers (`src/cadrumo/core/parsing/codes.py`) Three-state boolean parser (`src/cadrumo/core/parsing/utils.py`) Permissive ISO parser (`src/cadrumo/core/parsing/dates.py`) Strict ISO parser (`src/cadrumo/core/parsing/dates.py`) Spanish day-first parser (`src/cadrumo/core/parsing/dates.py`)

Two ISO token normalizers use Unicode-aware `str.isalpha()` but do not require ASCII. A three-letter non-ASCII alphabetic token can therefore pass the currency helper after uppercasing, and a two-letter non-ASCII uppercase token can pass the jurisdiction helper, despite both APIs naming ISO alpha codes. This is a concrete boundary mismatch for the aliases that delegate to these helpers; add explicit ASCII checks or `[A-Z]` matching and verify the Pydantic boundary rejects non-ASCII input. Currency normalizer (`src/cadrumo/core/parsing/codes.py`) Jurisdiction normalizer (`src/cadrumo/core/parsing/codes.py`)

`round_to_cents` centralizes Decimal half-up quantization to a `0.01` quantum. Its context-precision `InvalidOperation` remains possible for large magnitudes, and the module assigns range refusal to caller boundaries. This is a shared arithmetic primitive, not evidence that every calculation caller bounds values or that the convention is currently legally correct. Half-up cent rounding (`src/cadrumo/core/money/rounding.py`)

## Run recording, persistence, and privacy

`run_context()` mints a 16-hex run ID, fingerprints effective Settings, the canonical data root, and the configured certificate, then binds run/step context variables, attaches a JSONL sink, records step events, and saves a final trace even when the body fails. Nested contexts reuse the run ID and add step boundaries. Trace and event DTOs are frozen, strict, and typed; each event must contain exactly one payload. Run context lifecycle (`src/cadrumo/core/observability/context.py`) Exactly-one event payload (`src/cadrumo/core/observability/models.py`) Trace fields (`src/cadrumo/core/observability/models.py`)

The event schema covers navigation URLs, literal form-field values, assertions, cache hits, free-form errors, workflow links, and generic string pairs. The model documentation explicitly classifies traces as tax/PII-sensitive and warns that arguments are not redacted at model construction. The JSONL sink and `save_trace` do apply the DIAGNOSTIC structured-redaction rules to every string leaf; the event sink is bound to one run ID, ignores ordinary log records, serializes under an append lock, flushes each line, and fsyncs on close. Those rules reduce NIFs, token-shaped strings, and URL paths, but the audit record still includes literal form amounts and arbitrary diagnostics, and the code itself writes JSON/JSONL without encryption. The model therefore correctly warns operators to treat these artifacts as tax-return data; actual filesystem permissions or storage-layer protection are outside this chunk. Sensitive payload contract (`src/cadrumo/core/observability/models.py`) Sink redaction and run filter (`src/cadrumo/core/observability/sink.py`) Redacted trace persistence (`src/cadrumo/core/observability/store.py`)

Run IDs are shape-validated before becoming path segments; traces are atomically written and checked against the directory's ID when loaded. Read APIs do not create missing directories, event iteration streams and strictly validates records, and trace pruning applies age and total-size limits while protecting the newest run. However, the direct `save_events_append(run_id, event)` path does not check that `event.run_id == run_id`, and `iter_events(run_id)` validates each event's shape without comparing its embedded run ID to the requested directory. A valid event tagged for run B can therefore be persisted in run A's directory and yielded there; the JSONL handler's run-ID filter does not protect this separate direct-write API. Add the identity check at write and read boundaries, then trace production callers to establish reachability. Run-ID path guard (`src/cadrumo/core/observability/store.py`) Direct event append (`src/cadrumo/core/observability/store.py`) Event iteration (`src/cadrumo/core/observability/store.py`) Event run ID field (`src/cadrumo/core/observability/models.py`)

`save_envelope` intentionally trusts that its caller passes a CLI-redacted document and does not independently redact it. `save_trace` fingerprints the data directory with exclusions from the storage taxonomy and hashes the certificate bytes without unlocking it. Fingerprints provide deterministic change indicators, not signed provenance; unreadable files are represented by a stable error marker. Envelope persistence contract (`src/cadrumo/core/observability/store.py`) Data-root fingerprint (`src/cadrumo/core/observability/fingerprint.py`) Certificate fingerprint (`src/cadrumo/core/observability/fingerprint.py`)

## Assessment and follow-up

The strongest controls are typed identity/record boundaries, explicitly authority-supplied Spanish ID parameters, safe YAML loading, production fail-soft localization with test strictness, bounded run retention, canonical run-path validation, and repeated structured redaction at trace/event persistence. Main follow-up items are the locale-cache/current-digest mismatch under supported mutation, non-ASCII acceptance in ISO token helpers, event-to-directory run-ID binding, and verification that producers redact secret-named arguments before trace construction. No tests are in this chunk; static review does not establish current catalog coverage, the correctness of authority data, completeness of redaction, or whether identified conditional paths have production callers.

## Complete assigned-file coverage

- i18n/__init__.py (`src/cadrumo/core/i18n/__init__.py`) — lines 1–9
- i18n/_lazy_catalogue.py (`src/cadrumo/core/i18n/_lazy_catalogue.py`) — lines 1–322
- i18n/auth_provider.py (`src/cadrumo/core/i18n/auth_provider.py`) — lines 1–20
- i18n/locale_catalogue.py (`src/cadrumo/core/i18n/locale_catalogue.py`) — lines 1–246
- i18n/render.py (`src/cadrumo/core/i18n/render.py`) — lines 1–722
- i18n/routing.py (`src/cadrumo/core/i18n/routing.py`) — lines 1–54
- i18n/translatable.py (`src/cadrumo/core/i18n/translatable.py`) — lines 1–35
- identity/__init__.py (`src/cadrumo/core/identity/__init__.py`) — lines 1–9
- identity/aeat_box.py (`src/cadrumo/core/identity/aeat_box.py`) — lines 1–16
- identity/aeat_certificado.py (`src/cadrumo/core/identity/aeat_certificado.py`) — lines 1–13
- identity/aeat_clave_liquidacion.py (`src/cadrumo/core/identity/aeat_clave_liquidacion.py`) — lines 1–13
- identity/aeat_csv.py (`src/cadrumo/core/identity/aeat_csv.py`) — lines 1–23
- identity/aeat_expediente.py (`src/cadrumo/core/identity/aeat_expediente.py`) — lines 1–30
- identity/aeat_presentation.py (`src/cadrumo/core/identity/aeat_presentation.py`) — lines 1–13
- identity/bucket.py (`src/cadrumo/core/identity/bucket.py`) — lines 1–68
- identity/continuidad.py (`src/cadrumo/core/identity/continuidad.py`) — lines 1–20
- identity/digest.py (`src/cadrumo/core/identity/digest.py`) — lines 1–67
- identity/documents.py (`src/cadrumo/core/identity/documents.py`) — lines 1–430
- identity/hex_ids.py (`src/cadrumo/core/identity/hex_ids.py`) — lines 1–41
- identity/nif_iva.py (`src/cadrumo/core/identity/nif_iva.py`) — lines 1–103
- identity/profile.py (`src/cadrumo/core/identity/profile.py`) — lines 1–66
- identity/profile_label.py (`src/cadrumo/core/identity/profile_label.py`) — lines 1–47
- identity/tax_id.py (`src/cadrumo/core/identity/tax_id.py`) — lines 1–173
- identity/transaction_ids.py (`src/cadrumo/core/identity/transaction_ids.py`) — lines 1–18
- money/__init__.py (`src/cadrumo/core/money/__init__.py`) — lines 1–20
- money/rounding.py (`src/cadrumo/core/money/rounding.py`) — lines 1–43
- observability/__init__.py (`src/cadrumo/core/observability/__init__.py`) — lines 1–8
- observability/capture.py (`src/cadrumo/core/observability/capture.py`) — lines 1–71
- observability/context.py (`src/cadrumo/core/observability/context.py`) — lines 1–430
- observability/errors.py (`src/cadrumo/core/observability/errors.py`) — lines 1–93
- observability/fingerprint.py (`src/cadrumo/core/observability/fingerprint.py`) — lines 1–255
- observability/models.py (`src/cadrumo/core/observability/models.py`) — lines 1–393
- observability/recorder.py (`src/cadrumo/core/observability/recorder.py`) — lines 1–105
- observability/redaction_rules.py (`src/cadrumo/core/observability/redaction_rules.py`) — lines 1–40
- observability/sink.py (`src/cadrumo/core/observability/sink.py`) — lines 1–165
- observability/store.py (`src/cadrumo/core/observability/store.py`) — lines 1–630
- parsing/__init__.py (`src/cadrumo/core/parsing/__init__.py`) — lines 1–9
- parsing/codes.py (`src/cadrumo/core/parsing/codes.py`) — lines 1–106
- parsing/dates.py (`src/cadrumo/core/parsing/dates.py`) — lines 1–301
- parsing/utils.py (`src/cadrumo/core/parsing/utils.py`) — lines 1–99
<!-- /preserved:article -->
