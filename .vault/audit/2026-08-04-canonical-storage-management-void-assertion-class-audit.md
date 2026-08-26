---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:d109160f0cfa6a20f49b4ea64cc5574b42bf1bd9e872db1558fae7be9068dabf'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

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

**Correction, credited to a peer review pass:** `test_storage_substrate_state_root.py:43`
carries `PINNED_TAXONOMY_LITERALS = frozenset({"secrets"})`, and the module docstring states
the literal is deliberate — "the independent oracle for what `cadrumo_secret_store_dir`
defaults to when unoverridden, not scaffolding." The mutation-confirmed void behaviour still
holds as a fact (line 41 dies first, so line 43 has never executed), but the correct
classification is **declared, resolved risk acceptance, not residue** — the author already
traded off the exact property this audit tests and said why. `test_fast_path_no_state.py`
carries no such declaration for either line and is the sole confirmed, undeclared void in
this audit — the highest-severity finding here, not one of two.

### void-assertion-class | medium | AST sweep: 19 raw hits, 3 false positives, 6 declared/resolved, 10 undeclared

An AST sweep for the three assertion shapes above, restricted to a taxonomy-vocabulary
segment literal composed independently of `storage_path(StorageCategory...)`, returned 19
hits across the test corpus. Three (`entrypoints/mcp/tests/test_persona_scope.py:96,111,119`,
all `"live" not in scope.families`) are false positives: an MCP persona-command-family
scope check, unrelated to the storage taxonomy's `live/` audit subpath — same word, different
owner, excluded before counting. 16 remain genuine.

**Enrollment check, credited to a peer review pass that found one of this audit's own
confirmed voids was a declared pin (above).** Every genuine hit's module was checked for
`PINNED_TAXONOMY_LITERALS`, and — per the caution that a module-level pin is a weaker test
than confirming the declaration covers the SITE's own literal — each candidate's docstring
was read to confirm it names the specific assertion, not just the module in general. Six of
sixteen are declared, resolved risk acceptance, not residue:
- `application/live/tests/test_expedientes.py:257`, `test_notifications.py:294`,
  `test_verify.py:330` each pin `{"live"}`, and each module docstring names the exact
  assertion verbatim: "An accessor aimed at the wrong location would leave that assertion
  trivially satisfied — the exact silent-pass shape a refusal test must not risk — so the
  literal stays." Same reasoning, same author pattern, as the `SECRETS` pin above. These
  also carry the `W05.P22.S115` dormancy-proof shape (nested `cadrumo_audit_dir / "live" /
  "<domain>" / "<bucket_id>.jsonl"` never appears, right after proving the data went to SQL)
  — flagged for that cross-reference, but resolved as void risk.
- `core/tests/test_storage_route_classification.py:131,144` — the module pins
  `{"cadrumo.db", "buckets", "db", "active-profile"}`, and its docstring names these two
  `not (... / "cadrumo.db").exists()` refusals by the identical reasoning: "An accessor
  aimed at the wrong location would leave that assertion trivially satisfied."

Ten of sixteen remain **undeclared** — no `PINNED_TAXONOMY_LITERALS` in the module at all:
- Two are the confirmed void from the previous finding: `test_fast_path_no_state.py:107,118`.
  This is now the audit's sole confirmed, undeclared void — its severity stands as reported.
- Six are **analogous** to the `cadrumo.db`/`SECRETS` mechanisms measured today, not
  independently mutation-tested: `adapters/persistence/storage/sql/tests/test_engine.py:194`,
  `adapters/persistence/storage/tests/test_cadrumo_state_identity_acceptance.py:96`,
  `entrypoints/cli/tests/test_root_fallback_write_guard.py:201,272`,
  `tests/test_secure_sql.py:154` (the undeclared remainder of the `cadrumo.db`
  refusal-guard shape once the two declared `test_storage_route_classification.py` lines are
  removed), plus `core/tests/test_token_dir_state_root.py:77` (`cadrumo_token_dir !=
  storage_root / "tokens"`, the same override-precedence-negation shape as the `SECRETS`
  void).
- Two are **pattern-matched only**, unverified, no pin found in either module:
  `adapters/outbound/aeat/export/tests/test_engine.py:77` (`not (tmp_path /
  "submissions").exists()` beside `not hasattr(engine, "submit_draft")`, a capability-absence
  claim) and `adapters/persistence/storage/blob_store/tests/test_blob_store.py:457` (a
  refusal guard on one specific obstructed write — transient, not a permanent claim, so a
  different severity than the persistent-claim sites above even if it does void).

(Corrected post-commit, separately from the enrollment pass: this set was first reported to
the team as "16 genuine, nine pattern-matched-only" — a subtraction never checked against
the actual enumeration, which only ever listed five. The five-vs-nine error and the
six-declared/ten-undeclared enrollment correction are independent fixes landing in the same
revision.)

### void-assertion-class | medium | the sweep's own blind spot is demonstrated, not theorised — measured today

