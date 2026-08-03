---
tags:
  - '#research'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:2169cba2675029e6e4378289653bfb0490f921fc6d7a05ebe34121ce2de509b9'
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

The Settings-derived taxonomy is one of four. All were confirmed by direct
read:

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
  no environment override, and no `ensure_storage_tree` coverage. That absence
  of an override is deliberate, not an oversight: an operator must not be able
  to relocate a keystore out from under the bucket it unlocks.
- **Module-local constants.** `src/cadrumo/application/corpus_search/_runtime.py:28`
  declares `_INDEX_SUBDIR = "corpus-search"` and resolves
  `cadrumo_local_storage_root / _INDEX_SUBDIR`;
  `src/cadrumo/entrypoints/mcp/_telemetry.py:44` declares
  `_TELEMETRY_DIRNAME = "telemetry"` and resolves it the same way;
  `src/cadrumo/core/_bucket_pointer_io.py:42` declares
  `_POINTER_FILENAME = "active-profile"` for the top-level pointer file. Each is
  root-anchored (so no escape), each is invisible to every gate and to the
  operator's override surface.
- **Inline literals duplicating the registry — three copies, not two.**
  `src/cadrumo/core/config.py:1088` builds
  `cadrumo_local_storage_root / "buckets" / bucket_id / "db" / PRODUCT_DATABASE_FILENAME`
  from bare strings; `src/cadrumo/core/_config_storage_route.py:127` matches
  `parts[0] == "buckets" and parts[2:] == ("db", PRODUCT_DATABASE_FILENAME)`;
  and `src/cadrumo/core/tests/test_storage_route_classification.py` restates the
  same two names in five separate assertions (lines 25, 51, 81, 98, 120),
  confirmed by direct grep. None references the namespace-registry constants,
  and none would catch the other two drifting. The contrast is
  `CONFIG_RESET_JOURNAL_DIRNAME`, whose deliberate duplicate in
  `src/cadrumo/application/_config_reset_repository.py:27` **is** pinned at
  `src/cadrumo/tests/test_persisted_format_enrollment.py:143` — the shipped
  precedent for a parity gate.

Consequence for the option space: an authority scoped to "the settings fields"
is a smaller thing than an authority scoped to "the locations". The ADR must
choose which it is building, and if the former, must say what governs the rest.
F11 establishes why the choice is forced rather than free.

### F2 — The existing anti-literal gate is structurally blind to every site in F1

**Provenance correction, load-bearing: the gate analysed here is not at HEAD.**
It exists only as uncommitted peer working-tree edit to
`src/cadrumo/core/tests/test_settings_lifecycle_gate.py`. Verified by
`git show HEAD:` on that file: the entire
`test_no_production_module_names_an_operator_data_location_by_literal` section,
with its `_TAXONOMY_VOCABULARY`, `_LITERAL_OWNERS`, and `_production_modules`
support code, is absent from the committed tree. The analysis below therefore
describes a gate that is about to land, not one this campaign inherits.

The gate sweeps production modules with the regex `Path\(\s*"([^"]*/[^"]*)"` and
flags a literal whose segments intersect the taxonomy vocabulary. Two
properties of that predicate bound its reach hard:

- It matches only a `Path("…")` call whose literal **contains a slash**. The
  ad-hoc sites build paths by operator join — `root / "buckets" / bucket_id / "db"`,
  `cadrumo_local_storage_root / _INDEX_SUBDIR` — which the regex cannot see.
- Its vocabulary derives from `_STATE_ROOT_DERIVED_DIRS.values()`, so a segment
  that was never enrolled (`buckets`, `keystore`, `corpus-search`, `telemetry`,
  `active-profile`) is not in the vocabulary and cannot be flagged even if it
  did appear in a slashed literal.
- It excludes test trees entirely (`"/tests/" in rel` is skipped), so a test
  restating a governed name — the five assertions in
  `test_storage_route_classification.py` — is invisible to it.

The gate therefore certifies exactly the sites already enrolled and is silent
on the class it was written to catch. A literal-census gate cannot close this,
and a stricter regex would only chase a syntax the offenders do not use.

**Companion trap for any name-counting gate.**
`src/cadrumo/core/auth_session_keys.py:13` mentions `cadrumo_token_dir` in a
docstring that exists precisely to state the module does *not* use it. A gate
that counts name occurrences inherits this false-positive class. The property
to assert is that resolution goes through the typed accessor, not that a name
is absent from a file.

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

### F20 — Cancelling a browser download does not prevent the bytes reaching disk

The original correction to the submitted-declaration fetch (F15) cancelled the
download once its URL was known and re-fetched the bytes in memory. Direct
measurement showed that shape does **not** close the breach.

