---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:40835e51a76659ca3a30059ffd62e38a2bc0ac4418275290c952493dbea309d5'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
  - "[[2026-08-03-canonical-storage-management-W05-P22-S115]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `canonical-storage-management` audit: `void assertion class`

## Scope

A prior sweep (`W05.P22.S115`) proved four taxonomy-declared locations dormant by writing
new test-authored assertions of the shape "persist through the production repository, then
assert the plaintext location was never touched." That work assumed the pre-existing test
corpus's own absence/inequality/membership assertions were reliable checks in the meantime.
This audit tests that assumption directly: for a sample of assertions built from a
taxonomy-vocabulary string literal composed independently of the `storage_path` accessor,
does the assertion still pass after the referenced taxonomy segment is renamed — for a
reason unrelated to the property it claims to verify?

Five taxonomy-segment mutations were run against the live tree (`BUCKETS`, `SECRETS`,
`CORPUS_TEXT_CACHE`, `ROOT_FALLBACK_DATABASE`'s filename), each isolated to a single-line
change in `core/_storage_taxonomy_locations.py`, backed up via `git show HEAD:<file>`,
applied, exercised against only the targeted tests, then restored and verified
byte-identical to `HEAD` before the next mutation. An AST sweep then searched the wider test
corpus for the same three assertion shapes (`not (...).exists()/.is_dir()/.is_file()`, `!=
<literal>`, `"<segment>" not in <listing>`) built from a segment literal without the
accessor, as a biased inventory of further candidates — not an exhaustive population.

Every claim below is graded **measured today** (a mutation was actually run and observed),
**analogous** (matches a mechanism proven by a measured site, not independently mutated), or
**pattern-matched only** (surfaced by the AST sweep, unverified).

## Findings

### void-assertion-class | high | five predicted-break sites: four broke, one was void — measured today

Of the five sites nominated as rename-sensitive (`test_profile_bucket_scan.py:20,84`,
`test_corpus_text_cache_location.py:42`, `test_config.py:405`,
`test_sessions_storage_state_paths.py:145`), four broke under mutation exactly as predicted.
The fifth did not: `test_provider_logout_leaves_unrelated_bucket_session_bytes_identical`
and its sibling `test_all_provider_reset_...` passed clean under the `BUCKETS` rename. The
prediction was corrected by measurement, not assumed correct and left unverified.

### void-assertion-class | critical | empty-hash equality is a new vacuity sub-class — measured today

`_hash_bucket_tree` (`test_sessions_storage_state_paths.py:143-152`) composes
`storage_root / "buckets" / bucket_id` — a literal, independent of the `BUCKETS_DIRNAME`
accessor real production code uses — and hashes every file found under it. Under the
`BUCKETS` rename, real bucket data moves to `buckets-mutated/`; the literal path never
existed, `rglob("*")` on it yields nothing, and `hashlib.sha256()` with zero updates
produces the fixed empty-input constant (`e3b0c442...`, confirmed by direct computation).
`unrelated_before` and `unrelated_after` are both that constant, so `assert unrelated_after
== unrelated_before` passes for a reason that has nothing to do with bucket B's real data
staying untouched. Generalises: **any assertion comparing two hashes/digests of a path that
stops existing degenerates to comparing a fixed constant to itself** — a distinct entry
point into vacuity from the "wrong path silently satisfies a negative" shape the earlier
`ATTACHMENTS`/`DRAFTS`/`JUSTIFICANTES` work and the fast-path sites share.

### void-assertion-class | high | two predicted-void sites, both confirmed, one overstated in the brief — measured today

`test_storage_substrate_state_root.py:43` (`cadrumo_secret_store_dir != REPO_ROOT /
"var" / "secrets"`) is void: the preceding assertion at line 41 (`== storage_root /
"secrets"`) breaks first under the `SECRETS` rename, so line 43 has never once executed
since the module was written, in any taxonomy state — not drift, void from birth. Confirmed
both by independent evaluation of each operand and by running the real test through pytest.

`test_fast_path_no_state.py:118` (and its sibling at line 107) passed clean under the
`BUCKETS` rename, confirming the void. But the framing that this represents a live,
currently-active leak was checked and found overstated: `--help` under the mutated taxonomy
was run and the full storage root enumerated — nothing was created, under either the old or
the renamed name. The void is real as a **coverage-gap risk** (a future regression writing
under the real taxonomy name would go undetected by this literal), not a presently-occurring
defect.

### void-assertion-class | medium | AST sweep: 19 raw hits, 3 same-word-different-owner false positives, 16 genuine candidates

An AST sweep for the three assertion shapes above, restricted to a taxonomy-vocabulary
segment literal composed independently of `storage_path(StorageCategory...)`, returned 19
hits across the test corpus. Three (`entrypoints/mcp/tests/test_persona_scope.py:96,111,119`,
all `"live" not in scope.families`) are false positives: an MCP persona-command-family
scope check, unrelated to the storage taxonomy's `live/` audit subpath — same word, different
owner, excluded before counting. 16 remain as genuine candidates; none beyond the two
confirmed above were mutation-tested individually.

Two sub-clusters are **analogous** to a mechanism measured today, not independently proven:
- Seven line-locations across five files (`adapters/persistence/storage/sql/tests/test_engine.py:194`,
  `adapters/persistence/storage/tests/test_cadrumo_state_identity_acceptance.py:96`,
  `core/tests/test_storage_route_classification.py:131,144`,
  `entrypoints/cli/tests/test_root_fallback_write_guard.py:201,272`,
  `tests/test_secure_sql.py:154`) all share the shape `assert not (X / "cadrumo.db").exists()`
  immediately after a refusal (`pytest.raises`, "No active profile"). Same mechanism as the
  confirmed `test_config.py:405` mutation: a `ROOT_FALLBACK_DATABASE`-filename rename leaves
  every one of these checking a name nothing would ever create, refusal or not.
- `core/tests/test_token_dir_state_root.py:77` (`cadrumo_token_dir != storage_root /
  "tokens"`) is the same override-precedence-negation shape as the confirmed `SECRETS` void:
  a negative check that stays true regardless of whether the precedence logic underneath it
  does anything.

The remaining five are **pattern-matched only**, unverified. (Corrected post-commit: this
was first reported to the team as "nine," a subtraction — 16 minus the analogous cluster —
that was never checked against the actual enumeration below, which only ever listed five.
16 genuine hits = 3 confirmed-today + 8 analogous + 5 pattern-matched-only.)
- Three (`application/live/tests/test_expedientes.py:257`,
  `test_notifications.py:294`, `test_verify.py:330`) check a nested
  `cadrumo_audit_dir / "live" / "<domain>" / "<bucket_id>.jsonl"` never appears, immediately
  after proving the real data went to the SQL side — the same shape as the `W05.P22.S115`
  dormancy proofs, not this void class. Flagged here for cross-reference only; disposition
  belongs with the dormancy work, not this audit.
- `adapters/outbound/aeat/export/tests/test_engine.py:77` (`not (tmp_path /
  "submissions").exists()` alongside `not hasattr(engine, "submit_draft")`) is a
  capability-absence claim, structurally close to the dormancy class as well.
- `adapters/persistence/storage/blob_store/tests/test_blob_store.py:457` is a refusal guard
  on one specific obstructed write, not a permanent claim — void-prone under a `BLOBS`
  rename but a different severity than the persistent-claim sites above.

### void-assertion-class | medium | the sweep's own blind spot is demonstrated, not theorised — measured today

The AST sweep matches only a segment literal appearing directly inside the asserted
expression. It cannot see a void built from a helper function's *internal* literal composed
elsewhere and only compared by its output — which is exactly the shape of
`_hash_bucket_tree`, the sweep's own missed site. The sweep's 16-candidate count is
therefore a floor, not a population, in a direction the instrument cannot itself measure:
the true void count is larger, and no further AST pass over this codebase will find the next
instance of this shape without a differently-designed detector (e.g. one that resolves
literals through called helper functions before comparing).

## Recommendations

Do not remediate any site from this audit yet; disposition is a scoping decision for a
follow-on plan, not a cleanup folded into this one. A follow-on ADR should decide: whether
the seven-line `cadrumo.db` refusal-guard cluster and `test_token_dir_state_root.py:77` are
re-expressed to route through the taxonomy accessor (closing the void at the cost of the
accessor-equals-itself tautology risk this campaign has repeatedly had to reason through
elsewhere) or re-pinned as deliberate independent-oracle literals with the void risk stated
in-docstring; whether the five pattern-matched-only candidates warrant individual mutation
verification before any edit, given two of five and two of two predictions in this pass
diverged from measurement; and whether the three `cadrumo_audit_dir / "live" / ...` sites
and the `submissions` capability-absence site should be folded into the `W05.P22.S115`
dormancy-proof lineage rather than treated as void risk.
