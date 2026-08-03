---
tags:
  - '#research'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:b3530fb33097f1ea316162e7439407c69dba734d5da39ee1f869d13fbf3468e2'
related: []
---

# `canonical-storage-management` research: `storage-location authorities, blast radius, and enrollment surface`

The question: what exactly decides where a byte lands on disk today, and what
would a single typed authority have to absorb to make that decision
enumerable, overridable, and gate-enforced?

The evidence picture is sharper than the campaign's opening premise. The
premise was that `_STATE_ROOT_DERIVED_DIRS` in `src/cadrumo/core/config.py:96`
is *the* untyped incumbent, a `dict[str, str]` of 28 entries to be typed. That
dict is real and is 28 entries, but it is **not** the inventory. At least four
independent authorities decide on-disk locations under
`cadrumo_local_storage_root`, they do not reference one another, and the two
most security-load-bearing directories in the product tree — `buckets/` (bucket
database, blobs, audit log) and `keystore/` (bucket DEK, persisted session,
login throttle) — are declared in none of them but the second. Typing the dict
alone would leave the tree half-governed and the enrollment gate blind to the
sites that most need it.

Method: `vaultspec-rag` semantic probes (`--type code --port 8766`, and
`--type vault --doc-type adr` for decisions) followed by targeted `rg`/full
reads confirming every load-bearing claim against the working tree on
2026-08-03. Five parallel discovery ledgers covered core settings, data
surfaces, integrations, tests/tooling, and prior decisions plus the CLI; every
claim reproduced below was re-verified directly, not carried from a ledger.

## Findings

### F1 — Four parallel location authorities, mutually unaware

The Settings-derived taxonomy is one of four. The others were confirmed by
direct read:

- **Settings taxonomy.** `src/cadrumo/core/config.py:96` declares
  `_STATE_ROOT_DERIVED_DIRS: dict[str, str]`, 28 entries keyed by settings-field
  name, valued as POSIX relative subpaths. The derivation validator
  `_resolve_output_dirs_under_storage_root` (`src/cadrumo/core/config.py:1096`)
  re-roots each field under `cadrumo_local_storage_root` unless the field is
  already in `model_fields_set`; `ensure_storage_tree`
  (`src/cadrumo/core/config.py:1370`) materialises exactly this dict and
  nothing else.
- **Namespace registry.** `src/cadrumo/adapters/persistence/storage/_namespace_registry.py:31`
  declares bare string constants: `BUCKETS_DIRNAME = "buckets"`,
  `BUCKET_DB_DIRNAME = "db"`, `BUCKET_BLOBS_DIRNAME = "blobs"`,
  `BUCKET_AUDIT_DIRNAME = "audit"`, `BUCKET_MANIFEST_FILENAME = "manifest.toml"`,
  `BUCKET_LOCK_FILENAME = ".lock"`,
  `BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME = "output-language.hint"`,
  `KEYSTORE_DIRNAME = "keystore"`, `BUCKET_DEK_FILENAME = "bucket.dek.json"`,
  `PROFILE_SESSION_FILENAME = "session.v1.json"`,
  `LOGIN_THROTTLE_FILENAME = "login-throttle.json"`,
  `CONFIG_RESET_JOURNAL_DIRNAME = "reset-operations"`. These resolve through
  `bucket_paths` (`src/cadrumo/adapters/persistence/storage/bucket/_layout.py:47`)
  and `keystore_path`
  (`src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py:22`).
  `buckets/` and `keystore/` are real top-level directories under the storage
  root, structurally peer to `tokens/` and `secrets/`, with no settings field,
  no environment override, and no `ensure_storage_tree` coverage.