The harness was a local `ThreadingHTTPServer` serving synthetic bytes — no AEAT
contact — with a real headless Chromium whose `downloads_path` was observable,
and a 20ms poller. Serving a 6MB payload in 250KB chunks:

- at t=0.354s, **0.107s after the download began**, a `.crdownload` file existed
  on disk holding **250,000 bytes**;
- the server log independently confirmed Chromium had pulled **500,000 bytes**
  over the network before `cancel()` aborted the connection;
- `cancel()` itself took **3ms**, so the window is not a slow-cancel artefact;
- `download.failure()` returned `'canceled'`, confirming a genuine in-flight
  abort rather than a completed download that was cleaned up afterwards.

Chromium removed the file at context close, but taxpayer bytes were on disk
during the window. **Cancel-after-the-fact removes the application's dependence
on the artefact; it does not prevent the artefact.**

The measured closure is `accept_downloads=False` on the browser context. The
download event still fires and `download.url` is still populated — the only
thing the flow needs — while `download.path()` raises and **no file ever
appears**: 0 files across the run, against the transient one in the first
experiment. The production shape (read url, cancel, re-fetch through the
authenticated request context) was reproduced end-to-end against the harness and
returned bytes byte-identical to the payload.

It is set globally in the single context-construction path this adapter uses,
verified at `src/cadrumo/adapters/outbound/aeat/browser/session.py:273`. The
change is behaviour-neutral — the download-consuming site is the only one in the
codebase and nothing listens for a download event — and refuse-by-default is
strictly safer than the silent accept-to-an-unread-temp-file default for any
download a future change might trigger. Landed as commit
`fix(sede): refuse downloads at the browser context so bytes never touch disk`,
confirmed present at HEAD with its behavioural test.

**The reusable lesson, and why it was hard to see:** a fix that removes our
*dependence* on an artefact is not a fix that *prevents* the artefact. The two
are easy to conflate precisely because the code stops mentioning the file — the
symptom of the weaker fix is that the artefact disappears from the source, not
from the disk. Only measurement distinguished them; the documentation was
ambiguous and both readings were defensible from the prose alone.

### What was not investigated

The untriaged tail of test files in F16 was not individually confirmed; an
estimate is not an acceptable closing state for the migration mandate and that
triage is being run separately. `dev/docs/tests/test_env_reference.py` was not
read, and it gates drift between the generated environment reference and the
settings fields, so a field rename would trip it. Whether the `blobs` and
`audit` name collision across depths has ever caused a real defect was not
investigated; both work correctly today. Whether the registry-disk-cache
fingerprint churn (F18) has produced observed spurious replay refusals in
practice was not investigated — only that the digest demonstrably moves. Whether
any other browser-mediated flow in the tree could trigger a download was not
exhaustively swept; F20's context-level refusal makes that safe by default
rather than by inventory.

### F18 — No derivation reproduces the fingerprint-exclusion set, and the shipped set has a proven gap

`data_root_cache_exclusions` (`src/cadrumo/core/observability/_fingerprint.py:163`)
returns 8 resolved directories that `_hash_tree` prunes during the walk. Its
docstring states the semantic axis: the excluded locations are regenerable,
self-referential, or non-canonical duplicates, and carry no taxpayer state a
replay must detect drift in. Three distinct reasons are given — self-reference
(the observability run directory would make each digest depend on the previous
run), regenerable-with-no-taxpayer-state (the LLM and status and corpus and
verdict caches), and non-canonical duplicate (backups of state already
fingerprinted at its primary location).

**Every candidate derivation was enumerated against the shipped set and all
fail, in both directions:**

| candidate | size | delta versus shipped set |
|---|---|---|
| retention ∪ TTL | 7 | misses corpus-text, validation-verdict, backups; wrongly adds registry-disk-cache, wallet-diagnostic |
| `cache/` grouping | 4 | misses llm-usage, llm-run-telemetry, runs, backups |
| `cache/` ∪ retention ∪ TTL | 9 | misses backups; wrongly adds registry-disk-cache, wallet-diagnostic |
| retention alone | 6 | misses status-cache, corpus-text, validation-verdict, backups; wrongly adds two |

So participation is a genuinely independent axis. Deriving it from lifecycle or
grouping would silently change what the replay-refusal mechanism treats as real
state drift — and the mechanism's own docstring records the historical defect
where `db_sha256` degraded to the empty-tree constant for every installed
operator, permanently defeating drift detection.

**A latent gap in the shipped set, proven by measurement with a positive
control.** Using a real temporary storage root and the production functions:

