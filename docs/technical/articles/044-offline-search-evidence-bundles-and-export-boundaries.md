# Offline search, evidence bundles, and export boundaries

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-044` · **Topic:** [Application orchestration and diagnostics](../topics/application-orchestration-and-diagnostics.md)

<!-- preserved:article -->
## Scope

This chunk covers 21 application modules (3,740 lines; 31,228 measured proxy tokens). I read every assigned range across six bounded pages. This is static inspection; no index build, bundle write, spreadsheet call, file export, or external contact was executed. Statements describing legal or operator-facing meaning are implementation behavior, not independent validation of those claims.

## Command discovery and corpus grounding

The command index ranks plain command documents locally. When SQLite FTS5 is available, it uses Spanish tokenization and stemming with separately weighted command key/name, curated aliases, description, and per-verb help columns; otherwise a token-overlap scorer preserves a useful offline search. Blank/short-only queries and nonpositive limits return no hits. Results expose an ordinal-derived score rather than claiming that the two scoring paths share a meaningful scale. Weighted index and fallback (`src/cadrumo/application/command_search/index.py`) Search ranking (`src/cadrumo/application/command_search/index.py`)

Normative grounding has two deliberately separate paths: exact citation IDs resolve through signed registry evidence, while in-prose concepts rank over a local FTS5 index of extracted normative HTML. Citation text is read from the pinned operation’s legal-evidence projection and checked against the requested legal-reference ID; arbitrary corpus paths are not opened, and a corpus reference must match exactly one known catalogue entry. The lexical index preserves deterministic source/anchor metadata and Spanish folded/stemmed text. Citation resolution (`src/cadrumo/application/corpus_search/citation_lookup.py`) Known-reference text lookup (`src/cadrumo/application/corpus_search/citation_lookup.py`) Lexical search (`src/cadrumo/application/corpus_search/lexical_index.py`)

The cache identity hashes schema versions plus sorted relative paths and exact extracted bytes. Runtime rebuilding is lock-protected, stages the database beside the destination, rechecks source identity, and atomically replaces the cache; query matching is bound as a SQL parameter. One scope boundary matters: the lower-level `build_lexical_index` drops its target tables before rebuilding, so callers outside this staging flow must pass a disposable index path. The runtime service itself handles exact citation lookup before lexical ranking and leases one bundled authority operation for the lookup. Atomic cache provisioning (`src/cadrumo/application/corpus_search/runtime.py`) Cache identity (`src/cadrumo/application/corpus_search/runtime.py`) Fresh-index builder (`src/cadrumo/application/corpus_search/lexical_index.py`) Retrieval dispatch (`src/cadrumo/application/corpus_search/_retrieval.py`)

Terminology search loads bundled TOML concepts, projects the requested locale with Spanish fallback, and defaults to approved lifecycle only. Unknown lifecycle values are refused instead of silently disappearing. Matching prioritizes exact IDs/labels, then prefix and substring label matches, then descriptions/definitions; it is deterministic by score and concept ID and is a small in-memory lexical matcher, not semantic retrieval. The function permits a caller to pass another lifecycle set, so the transport/caller admission should be checked to ensure taxpayer-facing surfaces retain the approved-only default. Terminology loading (`src/cadrumo/application/corpus_search/terminology.py`) Terminology ranking (`src/cadrumo/application/corpus_search/terminology.py`)

## Evidence bundles and deletion holds

Evidence bundles group bucket-local object references with content hashes and sizes. Their stable identifier covers manifest version, bucket/work-unit IDs, optional revision/filing IDs, and ordered object type/ID/digest triples. `show` performs exact lookup then bucket-scoped prefix lookup, refusing ambiguous prefixes. `check` verifies the manifest ID, bucket and work-unit binding, object reachability, and digests; reachability is byte-weighted for completeness. Missing objects yield `INCOMPLETE`, while digest disagreement or failed integrity checks yield `FAILED`. `export` always refuses failed verification; incomplete export needs the explicit override, and its ZIP writes record payloads before `manifest.json`. Bundle identity (`src/cadrumo/application/evidence/models.py`) Lookup and verification (`src/cadrumo/application/evidence/service.py`) Export checks and archive (`src/cadrumo/application/evidence/service.py`)

Two boundary checks deserve follow-up. First, `EvidenceRecordRef.object_id` is only length-bounded in the model, while ZIP member names interpolate that value directly. Trace object-ID admission; if separators or traversal components can reach this service, reject or encode them before archive creation. This is a path-safety concern in the local serialization boundary, not proof that a normal repository can produce such an ID. Second, `build` persists a manifest without consulting the supplied work-unit port; `check` detects a missing work unit later. Verify the build caller supplies a known work unit or decide whether construction should reject it up front. The service’s operator-directed ZIP is plaintext by design and can contain the referenced object bytes, so its output path and recipient remain an explicit caller choice.

The legal-hold owner stores a bounded canonical snapshot of sorted open-case IDs, profile identity, timestamp, and a self-digest in the local custody record store. Projection checks the UUID/path binding, canonical bytes, digest and UTC time; a missing or malformed record raises rather than clearing a hold. The public projection derives `blocks_local_deletion` from whether any cases are listed, and the mutation interface has no caller-supplied held/cleared boolean. Its documented lifecycle gap is material: today’s best-effort producer runs at profile registration with an empty case list, and the module says no producer refreshes it when filings/expedientes or external litigation later arise. That can leave a once-true “no known cases” snapshot stale; trace freshness and refresh ownership in deletion admission before treating this projection as current legal clearance. Snapshot validation and projection (`src/cadrumo/application/evidence/profile_legal_hold.py`) Owner API (`src/cadrumo/application/evidence/profile_legal_hold.py`) Registration snapshot limitation (`src/cadrumo/application/evidence/profile_legal_hold.py`)

## Google Sheets and tabular export

The supervised Google workbook export binds an exact active profile, checks the export capability, validates a canonical filing period, selects a registry snapshot, and builds the workbook plan before preparing the injected transport. The request’s subject must match that profile. Dry-run requires the port to return the same dry-run flag and records no effect; an applied call enters an irreversible section, records `UNKNOWN` before the remote mutation and `UPDATED` after success, then stores a strict result with revision, registry hash and engine version. Concrete Google credentials and adapters are outside this module. The separate synchronous service method is documented as a legacy reuse path and does not itself emit supervisor effect events; confirm no production caller relies on it for supervised mutation. Admission and plan path (`src/cadrumo/application/export/google_operation.py`) Port result check (`src/cadrumo/application/export/google_operation.py`) Supervised execution (`src/cadrumo/application/export/google_operation.py`)

The tabular serializer is a pure in-memory CSV/JSONL/XLSX renderer with fixed format metadata, normalized unique field names, and rejection of unknown row keys. Its result model recomputes byte size, SHA-256, media type, extension, and row count from the payload, including format-specific parsing. Metadata validation (`src/cadrumo/application/export/tabular.py`) Serializer (`src/cadrumo/application/export/tabular.py`) Metadata verifier (`src/cadrumo/application/export/tabular.py`)

The CSV writer emits values as received after string conversion and adds no spreadsheet-formula neutralization. For user-controlled ledger text, a cell beginning with a spreadsheet formula marker can become active when opened in spreadsheet software; follow the row-source path and apply a safe text encoding policy where needed. XLSX also appends strings through the workbook library without an explicit formula-leading-string defense, so verify that library behavior or force text cells. The model validates listed field names but its consistency check does not compare the CSV header or JSONL object keys back to `fieldnames`; serializer-produced results are consistent, while manually constructed result models should not be treated as proof of field-schema consistency without caller controls. CSV writer (`src/cadrumo/application/export/tabular.py`) XLSX writer (`src/cadrumo/application/export/tabular.py`) Payload consistency gate (`src/cadrumo/application/export/tabular.py`)

## Implementation assessment

The strongest controls here are offline lexical-only retrieval with signed exact-citation evidence, content-keyed atomic index refresh, strict bucket-bound evidence checks, a fail-closed legal-hold projection, exact-profile and supervised remote-export effect tracking, and output metadata recomputation. Scoped follow-ups are work-unit admission at bundle build, archive-member ID safety, legal-hold snapshot freshness, the legacy synchronous remote-export call path, and spreadsheet-formula handling for arbitrary tabular text. No test or external-service behavior was exercised in this pass.

## Complete assigned-file coverage

- command_search/__init__.py (17 lines) (`src/cadrumo/application/command_search/__init__.py`)
- command_search/index.py (218 lines) (`src/cadrumo/application/command_search/index.py`)
- corpus_search/__init__.py (20 lines) (`src/cadrumo/application/corpus_search/__init__.py`)
- corpus_search/_retrieval.py (84 lines) (`src/cadrumo/application/corpus_search/_retrieval.py`)
- corpus_search/citation_lookup.py (180 lines) (`src/cadrumo/application/corpus_search/citation_lookup.py`)
- corpus_search/errors.py (71 lines) (`src/cadrumo/application/corpus_search/errors.py`)
- corpus_search/lexical_index.py (349 lines) (`src/cadrumo/application/corpus_search/lexical_index.py`)
- corpus_search/models.py (180 lines) (`src/cadrumo/application/corpus_search/models.py`)
- corpus_search/runtime.py (197 lines) (`src/cadrumo/application/corpus_search/runtime.py`)
- corpus_search/terminology.py (381 lines) (`src/cadrumo/application/corpus_search/terminology.py`)
- evidence/__init__.py (55 lines) (`src/cadrumo/application/evidence/__init__.py`)
- evidence/bundle_text.py (24 lines) (`src/cadrumo/application/evidence/bundle_text.py`)
- evidence/models.py (210 lines) (`src/cadrumo/application/evidence/models.py`)
- evidence/payloads.py (29 lines) (`src/cadrumo/application/evidence/payloads.py`)
- evidence/ports.py (64 lines) (`src/cadrumo/application/evidence/ports.py`)
- evidence/profile_legal_hold.py (271 lines) (`src/cadrumo/application/evidence/profile_legal_hold.py`)
- evidence/service.py (457 lines) (`src/cadrumo/application/evidence/service.py`)
- export/__init__.py (35 lines) (`src/cadrumo/application/export/__init__.py`)
- export/errors.py (33 lines) (`src/cadrumo/application/export/errors.py`)
- export/google_operation.py (511 lines) (`src/cadrumo/application/export/google_operation.py`)
- export/tabular.py (354 lines) (`src/cadrumo/application/export/tabular.py`)
<!-- /preserved:article -->