- **Module-local constants.** `src/cadrumo/application/corpus_search/_runtime.py:28`
  declares `_INDEX_SUBDIR = "corpus-search"` and resolves
  `cadrumo_local_storage_root / _INDEX_SUBDIR`;
  `src/cadrumo/entrypoints/mcp/_telemetry.py` declares
  `_TELEMETRY_DIRNAME = "telemetry"` and resolves it the same way;
  `src/cadrumo/core/_bucket_pointer_io.py:42` declares
  `_POINTER_FILENAME = "active-profile"` for the top-level pointer file. Each is
  root-anchored (so no escape), each is invisible to every gate and to the
  operator's override surface.
- **Inline literals duplicating the registry.** `src/cadrumo/core/config.py:1088`
  builds `cadrumo_local_storage_root / "buckets" / bucket_id / "db" / PRODUCT_DATABASE_FILENAME`
  from bare strings rather than importing the constants, and
  `src/cadrumo/core/_config_storage_route.py:127` matches
  `parts[0] == "buckets" and parts[2:] == ("db", PRODUCT_DATABASE_FILENAME)`
  the same way. Neither is pinned to the namespace-registry constants by a
  parity test, unlike `CONFIG_RESET_JOURNAL_DIRNAME`, whose deliberate
  duplicate in `src/cadrumo/application/_config_reset_repository.py:27` is
  pinned at `src/cadrumo/tests/test_persisted_format_enrollment.py:143`.
  A rename of either constant silently breaks the SQLite fallback URL and the
  route classifier.

Consequence for the option space: an authority scoped to "the settings fields"
is a smaller thing than an authority scoped to "the locations". The ADR must
choose which it is building, and if the former, must say what governs the rest.

### F2 — The existing anti-literal gate is structurally blind to every site in F1

`test_no_production_module_names_an_operator_data_location_by_literal`
(`src/cadrumo/core/tests/test_settings_lifecycle_gate.py`) sweeps production
modules with the regex `Path\(\s*"([^"]*/[^"]*)"` and flags a literal whose
segments intersect the taxonomy vocabulary. Two properties of that predicate
bound its reach hard:

- It matches only a `Path("…")` call whose literal **contains a slash**. The
  ad-hoc sites build paths by operator join — `root / "buckets" / bucket_id / "db"`,
  `cadrumo_local_storage_root / _INDEX_SUBDIR` — which the regex cannot see.
- Its vocabulary is derived from `_STATE_ROOT_DERIVED_DIRS.values()`, so a
  segment that was never enrolled (`buckets`, `keystore`, `corpus-search`,
  `telemetry`, `active-profile`) is not in the vocabulary and cannot be flagged
  even if it did appear in a slashed literal.

The gate therefore certifies exactly the sites that are already enrolled, and
is silent on the class it was written to catch. This is the single most
important input to the ADR's gate ruling: a literal-census gate cannot close
this, and a stricter regex would only chase a syntax the offenders do not use.
A property-shaped gate — every produced location resolves through the typed
accessor — is the only shape that reaches join-built paths.

### F3 — Lifecycle classification is a second hand-maintained axis over the same fields

`src/cadrumo/core/tests/test_settings_lifecycle_gate.py` classifies every
`_dir`/`_path`/`_root` `Path`-typed settings field into exactly one of five
hand-maintained frozensets: `_ROTATION` (1 field), `_TTL` (1),
`_RETENTION` (6), `_UNBOUNDED_BY_DESIGN` (23), `_EXEMPT_INPUT` (5). The gate
asserts total coverage, pairwise disjointness, and that a non-exempt output
directory either appears in `_STATE_ROOT_DERIVED_DIRS` or carries a `None`
default (the opt-in-override branch).

The two axes describe the same fields from different modules and can drift
independently: `cadrumo_registry_disk_cache_dir` is lifecycle-classified
`_RETENTION` while being absent from the subpath taxonomy, satisfying the gate
only through the opt-in branch. The rationale prose for the classification
(why the corpus-text cache is bounded, why live read-evidence must never be
pruned) is genuine domain knowledge currently living in test-module comments,
which no production consumer can read. Whether that axis folds onto the typed
member or stays orthogonal is a live ADR question; leaving it implicit is how
the gate rots.