- writing a file into an excluded directory (the LLM cache) left the digest
  unchanged — the positive control, proving the exclusion mechanism works and
  the probe can detect a no-op;
- writing a file into `cache/registry`, the production location of the compiled
  registry pickle, **changed the digest**.

The registry disk cache is therefore fingerprinted today. It is a regenerable
cache rewritten on every registry recompile, so it churns `db_sha256` and
produces spurious replay refusals — the exclude-too-little failure mode. The
omission is explainable: `cadrumo_registry_disk_cache_dir` defaults to `None`,
and the exclusion function resolves each entry unconditionally, so the field
could not be added to the tuple without handling `None`.

The consequence for the campaign is that the shipped 8-field set is not the
*correct* set, only the *current* one. Declaring participation per member
surfaces the gap; the declared set should differ from today's by adding the
registry disk cache. That is a deliberate correction, not a regression to be
"restored to parity".

### F19 — The two opt-in retention fields are not alike under the escape test

The two lifecycle-classified fields outside the taxonomy behave differently
against the choose-and-write questions:

- `cadrumo_registry_disk_cache_dir` — when unset, the application itself picks
  `<root>/cache/registry` (`src/cadrumo/domain/calculations/registry/_loader_cache.py:230`)
  and writes the compiled pickle there. It chooses **and** writes, so it is not
  an escape. Its `None` default is an override affordance, not an absence of an
  application-chosen location. Note the constraint: the three-branch resolver
  depends on the field being `None` to select its pytest branch, so the *name*
  can be taxonomy-governed while the *field* must not be auto-derived by the
  settings validator.
- `cadrumo_wallet_diagnostic_dump_dir` — when unset, the feature is off and
  there is no application-chosen location at all; when set, the operator names
  the destination. It fails the choose test and is a genuine escape, but of a
  role none of the four declared roles covers: it is an operator-directed
  *output* destination, not a bundled resource, operator input, third-party
  cache, or external executable.

### What was not investigated

The untriaged tail of test files in F16 was not individually confirmed; an
estimate is not an acceptable closing state for the migration mandate and that
triage is being run separately. `dev/docs/tests/test_env_reference.py` was not
read, and it gates drift between the generated environment reference and the
settings fields, so a field rename would trip it. Whether the `blobs` and
`audit` name collision across depths has ever caused a real defect was not
investigated; both work correctly today. Whether the registry-disk-cache
fingerprint churn (F18) has produced observed spurious replay refusals in
practice was not investigated — only that the digest demonstrably moves.

### F11 — The duplicate literals are a layering symptom, and they foreclose the obvious fix

The canonical bucket-layout constants live in
`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:31`. All three
unpinned copies live in `src/cadrumo/core/`. "Just import the constants" would
make **core import from adapters**, inverting the hexagonal direction
`aeat-architecture-boundaries` mandates. That is almost certainly why the
literals were retyped: someone hit the layering wall and typed the string.

The wall is real and consciously maintained, not incidental:
`src/cadrumo/core/secure_object_write.py:9` documents that it names a storage
concept "without importing the `cadrumo.adapters` layer", i.e. the codebase
already treats core-to-adapters as a boundary it works around by design.

This makes the duplication a symptom of the names living in the wrong layer
rather than sloppiness for a burndown to tidy, and it constrains the
representation ruling directly. `aeat-architecture-boundaries` requires the
closed value set to be declared in `core/`; if the taxonomy lives in core and
the bucket-layout names do not, the three copies stay unfixable without an
upward import. Federating the two layers while leaving the bucket names in
`adapters/` therefore leaves both the layering violation and the duplication
standing.

### F12 — Lifecycle is not one axis but three, and folding it naively narrows a gate

The 28 taxonomy entries partition cleanly across the five lifecycle frozensets,
which superficially supports folding the classification onto a category member.
Two measured cross-cuts defeat it:

- **Scope mismatch.** The gate classifies every `_dir`/`_path`/`_root`
  `Path`-typed `Settings` field, a strictly larger set than the 28: it also
  covers 2 opt-in retention fields and 5 exempt-input fields, 35 in total. A
  field on a category member cannot classify a non-category field. A naive fold
  would silently narrow the gate's coverage from 35 fields to 28 **and the gate
  would still pass**, which is why this must be ruled explicitly rather than
  left to the implementer.
