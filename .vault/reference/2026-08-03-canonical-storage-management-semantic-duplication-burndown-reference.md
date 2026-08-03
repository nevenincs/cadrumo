---
tags:
  - '#reference'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ccee6efa89970b42ef1baaa664f4ef1da78939162d7060821b864647347feae2'
related:
  - "[[2026-08-03-canonical-storage-management-adr]]"
---

# `canonical-storage-management` reference: `semantic duplication burndown inventory`

The explicit burndown target for the operator mandate that every same-meaning,
different-code storage site is in scope. This is the campaign's definition of
done for the semantic-duplication half of the work: a plan cites cluster
identifiers from here, and a reviewer checks a completed migration against the
per-cluster target below.

Discovery was by meaning (`vaultspec-rag search --type code`, many behavioural
phrasings) with every candidate then pinned and read at `file:line`. The
substitutability pre-filter was applied before any CONVERGE verdict: a site is
promotable only when the canonical implementation's constraint shape is a
superset of the site's own. Claims marked verified below were re-measured
directly against the working tree on 2026-08-03; peer WIP is called out where it
changes what a reader would see.

The decision this inventory serves is `2026-08-03-canonical-storage-management-adr`;
the evidence behind its rulings is `2026-08-03-canonical-storage-management-research`.

## Summary

### Reading a verdict

- **CANONICAL** — the site other members converge onto. No work.
- **CONVERGE** — real duplication, safely substitutable, carries a concrete
  target below. This is the burndown.
- **CONSTRAINT-DIVERGENT** — looks like duplication, is not promotable, and the
  reason is recorded. **These matter as much as the inclusions**: they are how a
  later reader verifies nothing inconvenient was silently dropped, and how a
  future agent avoids "fixing" a divergence that exists for a reason.

### Totals

| axis | clusters | CONVERGE sites | CONSTRAINT-DIVERGENT | new primitives |
|---|---|---|---|---|
| paths (P) | 5 | 13 | 3 | 2 |
| lifecycle (L) | 8 | 19 | 7 | 3 |
| **total** | **13** | **32** | **10** | **5** |

Distinct files touched by path-axis CONVERGE sites: 11. The lifecycle read pass
spanned roughly 28 files. The isolation axis has not landed and is not counted
(see the final subsection).

### P1 — Per-bucket keystore sidecar path

*Concept:* the path to a file inside one bucket's separated keystore directory,
after confirming that directory is not nested under `buckets/` or a bucket's
`db/`.

*Canonical:* `keystore_path` and `validate_keystore_separation`, both in
`src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py:29`. The
primitives are already correct and already reused — the duplication is the
two-line validate-then-join **call sequence** wrapping them, not the path math.

*Members:* `master_key/_persisted_session.py:527` (`profile_session_path`),
`master_key/_master_key_bucket_dek.py:27` (`bucket_dek_path`),
`master_key/_login_throttle.py:104` (`login_throttle_path`) — all **CONVERGE**,
byte-identical shape differing only in the filename constant.

*Target:* add `keystore_sidecar_path(root, bucket_id, filename)` to
`_keystore_paths.py`, export from the `bucket` facade, rewrite the three as
one-line callers. Net: three call sites converged, one new primitive.

### P2 — Effective storage root, and a real correctness defect

*Concept:* given an optional caller-supplied root, return the effective storage
root — the override if given, else `load_settings().cadrumo_local_storage_root`.

*Canonical:* none exists. Nominate `effective_storage_root(root: Path | None)`
in `src/cadrumo/core/paths.py`, the module already owning path resolution
against the storage-root anchor.

**This cluster is a correctness defect, not a style cleanup.** Five sites
implement override-else-default and **only one normalizes**. Verified directly:
`expanduser`/`resolve(strict=False)` appears at
`application/user_profile/_profile_pointer_transaction.py:111` and nowhere else
among the standalone sites. The two journal repositories are covered because
`application/_journal_repository.py:80` normalizes one layer down,
unconditionally. The remaining sites can therefore hold a path that compares
unequal to the same location — a relative test override, or a differently-cased
path on Windows, silently fails an identity comparison against a normalized root
elsewhere. That is exactly what the pointer-transaction's normalize step exists
to prevent for re-entrancy checks; the others are exposed to the same bug class
and have merely not been hit yet.

*Members:* `_profile_pointer_transaction.py:109` (**CONVERGE**, and its body is
the reference implementation for the new primitive);
`user_profile/_login_session.py:148`; `workflow/_profile_bucket_scan.py:365`;
`user_profile/_profile_repository.py:180`; and the settings-fallback halves of
`application/_config_reset_repository.py:134` and
`user_profile/_bundle_export_operation.py:225` — all **CONVERGE**.