### F4 — The file-versus-directory distinction is carried by a name suffix, not a type

`ensure_storage_tree` (`src/cadrumo/core/config.py:1414`) decides whether to
create a path or its parent with `field_name.endswith("_path")`. The taxonomy
holds exactly one file today, `cadrumo_usage_ratios_path`
(`financial/usage-ratios.json`), pinned by
`test_usage_ratios_path_is_classified_as_a_file_output`. A future file entry
whose settings-field name does not end in `_path` would silently receive a
directory created over it. The namespace registry (F1) additionally holds six
file names that no suffix convention governs at all.

### F5 — The `cache/` prefix asymmetry is deliberate and documented

Confirmed by reading the table comment at `src/cadrumo/core/config.py:96`:
`cache/` is the sole literal on-disk prefix (`cache/llm-cache`,
`cache/status-cache`, `cache/corpus-text`, `cache/registry-verdict`); the
state, logs, and exports groupings are conceptual classifications carried as
bare self-describing leaf names, matching the pre-existing
`tokens`/`secrets`/`blobs`/`audit` layout. The comment states this explicitly:
the lifecycle grouping "is a conceptual classification, not a rigid path
prefix." A uniform structural prefix would move every non-cache directory on
disk — a far larger blast radius than typing the representation, and a change
the ADR must take deliberately rather than as a side effect of tidying.

`src/cadrumo/domain/calculations/registry/_loader_cache.py:230` independently
hand-writes `storage_root / "cache" / "registry"` as its production branch,
honouring the prefix convention without drawing it from the table.

### F6 — Escape categories: what legitimately sits outside the root

Four distinct kinds of path-valued setting are not app-generated output under
the root, and they differ in *why*:

- **Bundled read-only package resources.** `aeat_manuals_root`,
  `aeat_normatives_root`, `cadrumo_iva_catalogue_root`
  (`src/cadrumo/core/config.py:522`) resolve through `bundled_path`
  (`src/cadrumo/core/resources/_boundary.py:65`) into the installed package.
  Read-only, shipped, never written.
- **Operator-supplied inputs.** `cadrumo_certificate_path` — a credential the
  operator owns and names; the application reads it and never chooses its
  location.
- **Third-party-owned caches.** The Playwright browser root
  (`src/cadrumo/application/provisioning.py:162`) resolves
  `PLAYWRIGHT_BROWSERS_PATH` or a per-OS default; it holds a vendor's binaries
  under the vendor's own layout convention.
- **External executables.** `cadrumo_libreoffice_executable`
  (`src/cadrumo/core/config.py:501`) is `Path | None`, resolved from `PATH`
  when unset. It is classified in none of the five lifecycle frozensets and is
  invisible to the gate's own field selector, because its name ends in neither
  `_dir`, `_path`, nor `_root`. Whether that omission was deliberate is
  unrecorded; it is the one path-valued field with no declared position in any
  current structure.

The distinguishing question across all four is the same and is answerable
mechanically: does the application *choose* this location for data it *writes*?
Bundled resources and operator inputs fail the write test; third-party caches
and external binaries fail the choose test. Nothing in the current tree
classifies escapes by this question — membership is decided per field by
frozenset editing.

### F7 — Two taxonomy entries are declared but have no production writer

`cadrumo_storage_backup_dir` (`backups`) has no production consumer:
`rg` across the non-test tree returns only its own field declaration, the
taxonomy table entry, and `src/cadrumo/core/observability/_fingerprint.py`,
which *excludes* it from a content fingerprint. No backup-writing code path
exists. `cadrumo_inbox_dir` and `cadrumo_inbox_pdf_dir` likewise have no
production reader; only review-module test fixtures reference them.