- **An independent third axis.** `data_root_cache_exclusions`
  (`src/cadrumo/core/observability/_fingerprint.py:163`) selects 8 fields by
  name for exclusion from the drift fingerprint. That set equals neither
  retention, nor retention united with TTL, nor any other existing
  classification: it drops `cadrumo_registry_disk_cache_dir` and
  `cadrumo_wallet_diagnostic_dump_dir` (which are pruned but still count toward
  drift detection) and adds `cadrumo_corpus_text_cache_dir`,
  `cadrumo_validation_verdict_cache_dir`, and `cadrumo_storage_backup_dir`
  (which are unbounded-by-design yet excluded). No single axis predicts it.

So the typed model needs category membership, lifecycle class, and
fingerprint-exclusion as three orthogonal axes, and the lifecycle gate must
keep enumerating `Path`-typed settings fields rather than taxonomy members.
Deriving the exclusion set from any existing axis would silently change what
the replay-refusal safety mechanism treats as real state drift.

### F13 — The lifecycle gate is red at committed HEAD, and a peer owns the fix

`src/cadrumo/core/config.py` at HEAD declares `cadrumo_filed_declarations_dir`,
`cadrumo_iva_compensation_history_dir`, and `cadrumo_iva_read_evidence_dir` in
the taxonomy (9 occurrences confirmed via `git show HEAD:`), while HEAD's
lifecycle gate classifies none of them (0 occurrences, same method). HEAD's
coverage assertion therefore fails naming exactly those three.

The peer's uncommitted edit adds precisely those three classifications, with
their justifying rationale, plus the literal gate of F2. It is an active fix
for a currently-red committed gate, not a stylistic improvement. **Consequence
for planning: no implementation lane may edit that file** — a peer owns it
mid-flight, and an edit over it would collide with work already in progress.

### F14 — The taxonomy governs the top of a category, not what is written beneath it

Production code nests further ad-hoc subdirectories under enrolled categories:
`src/cadrumo/application/live/_iva_remote_state.py:677,736` writes
`cadrumo_audit_dir / "live" / "iva-wallet"` and `… / "live" / "iva-remote-state"`;
the rotation planner reaches `"amendments"` and `"amendment-results"` under
submissions and `"manifests"` under attachments. None is a taxonomy entry.

A typed top level with an ungoverned free-for-all one directory down is the
same defect at a different depth, and it also bears on the CRUD surface: a
prune or relocate verb must account for content nested arbitrarily deep beneath
a category by code the taxonomy cannot see.

### F15 — Three data-safety findings are already being fixed in-flight by peers

Each was real at HEAD and each is now corrected in the working tree, verified
by diffing HEAD against the working copy:

- **Review-package staging.** At HEAD both
  `src/cadrumo/application/modelo/_review_package.py:270` and
  `src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py:287` call
  `TemporaryDirectory` with no `dir=`, staging plaintext fichero-BOE bytes, the
  full calculation revision JSON, and the ledger filing evidence JSON in the OS
  temp directory. The working tree pins both to `output.parent` /
  `output_path.parent` with a comment citing the sensitive-data rule, and
  creates the parent first so a failure refuses loudly rather than falling back
  to OS temp.
- **Submitted-declaration download.** At HEAD
  `src/cadrumo/adapters/outbound/aeat/sede/_declarations_fetch.py` reads
  `await download.path()` and then the file, so Playwright materialises
  taxpayer-filed bytes to its own temp location. The working tree cancels the
  download as soon as its URL is known and re-fetches the bytes in memory
  through the authenticated request context — the same shape the sibling
  justificante capture already used.
- **Lifecycle classification.** F13.

These are the correct fixes and the correct rationale. They are recorded here
so the campaign ratifies them rather than commissioning them a second time, and
so no lane edits the owning files.

### F16 — The test surface is the larger half of the migration

201 test files call `override_settings(`, of which **108 pass a genuinely
path-valued argument** across **263 kwarg occurrences**; the other 93 are
non-path only and are untouched by this campaign. 24 project conftests
participate and 28 `dev/` files reference the storage root.

**Two isolation tiers, with different dispositions.** They are easy to conflate
and the conflation misdirects the migration:

*Tier one — collection-time bootstrapping, exempt.*
`src/cadrumo/tests/_collection_storage_root.py` derives a per-process root under
the OS temp directory; the repo-root conftest applies it with `overwrite=False`
before anything can resolve settings, and `src/cadrumo/conftest.py:41` re-applies
it with `overwrite=True`. Verified directly: the module imports **only stdlib**
(`atexit`, `os`, `shutil`, `time`, `pathlib`, `tempfile`), sets **only**
`CADRUMO_LOCAL_STORAGE_ROOT`, and names **no taxonomy leaf** — a grep for leaf
names returns one hit which is the ordinary English word "runs" in prose, a
substring false positive. The one field it touches,
`cadrumo_local_storage_root`, is classified exempt input by the lifecycle gate
precisely because it is the container rather than a categorised child.