*Target:* add `effective_storage_root()` with the pointer-transaction body
verbatim; replace all five; delete `_canonical_root`, `_storage_root`, and
`_resolve_root` as named symbols.

*Excluded after verification:* `application/auth/_operator_scope.py:92`
(`_canonical_storage_root`) returns `os.path.normcase(str(...))` — a **string**
comparison key for route classification, never handed to a filesystem call. It
was flagged by an early broad pass and disqualified by reading the body. Do not
re-flag without re-checking its return type.

### P3 — Settings-derived category directory: taxonomy bypass

*Canonical:* the taxonomy itself — `_STATE_ROOT_DERIVED_DIRS`
(`src/cadrumo/core/config.py:96`), its derivation validator (`:1096`), and
`ensure_storage_tree` (`:1370`). Membership buys an env override, tree
provisioning, and correct redirection under a root override in tests.

*Member:* `application/corpus_search/_runtime.py:28` joins a private
`_INDEX_SUBDIR = "corpus-search"` literal onto the root. No settings field
exists, so no override can reach it and the tree is never pre-created — the
module works around that with its own `mkdir` at `:54`, an ad-hoc echo of what
`ensure_storage_tree` does centrally. **CONVERGE.**

*Target:* enroll a corpus-search member, add the matching settings field, delete
the private join and the local `mkdir`, and read the field directly — mirroring
how `registry/_validate_evidence.py:129` already does it for the sibling cache.

### P4 — Optional CLI path option with a bundled or settings default (lower priority)

Four copy-pasted resolvers in `entrypoints/cli/registry.py:141,145,149,159` plus
a more general `getattr`-based sibling at `entrypoints/cli/_app_live.py:101`.
**CONVERGE**, but thin — a shared helper mostly relocates a ternary. Target:
collapse the four into `_resolve_optional_root(value, default_factory)`; leave
the live-output resolver alone or fold it in if the package boundary allows.
Lowest priority in this document; taking it is optional.

### P5 — Bucket-dir-local sidecar signature drift (flagged, not counted)

`bucket/_manifest_io.py:35` and `bucket/_lockfile.py:76` take a `BucketPaths`;
`bucket/_output_language_hint.py:33` takes the raw pair and re-derives it.
**CONSTRAINT-DIVERGENT (signature only)** — `bucket_paths()` is pure, cheap Path
composition with no IO, so re-deriving is an inconsistent calling convention,
not a correctness bug. Align the signature next time the file is touched; not
worth a dedicated step, and deliberately excluded from the burndown total.

### L1 — Atomic single-file write (already converged; reference example)

*Canonical:* `src/cadrumo/core/atomic_write.py` — standard, streaming, text,
best-effort, and hardened tiers, per the accepted data-output ADR. Members call
the tiers rather than reimplementing. **No burndown target.** Cite as the
example of successful convergence.

### L2 — Encrypted secure-object retention prune (already converged)

*Canonical:* `adapters/outbound/llm/_retention.py:27`
(`select_retention_removal_keys`), a pure rank-and-bound function. Members:
`_cache.py:237`, `_usage.py:183`, `_run_telemetry.py:258`. **No burndown
target.**

Worth preserving as a signal: these three **cross-cite each other's docstrings**.
That is what a converged cluster looks like, and it is the direct contrast with
L3, whose four members reference nothing.

### L3 — Raw-filesystem retention eviction: four implementations, no shared helper

The real duplication find of the lifecycle axis. Four independent hand-rolled
implementations of enumerate, rank by mtime, apply a bound, remove the excess,
swallow `OSError`, log:

| site | entity | bound | removal | tie-break |
|---|---|---|---|---|
| `core/observability/_store.py:501` | directories | age then total-size (AND) | `rmtree` | oldest first; newest never size-pruned |
| `adapters/outbound/aeat/sede/_iva_compensation_wallet.py:803` | files | age only | `unlink` | none |
| `entrypoints/mcp/_telemetry.py:132` | `*.jsonl` files | age OR count | `unlink` | newest first by (mtime, name) |
| `domain/calculations/registry/_compiled_cache.py:319` | glob-matched files | count only | `unlink` | newest first by mtime_ns |

*Verdict:* **CONVERGE-eligible**, four sites. The differences — entity type,
bound composition, tie-break — are composable parameters of one primitive, not
hard semantic incompatibilities. Nobody appears to have searched for "prune
files by age" before writing any of the later three.

*Target:* one pure helper mirroring L2's shape —
`select_filesystem_retention_survivors(entries, *, timestamp, cutoff, max_count,
max_total_bytes, size_fn) -> (keep, remove)`. Each caller keeps its own
enumeration and its own removal side effect; only the who-survives decision
converges, pinned by one shared test instead of four.

