# Text normalization, legal categories, and validity contracts

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-117` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 12 core modules totaling 1,674 lines, 61,851 bytes, and 17,728 measured proxy tokens. I read all four assigned pages in full. This is static inspection only; the TOML round-trip behavior, Unicode tables, and boundary helpers were not exercised, and I did not load application code or validate external legal sources.

## Text, legal categories, and validity

`text_fold.py` gives text-matching callers one deterministic set of Unicode transforms: NFKD accent removal against a checked-in Unicode 15.1 combining-mark table; a phrase-fold that casefolds, removes accents, collapses whitespace and preserves punctuation; an NFKC composition helper that retains accents and punctuation; and a separate ASCII slugger. Callers can choose the operation matching their need instead of treating transliteration, accent-insensitive matching, and canonical composition as the same task. The pinned mark list makes assigned characters stable across interpreter Unicode database changes; characters assigned later still inherit the runtime's decomposition behavior. Accent folding and pinned table (`src/cadrumo/core/text_fold.py`) Phrase and matching folds (`src/cadrumo/core/text_fold.py`) ASCII slugging (`src/cadrumo/core/text_fold.py`)

`TipoActividad` provides the closed Modelo 036 activity codes that separate A-series from B-series activity classifications. The source explains why this matters to activity-sensitive returns and withholding partitions, and explicitly leaves the livestock subdivision for pork-fattening and poultry outside this code set; the corresponding registry mapping is empty rather than guessed. The enum is a type vocabulary, not the registry's legal partition logic. Activity codes (`src/cadrumo/core/tipos_actividad.py`)

`ValidityWindow` requires both inclusive endpoints, refuses an inverted span, and has no implicit current date. Callers can ask whether a date or any portion of a year is covered, take the union of years covered by windows, or intersect coverage across evidence groups. This models a time-bounded grounding assertion rather than “effective until changed”; source validity claims still depend on the records and evidence passed in. Window validation and coverage (`src/cadrumo/core/validity_window.py`) Year union/intersection (`src/cadrumo/core/validity_window.py`)

## Parsing, boundary declarations, and shared guards

`toml.py` centralizes TOML parsing through `rtoml`, translates syntax/read failures through a caller-provided error factory at committed-input boundaries, converts table keys to strings only after validating them, and recursively freezes parsed arrays into tuples for strict immutable schemas. Its renderer handles nested tables, arrays of tables, inline mappings/sequences, quoted keys/strings, comments, and TOML float spellings. It is a parse/render utility, not a domain schema validator: registry/profile loaders must still enforce their own typed contract. Parse/read/freeze boundaries (`src/cadrumo/core/toml.py`) Strict committed-file bridge (`src/cadrumo/core/toml.py`) TOML renderer (`src/cadrumo/core/toml.py`)

`TransportLocus`, `TransportShape`, and `TransportRole` make CLI argument transport properties explicit. They distinguish no transport, a local input/output, and a remote handle; file, directory, and root shapes; and primary versus auxiliary paths. This gives operator-surface audits declarations to inspect rather than guesses based on Python type or option spelling. A gate can only be as complete as the authors' declarations and its checks. Transport axes (`src/cadrumo/core/transport_locus.py`)

The TTY helpers answer false rather than raising for missing, closed, or failing streams. The documentation correctly limits their claim: `isatty()` is necessary but can be insufficient on Windows (`NUL` or a console-less host can report true), so callers that collect secrets must combine it with a real-console probe. Shared type adapters and type guards offer standard or strict dictionary validation, tuple conversion, and precise runtime narrowing of untrusted mappings/lists/sets without pretending that their entries already have domain types. Safe terminal probe (`src/cadrumo/core/tty.py`) Reusable adapters (`src/cadrumo/core/type_adapters.py`) Object-container guards (`src/cadrumo/core/type_guards.py`)

`UnitProportion` and `UnitFraction` encode inclusive 0–1 bounds while keeping financial Decimal shares separate from floating-point classifier scores. `ANY_HTTP_URL_ADAPTER` consolidates the shared Pydantic absolute HTTP(S) URL validation; the module also warns that this adapter does not impose the length ceiling of Pydantic's distinct `HttpUrl`, so code needing that stronger length rule must keep using the stronger validator. Proportion and score types (`src/cadrumo/core/unit_proportion.py`) HTTP URL adapter and distinction (`src/cadrumo/core/url_validation.py`)

The Windows contention classifier recognizes errors 5 and 32, but the source notes that these can also arise from ACL/read-only conditions. A caller's retry budget, not the code alone, must distinguish transient open-handle contention from permanent refusal; off Windows, errors are never absorbed. The workbook policy uses a structural `data_type` protocol and identifies formulas for all readers to refuse rather than accepting stale cached results. Both helpers centralize a shared refusal rule while leaving caller-specific recovery/error presentation outside core. Windows contention codes (`src/cadrumo/core/windows_contention.py`) Shared formula refusal (`src/cadrumo/core/workbook.py`) First formula-cell location (`src/cadrumo/core/workbook.py`)

## Assessment and follow-up

This chunk is mostly foundational code rather than end-user flows. Its strongest contribution is explicit boundaries: different normalization transforms stay distinct; legal/corpus membership remains at the authority layer; TOML data becomes immutable before strict validation; CLI transport properties become inspectable; and formula caches cannot silently become filing inputs. Key follow-up is to verify callers choose the right fold and URL validator, that a live console probe is used for actual secret collection, and that the validity window's evidence is current. No runtime or test behavior was verified here.

## Complete assigned-file coverage

- text_fold.py (`src/cadrumo/core/text_fold.py`) — lines 1–530
- tipos_actividad.py (`src/cadrumo/core/tipos_actividad.py`) — lines 1–82
- toml.py (`src/cadrumo/core/toml.py`) — lines 1–352
- transport_locus.py (`src/cadrumo/core/transport_locus.py`) — lines 1–119
- tty.py (`src/cadrumo/core/tty.py`) — lines 1–83
- type_adapters.py (`src/cadrumo/core/type_adapters.py`) — lines 1–55
- type_guards.py (`src/cadrumo/core/type_guards.py`) — lines 1–101
- unit_proportion.py (`src/cadrumo/core/unit_proportion.py`) — lines 1–59
- url_validation.py (`src/cadrumo/core/url_validation.py`) — lines 1–27
- validity_window.py (`src/cadrumo/core/validity_window.py`) — lines 1–140
- windows_contention.py (`src/cadrumo/core/windows_contention.py`) — lines 1–47
- workbook.py (`src/cadrumo/core/workbook.py`) — lines 1–79
<!-- /preserved:article -->