Its concern — do not resolve settings during collection on a machine that may
carry retired-product state — is genuinely orthogonal to what lives under the
root. It is not a refactor target and it is not a migration destination:
**nothing migrates onto it**, because it has no application imports by design.

*Tier two — the shared isolation fixtures, the actual target.*
`secure_sql.py`'s `isolated_cli_backend`, `isolated_profile_storage_root`,
`isolated_runtime_profile`, `isolated_cli_runtime_profile`, and `env_scope.py`'s
`isolated_aeat_env` and `settings_without_env_file` isolate the whole root once
per test rather than a field at a time. They are the right consolidation target
— **and they hand-roll per-field literals themselves**. Verified:
`isolated_cli_runtime_profile` overrides five fields with bare literals
(`runs`, `drafts`, `tokens`, `txs`, `invoices`), and `txs` does not match the
taxonomy's `financial/transactions` for that category. Roughly 10 such
fixture-internal sites; migrating them first is what makes the larger sweep
coherent rather than a sweep onto a drifting target.

*The larger opportunity, named and not taken.* Beyond those fixtures, roughly
350+ call sites hand-roll per-field override blocks duplicating what the
fixtures already provide. Re-pointing each to the accessor satisfies the
mandate; converting them to **use the shared fixtures instead** would be better
engineering and is a separate design conversation about fixture ergonomics.
Recorded so neither the expansion nor the omission happens silently.

### F21 — The lifecycle gate can be made to pass on nothing, but only after this campaign's own rewrite

The gate discovers its subject structurally: `_path_typed_fields()` introspects
`Settings.model_fields`, and the literal-vocabulary support derives from
`_STATE_ROOT_DERIVED_DIRS.values()`. A structural discovery that finds nothing
yields assertions over empty sets.

The hazard is **conditional**, and the condition matters because it inverts the
obvious reading. At HEAD the gate is safe: if path fields moved off flat
`Settings` attributes, `_path_typed_fields()` would shrink while the
hand-maintained frozensets stayed populated, so the stale-entry assertion
(`classified - path_fields`, `test_settings_lifecycle_gate.py:143`) would fire
and the gate would red.

R4 deletes those frozensets and derives classification from the taxonomy. **At
that point both sides of the comparison move together**: a discovery finding
nothing compares an empty subject against an empty classification and passes.
The independent oracle disappears at precisely the moment the gate stops
hand-maintaining its own list — which is the moment nobody is watching for it.

Two consequences, both recorded as requirements rather than warnings: path
fields stay flat-introspectable on `Settings` as a stated design constraint, and
the binding gate carries a non-empty-discovery assertion so the vacuous pass is
impossible regardless of how the taxonomy is shaped. The general form is worth
stating: **a structural gate that discovers its own subject must assert that it
discovered something.**

### F17 — Twelve migration invariants a naive refactor would silently break

Recorded compactly because each has a dependent site and a concrete failure
mode; the sharpest are:

- Relative overrides anchor to the platform user-data root, **one level above**
  the storage root, not to the root itself — conflating the two moves real
  operator data for anyone using a relative override.
- Absolute overrides pass through unchanged, with no containment check.
- An explicit override wins via `model_fields_set`, never via a `None` or
  sentinel comparison; a typed accessor that unconditionally reassigns derived
  paths clobbers every operator override.
- `ensure_storage_tree` is idempotent and non-destructive, and its refusal names
  the path *and* diagnoses "occupied by a file"; a CRUD verb that removes and
  recreates for a "clean state" destroys content on second call.
- `override_settings` pops derived fields not explicitly overridden when the
  root changes, so they re-derive under the new root. Every isolation fixture
  depends on this; if the key space changes without updating that loop, other
  fields stay frozen at the previous root and each test still "passes" against
  a stale path.
- The settings cache keys on a pointer fingerprint that re-reads the root env
  var directly, a second independent root resolution.
- The pointer-file import inside the database-URL validator must stay deferred
  and submodule-qualified, or a half-initialised package raises intermittently.
- Root permission hardening applies to the root only and has **no test
  asserting the mode bits** — a refactor could drop it silently.

### What was not investigated

The untriaged tail of test files in F16 was not individually confirmed; an
estimate is not an acceptable closing state for the migration mandate and that
triage is being run separately. `dev/docs/tests/test_env_reference.py` was not
read, and it gates drift between the generated environment reference and the
settings fields, so a field rename would trip it. Whether the `blobs` and
`audit` name collision across depths has ever caused a real defect was not
investigated; both work correctly today.

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