### L4 — Directory-tree byte-size summation

`core/observability/_store.py:482` (`_run_dir_total_bytes`, tolerates a file
vanishing mid-walk, returns a partial total) and
`application/bucket_maintenance/_service.py:192` (`_directory_byte_total`, also
returns a file count, but has **no** per-file `OSError` tolerance).

*Verdict:* **CONVERGE-eligible with a superset merge**, two sites. Neither
side's extra behaviour blocks the other.

*Target:* one helper returning bytes and file count with opt-in stat-error
tolerance. The bucket-maintenance caller gains that tolerance as a free
correctness improvement — a blob write racing the disk-usage read today raises
unhandled, a small latent bug this convergence also closes.

### L5 — Directory-tree content-hash fingerprint (excluded, opposite safety postures)

Three walkers, each for a different trust boundary:
`core/observability/_fingerprint.py:53` (`_hash_tree`, prunes excluded subtrees,
retries permission errors, drift detection); `core/corpus_manifest/__init__.py:213`
(**skips** symlinks, skips hidden files, excludes its own sidecar);
`application/bucket_maintenance/_manifest_digest.py:56` (**raises** on any
symlink or junction — deletion safety, where a hostile symlink must never
silently vanish from a fingerprint that claims complete coverage).

*Verdict:* **CONSTRAINT-DIVERGENT**, three sites. Skip-a-symlink and
raise-on-a-symlink are opposite deliberate postures. A shared walker would need
`on_symlink`, `exclude_predicate`, and `prune_dirs` as first-class parameters,
and even then the acceptable-divergence lists differ. Three correctly-scoped
implementations of one *shape*, not one *mechanism*. **Do not silently merge the
skip and raise postures.**

### L6 — Stat-based single-file cache key (adjacent; ruled in scope, lowest priority)

`core/paths.py:291` (`file_stat_fingerprint`) returns `(path.name, size,
mtime_ns)` — correct for a same-directory tree fingerprint, adopted at three
sites. Roughly **11** loader modules independently inline the same
stat-and-reraise boilerplate feeding an `lru_cache`, keyed on `str(resolved)`
instead: `domain/user_profile/_loader.py:34`, `domain/iva/_rates.py:60`,
`domain/deadlines/_recargo.py:62`, `domain/categories/_registry.py:53`,
`domain/manuals/_loader.py:97`, `registry/_record_design.py:83,110,123,214`,
`registry/_export_parse.py:205`,
`adapters/inbound/justificante/_parsers/__init__.py:59`,
`adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py:120`.

*Verdict:* CONSTRAINT-DIVERGENT against `file_stat_fingerprint` **as it stands**
— its name-only first element is collision-prone across a global cache spanning
directories, so the inline sites are right to use the full path. But they are
100% duplicated among themselves.

*Target:* add a **path-keyed sibling** (`path_stat_fingerprint`) rather than
changing the existing name-keyed canonical, then converge the ~11 sites onto it.
Ruled in scope as an adjacent, lowest-priority concern. Note two modules
(`_rates.py`, `_registry.py`) already use both conventions in one file, and
`application/filing/runtime.py:475` explicitly documents declining to unify —
evidence the codebase knows about the scope limitation and has not closed it.

### L7 — Trash-rename-then-remove directory

`application/user_profile/_orchestration.py:696`
(`remove_profile_bucket_directory`) and
`application/user_profile/_profile_repository.py:1041`
(`_remove_bucket_directory`). The rename-fallback shape is byte-for-byte
identical **including the exact trash filename format**. The one real difference
— swallow versus propagate on trash-cleanup failure — is a deliberate policy
difference driven by caller context (ordinary delete versus create-rollback) and
is naturally a parameter.

*Verdict:* **CONVERGE-eligible**, two sites.

*Target:* one shared helper beside `_layout.py`'s `provision_bucket_directory`,
its natural sibling (create versus destroy of the same concept), taking the
error policy as an argument.

### L8 — Stage beside destination (positive pattern, no target)

Every production `TemporaryDirectory` staging sensitive bytes now pins `dir=` to
the destination's own parent: `modelo/_review_package.py:285` and
`entrypoints/cli/_modelo_review_package_cli.py:293` (both **peer WIP, verified
uncommitted** — at HEAD they still lack `dir=`), and
`bucket_maintenance/_service.py:1326` (already correct at HEAD).
`user_profile/_bundle_export.py:516` is the cleanest variant, staging via the
hardened atomic-write primitive at a sibling path without a temp directory at
all. **No target** — verify at commit time rather than assuming.