This repeats a pattern the prior campaign already paid for: two fields
(`cadrumo_purchase_invoice_evidence_dir`, `cadrumo_ledgers_dir`) were declared
with zero consumers and deleted after a per-field liveness audit. A typed
member set is a stronger structure than a dict only if registration is coupled
to a real consumer; otherwise it relocates the declare-but-never-wire failure
from dict keys into enum members. A CRUD inspection surface reporting
per-category populated-versus-empty state would make the condition visible to
the operator rather than discoverable only by audit.

### F8 — Prior decisions constrain but do not conflict

`2026-07-13-data-output-standardization-adr` is accepted and its rulings hold
at HEAD. Two of its rulings bind this increment directly: one root with a
category taxonomy beneath it (its Option O2), and the explicit rejection of a
platformdirs-style multi-root split (its Option O3) on the grounds that
fragmenting across OS-native roots breaks the operator's mental model and the
backup and export flows that assume one root. It rules on locations and
lifecycle, and is silent on Python-level representation — so a typed taxonomy
formalizes its O2 rather than contradicting it.

The four other accepted ADRs whose stems contain "storage" —
`2026-05-22-secure-storage-production-hardening-architecture-adr`,
`2026-06-04-storage-encryption-adr`,
`2026-06-14-storage-backend-security-review-adr`, and
`2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr` — were checked by
title and status: each governs the encrypted substrate's internals (custody,
key handling, security review, ledger record storage), not the on-disk location
taxonomy. No accepted ADR conflicts with a typed storage-category authority.
The operator's standing goal anticipates superseding conflicting ADRs; the
evidence is that there are none, which is itself worth recording so a future
reader does not hunt for one.

`cadrumo.core.COMPATIBILITY_REGIME` is `PRE_RELEASE`
(`src/cadrumo/core/compatibility_lifecycle.py:53`), so `no-legacy-compatibility`
governs in full: an on-disk layout change may strand pre-existing local data,
delete-not-migrate applies, and no read-tolerance of an older layout may be
added. This is permission, not obligation — the ADR still owes an explicit
ruling on whether layout changes.

### F9 — The CRUD surface would be net-new but not unprecedented

No `config storage` verb group exists. The nearest surfaces are `config repair
logs` (reports the log path and tails it — one category, read-only) and the
per-profile encrypted bundle and archive export/import verbs, which operate on
one profile's encrypted state as a portable artefact and deliberately exclude
caches, logs, and exports.

A generic contract already governs mutating noun-groups:
`src/cadrumo/application/operator_surface/_crud_contract.py` defines the
five-verb spine (`add`/`remove`/`update`/`view`/`list`) and three documented
exception kinds — `STRICT_CRUD`, `KEY_VALUE_AS_RECORD`, and
`LIFECYCLE_OPERATIONS_ONLY`. `_crud_registry.py` registers five noun-groups;
none is a storage group. Storage categories are a fixed, registry-defined set
that an operator cannot create or destroy, which is the same reasoning the
`APODERADO` and `INVENTORY` entries used to claim `LIFECYCLE_OPERATIONS_ONLY`.
Whether a purely read-only group must register at all is not settled by the
contract's own text, which scopes itself to noun-groups exposing an edit work
surface.

Envelope conformance is not optional: a new leaf needs a registered
`OutputSchema` subclass (`test_every_cli_leaf_has_a_registered_schema`), must
carry no bespoke advisory, `next`, or `suggestion` result field
(`test_registered_schema_has_no_bespoke_notice_field`), must round-trip, and
must be documented in the same commit through the reference generator.
Operator-facing strings need locale keys in all four catalogues via the locales
CLI.

### F10 — A pre-existing red test sits on this axis

`test_relative_env_paths_resolve_from_project_root` and
`test_relative_audit_flagged_paths_resolve_under_project_root` in
`src/cadrumo/tests/test_config.py` asserted that a relative environment
override anchors under the repository root, while `_relative_path_anchor`
(`src/cadrumo/core/paths.py:42`) deliberately carries no source-checkout arm and
anchors to the platform user-data root instead. The tests were not updated when
that arm was removed, and were red when this research was opened.