The AST sweep matches only a segment literal appearing directly inside the asserted
expression. It cannot see a void built from a helper function's *internal* literal composed
elsewhere and only compared by its output — which is exactly the shape of
`_hash_bucket_tree`, the sweep's own missed site. The sweep's 16-candidate count is
therefore a floor, not a population, in a direction the instrument cannot itself measure:
the true void count is larger, and no further AST pass over this codebase will find the next
instance of this shape without a differently-designed detector (e.g. one that resolves
literals through called helper functions before comparing).

### void-assertion-class | high | the blind spot is bounded, not just named — credited, denominator measured by a peer review pass

The prior finding named the blind spot; a peer review pass bounded it by enumerating the
**denominator** rather than searching for more voids — every absence assertion in the test
tree is AST-visible whether or not the path it checks is, so the miss rate can be bounded
without finding a single additional void. Measured against all 400
`assert not <expr>.exists()/.is_file()/.is_dir()` / `assert not any(...)/list(...)`
assertions in the test tree:

```
400  absence assertions total
 19  inline taxonomy literal      <- this audit's AST sweep, all it can see    4.75%
 13  accessor-resolved            <- rename-safe by construction
 58  helper-routed                <- the blind spot named above
  8  local-variable-held literal  <- a SECOND blind spot, named below
 89  unresolved, module mentions a taxonomy token
213  module names no taxonomy token  <- provably excluded
```

**155 candidates (58 + 8 + 89) need examination; 213 are provably excluded; 13 are already
safe.** The 213-exclusion is sound in the conservative direction even though the underlying
token set is known to over-match on homonyms elsewhere in this campaign (the constrained
detector's false-positive history): a permissive token set makes "this module mentions no
token at all" a *stronger* negative claim, so the error direction is toward over-including
into the 155, never toward wrongly excluding into the 213.

**A second blind spot, distinct from the helper-routed one:** a literal can also reach an
assertion through a local variable assignment rather than a function call —
`bucket_dir = tmp_path / "buckets" / bucket_id` followed by `assert not bucket_dir.exists()`
elsewhere in the same test. A scan extended to resolve helper-function bodies would still
miss this shape; it is a different hop, and 8 direct instances were counted, with an unknown
share of the 89 unresolved-but-token-mentioning bucket likely following this pattern too.

**Extrapolation caution:** this audit's 19-hit sample is 4.75% of the 400-assertion
population. A candidate rate estimated from that 19 is not evidence about the other 95% —
the same trap the constrained detector fell into, where its unread discard pile turned out
23% positive against a 0% prior from the visible slice. Any future extrapolation of the void
class must sample from the 155-candidate population, not from the 19 this sweep happened to
surface.

## Recommendations

Do not remediate any site from this audit yet; disposition is a scoping decision for a
follow-on plan, not a cleanup folded into this one.

**Six declared sites need no action.** `test_expedientes.py:257`, `test_notifications.py:294`,
`test_verify.py:330`, and `test_storage_route_classification.py:131,144` (plus the
`SECRETS` site in the earlier finding) already carry a `PINNED_TAXONOMY_LITERALS`
declaration whose docstring names the exact site and the exact tradeoff. Re-flagging these
in a follow-on pass would be re-litigating a decision already made and documented; note them
here so a future reader does not.

**`test_fast_path_no_state.py:107,118` is the sharpest open finding** — the sole confirmed,
undeclared void in this audit. A follow-on ADR should decide whether it is re-expressed
through the taxonomy accessor or re-pinned with the void risk stated in-docstring, informed
by the corrected framing: it is a coverage-gap risk today, not an active leak.

**Ten remaining undeclared candidates need triage, at two different levels of confidence.**
The 5 analogous-mechanism sites (`test_engine.py:194`[sql],
`test_cadrumo_state_identity_acceptance.py:96`, `test_root_fallback_write_guard.py:201,272`,
`test_secure_sql.py:154`) plus `test_token_dir_state_root.py:77` share a mechanism measured
today but were not individually mutation-tested; the 2 pattern-matched-only sites
(`test_engine.py:77`[export], `test_blob_store.py:457`) were not tested at all. `census` is
running individual mutation verification on the corrected 5-site pattern-matched-only list
now.

**The wider 155-candidate population (of 400 total absence assertions, measured separately)
is the real scoping surface**, not this audit's 19-hit sample — any follow-on estimate of
the true void count must sample from the 155, not extrapolate from the 19. A structural gate
was proposed (not yet built or measured) as a closing mechanism rather than a perpetual
detection problem: an absence assertion in a module that mentions a taxonomy token must
either route through `storage_path(...)`/`bucket_scoped_storage_path(...)` or carry a
`PINNED_TAXONOMY_LITERALS` declaration whose docstring names the specific site — both are
cheap AST facts requiring no callee-body analysis, avoiding the failure mode that retired the
constrained detector earlier in this campaign.