### Verified exclusions beyond the clusters

Recorded so a future pass does not re-litigate them:

- **`bundled_path()` fan-out is healthy.** `registry_root()`,
  `_terminology_root()`, `bundled_corpus_html_root()`, `_bundled_registry_root()`
  are named facades over the one canonical primitive — the intended pattern. The
  distinguishing test: does the candidate call an existing canonical function
  with different arguments (healthy), or re-derive the join itself (candidate)?
- **The Playwright browser root is pinned to a third party's convention.**
  `application/provisioning.py:162` mirrors the platform resolver's shape but its
  macOS branch resolves to `Library/Caches` (Playwright's convention, not
  Cadrumo's `Application Support`) and it honours `PLAYWRIGHT_BROWSERS_PATH`. It
  must match wherever the externally-installed Playwright put its browsers. Not
  promotable. It also passes the re-derives-instead-of-calling test, which is why
  that test is necessary but not sufficient — the constraint check must still run.
- **The secrets tempfile bridge stays separate.**
  `blob_store/_materialisation.py:147` uses `mkstemp` with `0o600` and fd-based
  TOCTOU-safe writes to hand **secrets** (service-account JSON, browser storage
  state) to third-party libraries that require a path. Already reviewed,
  secrets-only, deliberately not financial data. Do not fold into L1.
- **The sealed-archive writer carries a create-only refusal** no atomic-write
  tier has; promoting it would silently drop the no-overwrite guard.
- **`core/paths.py:98`'s hardcoded Windows path-length literal is the one
  documented genuine layering wall** — the module states it duplicates the
  bucket-layout suffix shape because it sits below the persistence layer. This is
  the single place in the sweep where same-meaning-different-code is a
  deliberate, tested trade-off. Note it is dissolved rather than pinned once the
  ADR's ruling moves the bucket-layout names into core.
- **Logical secure-object paths are not filesystem paths.** The `envelope_path` /
  `blobs_dir` / `manifests_dir` properties route through
  `secure_object_logical_path` — display markers for SQL rows, already canonical.
- **`_cli_entrypoints_root()` walks the source tree**, not a data root — a
  different concept entirely.

### Non-clusters: do not enroll

- **`mkdir(parents=True, exist_ok=True)` at roughly 49 sites is NOT duplication.**
  It is the correct one-line stdlib idiom for ensuring a write's own parent
  exists, repeated appropriately per call site, and is qualitatively different
  from the multi-line hand-rolled walkers in L3 through L6. Recorded explicitly so
  a future pass does not generate 49 phantom steps.
- **The two workbook-parity temp directories** (`registry/_workbook_parity.py:493,644`)
  have no `dir=` and look like the review-package pattern, but stage AEAT
  reference workbooks with test-only callers. The substantive check is *what bytes
  are staged*, not the API shape.

### Disposal rulings

- **Dormant categories are deleted, not enrolled** — `cadrumo_storage_backup_dir`,
  `cadrumo_inbox_dir`, `cadrumo_inbox_pdf_dir`, under the pre-release regime and
  delete-not-migrate. **Conditional**: this is contingent on a pending
  confirmation pass establishing zero writers by a method other than a name grep.
  Four independent axes agree they are writer-less, but all four used name-based
  searching, and a name grep is exactly the method that produced a documented
  false positive elsewhere in this campaign. Treat as conditional until that pass
  lands.
- **`cadrumo_registry_disk_cache_dir` enrolls with a declared exception** for its
  `_running_under_pytest()` branch, rather than being forced into static
  resolution or dropped. Its name is taxonomy-governed; its field stays
  resolver-owned because the pytest branch depends on the field being unset. The
  static subpath mechanism genuinely cannot express a conditional, and that is a
  boundary of the taxonomy rather than a defect in this field.

### Corrections found while verifying this inventory

- **The taxonomy has 28 entries, settling a dispute the ledgers left open.**
  Measured directly against the live mapping: 28 entries, of which exactly 1 is a
  file. Any 27 figure is wrong.
- **There is a fifth unpinned `"buckets"` literal**, beyond the four previously
  reported: `application/_journal_repository.py:196` builds
  `(self._storage_root / "buckets").resolve(strict=False)`. It is not pinned to
  the namespace-registry constant and no test would catch it drifting. Add it to
  the set the ADR's unification ruling deletes.

### Not yet covered

The isolation axis (`08`) had not landed when this document was written and is
not represented here. It is expected to cover test-fixture and conftest
duplication, which the migration mandate binds identically to production. This
document must be extended when it lands — its absence is a known gap in the
burndown target, not a statement that the axis is clean.