**Resolved during authoring, by a peer, not by this campaign.** A commit
landing while this document was being written re-anchored both tests via an
isolated `LOCALAPPDATA`, matching the pattern already used in the SQL engine
tests, and additionally documented and normalised three path settings
(`CADRUMO_FILED_DECLARATIONS_DIR`, `CADRUMO_IVA_COMPENSATION_HISTORY_DIR`,
`CADRUMO_IVA_READ_EVIDENCE_DIR`) that were absent from the environment
reference and from the normalisation validator tuple. Both tests were
re-run at HEAD after that commit and pass.

The finding is retained rather than deleted because the underlying semantics
remain load-bearing for this campaign: relative overrides anchor to the
platform user-data root, never to the checkout, and any future change to
anchoring must update these tests deliberately. What is no longer true is the
obligation — this campaign inherits no red test on this axis.

### What was not investigated

Per-flag enumeration of every `typer.Option` taking a `Path` was sampled, not
exhausted; the plan's enrollment site list needs a full sweep of CLI defaults
reading `load_settings().cadrumo_*`. `dev/docs/tests/test_env_reference.py` was
not read, and it gates drift between the generated environment reference and
the settings fields — a field rename would trip it. The nesting of two
OS-temp staging directories in the review-package flow
(`src/cadrumo/application/modelo/_review_package.py:270` and
`src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py:287`) is an existing
reviewed exception whose *destination choice*, as opposed to its write call,
has not been reviewed; it is adjacent to this campaign but is a
sensitive-data-staging question rather than a taxonomy question.

## Sources

- `src/cadrumo/core/config.py:96` — the derived-dirs table and its prefix comment
- `src/cadrumo/core/config.py:501` — `cadrumo_libreoffice_executable`
- `src/cadrumo/core/config.py:522` — bundled resource roots
- `src/cadrumo/core/config.py:1088` — inline `buckets`/`db` literal
- `src/cadrumo/core/config.py:1096` — the derivation validator
- `src/cadrumo/core/config.py:1370` — `ensure_storage_tree`
- `src/cadrumo/core/config.py:1414` — the `_path` suffix file/directory branch
- `src/cadrumo/core/paths.py:42` — `_relative_path_anchor`
- `src/cadrumo/core/_config_state_root.py:157` — platform user-data resolution
- `src/cadrumo/core/_config_storage_route.py:127` — the route classifier literal
- `src/cadrumo/core/_bucket_pointer_io.py:42` — the `active-profile` pointer name
- `src/cadrumo/core/compatibility_lifecycle.py:53` — the compatibility regime
- `src/cadrumo/core/resources/_boundary.py:65` — `bundled_path`
- `src/cadrumo/core/observability/_fingerprint.py` — backup-dir fingerprint exclusion
- `src/cadrumo/core/tests/test_settings_lifecycle_gate.py` — the lifecycle and literal gates
- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py:31` — the second authority
- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py:47` — `bucket_paths`
- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py:22` — `keystore_path`
- `src/cadrumo/application/corpus_search/_runtime.py:28` — `corpus-search`
- `src/cadrumo/application/provisioning.py:162` — the Playwright browser root
- `src/cadrumo/application/_config_reset_repository.py:27` — the pinned duplicate
- `src/cadrumo/application/operator_surface/_crud_contract.py` — the CRUD contract
- `src/cadrumo/application/operator_surface/_crud_registry.py` — the registered catalogue
- `src/cadrumo/entrypoints/mcp/_telemetry.py` — the `telemetry` directory
- `src/cadrumo/domain/calculations/registry/_loader_cache.py:230` — the registry cache branch
- `src/cadrumo/tests/test_config.py` — the two red relative-path tests
- `src/cadrumo/tests/test_persisted_format_enrollment.py:143` — the reset-journal parity pin
- `2026-07-13-data-output-standardization-adr` — the accepted prior decision
