---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S18'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Execute the settings-field renames the table authorizes, hard-cut, updating the dotenv exclusion set where product-state-selecting

## Scope

- `src/cadrumo/core/config.py`

## Description

- Re-read HEAD state of `config.py`/`_config_runtime_fields.py`/
  `_config_timeouts.py` before starting (per the S18 brief's note that W02
  landed new fields since S17). Re-grepped the full `aeat_*` field set and
  found the S17 audit's own summary arithmetic was wrong: `config.py` has
  33 fields (not 32) and `_config_timeouts.py` has 11 (not 10) -- every
  individual field verdict in the S17 Findings sections was already
  correct and complete, only the summary addition undercounted by 2 (47
  total / 37 RENAME instead of the correct 49 total / 39 RENAME). Corrected
  the S17 audit document's arithmetic in place (commit `2fe4194d03`) before
  executing against the corrected 39-field list.
- Re-confirmed the flagged open item: none of the 39 migrating fields
  overlap `_LEGACY_PRODUCT_DOTENV_NAMES` (5 storage/secret-selecting
  entries, all pre-existing and unrelated) -- no new dotenv-exclusion
  entries needed.
- Renamed all 39 fields (`aeat_*` to `cadrumo_*`) across the three
  Settings-mixin files via a repo-wide token substitution (both the
  lowercase field/attribute form and the uppercase `AEAT_*`/`CADRUMO_*`
  env-var-string form in one pass per field), covering ~80 production and
  test files plus `env/.env.example`. Verified the `@field_validator`
  repo-relative-path string-literal list (the S13 lifecycle-adjacent
  classification list) picked up `aeat_iva_catalogue_root` ->
  `cadrumo_iva_catalogue_root` and `aeat_certificate_path` ->
  `cadrumo_certificate_path` correctly while leaving the KEEP fields
  `aeat_manuals_root`/`aeat_normatives_root` untouched.
- Caught and fixed one substitution miss the word-boundary (`\b`) sed
  pattern could not reach: a literal `AEAT_CERTIFICATE_PATH` immediately
  preceded by a Python `\n` escape sequence in an f-string
  (`core/tests/test_env_loader.py`) -- the raw characters `n` then `A` are
  both word characters with no boundary between them, so `\bAEAT_...`
  never matched there. Found by a post-sweep repo-wide re-grep for literal
  token survivors (not relying on the same `\b` pattern), fixed by hand.
- Corrected three unrelated stale `src/aeat/...` path defaults in
  `env/.env.example` to `src/cadrumo/...` while directly touching those
  same lines for the field rename (a pre-existing staleness bug from the
  package-root relocation, safe and in-scope to fix here).
- Regenerated `docs/reference/environment-overrides.md` via
  `python -m dev.docs.env_reference` (generated file, never hand-edited).
- Fixed 7 new `ruff` line-length violations the longer `cadrumo_` prefix
  introduced (one extra character per occurrence pushed several call
  sites past 120 columns): extracted local variables
  (`certificate_path`, `nav_timeout_ms`, `configured_certificate_path`)
  rather than reformatting inline, and wrapped one `ValueError` message
  string across two lines.
- Deliberately left locale catalogues, `docs/how-to/*.md`, error-registry
  suggestions, `next_action` builders, curated operator help, and the
  agent harness untouched -- S19's explicit scope per the
  `cli-pull-and-file-standard` lesson (gates do not scan every prose
  surface). Confirmed via the same repo-wide grep that error-registry and
  agent-harness carry zero hits (matching the S17 audit's finding) and
  that the four locale catalogues still carry the 16
  `AEAT_CLAVE_MOVIL_DNI_NIE` citations S19 must route through the locales
  CLI.
- Deliberately skipped one untracked, stale (previous-day timestamp) test
  support file
  (`adapters/outbound/storage/tests/_runtime_attached_repositories_support.py`)
  that also referenced several renamed fields: it is unrelated,
  never-committed WIP that plausibly belongs to a concurrent peer
  campaign (S28's test-isolation work is in progress); per
  `uncommitted-wip-is-not-orphaned`, left untouched rather than risk
  interfering with someone else's in-flight, un-reviewable file.

## Outcome

Landed in three commits: `2fe4194d03` (S17 audit arithmetic correction),
`96eefdac00` (the two entangled `application/auth` files, via the
apply-cached technique described in Notes), and `e8d97b1cb2` (the
remaining 77 files including the corrected `config.py`, plus the
regenerated docs page). Gates: targeted suites for every touched
production surface pass (auth/live/browser/sede/manuals/registry -- 990+
tests; `core` -- 723 passed, 3 pre-existing failures confirmed unrelated,
see Notes); `ruff check` clean on every touched file; full-tree
`pytest --collect-only -q` clean (12886 collected, with the peer's
`config.py` WIP layered back on top); the lazy-import-policy and
production file-write-inventory gates both green unchanged (this rename
introduces no new deferred imports or tracked write calls).

## Notes

**Incident, fully resolved, no data lost:** two files were entangled with
live peer WIP.

1. `application/auth/_operator.py` and its test carried an UNSTAGED
   peer comment-hygiene edit (removing `"(persona-fleet finding GX)"`
   markers). I built a HEAD-anchored patch containing only my rename
   hunks and ran `git apply --cached` + verified zero foreign markers in
   the staged diff, believing this was sufficient. It was NOT: `git
   commit -- <pathspec>` reads the WORKING TREE content for the given
   paths, not the index, regardless of what is staged. My commit
   (`96eefdac00`) therefore swept the peer's uncommitted comment-removal
   into my commit alongside my renames. Their code changes are NOT
   lost -- they are captured correctly, just under my commit instead of
   a separate one of theirs. Caught immediately after the commit by
   re-checking `git diff` for the two files and finding it empty when a
   peer diff should have remained. Recorded here per the project's
   `pathspec-commit-takes-working-tree` lesson (a prior incident of the
   exact same shape) so it is visible to the coordinator and to whichever
   agent owns that comment-hygiene cleanup: their `_operator.py` /
   `test_operator.py` markers are already gone (landed in `96eefdac00`);
   they do not need to re-apply that specific hunk.
2. `core/config.py` had a peer's `suppress_operator_dotenv` feature
   ALREADY STAGED in the index (37 insertions) when I began, with my
   renames layered on top in the working tree. Having just learned the
   pathspec-commit lesson from incident 1, I handled this one correctly:
   copied the entangled working-tree file aside, reconstructed a
   HEAD-plus-my-renames-only version by re-running the sed script against
   a fresh `git show HEAD:...` copy, wrote that clean version into the
   real file path (a plain file copy, not a git operation), committed
   with the explicit pathspec, then copied the entangled version back
   into place afterward. Verified before and after with `git diff`/`git
   diff --cached` that the peer's feature was absent from my commit and
   present, byte-identical, in the restored working tree. Their `git add`
   staging for `config.py` was reset by this process (an unavoidable
   consequence of any commit touching that path, not something this Step
   did deliberately) -- their code is fully intact in the working tree;
   they will need to `git add` it again before their own commit, which is
   a normal, non-destructive re-stage, not a recovery from loss.

Three pre-existing, unrelated `src/cadrumo/core` test failures were
observed during the full-suite gate run and confirmed NOT caused by this
Step (none touch env-var/Settings surfaces): `test_exception_base_hygiene
.py::test_production_exception_classes_do_not_introduce_unregistered_
builtin_roots` (an unrelated `_session_store.py` exception-class finding),
`test_clock_seam_usage.py::test_no_bare_wall_clock_reads_in_production`
(a stale allowlist entry in `domain/invoices/_enums.py`, a file showing
peer uncommitted WIP), and `test_period_combined_string_gate.py` (a new
peer-added docs sequence fixture, `modelo-303-first-quarter.json`, not
yet allowlisted). Per `full-tree-gate-must-distinguish-owner`, these are
out of this Step's ownership and were not fixed here.

One commit-message error: the three S18 commits' subject lines cite
`W05.P08.S18` instead of the plan's actual `W03.P06.S18` step path (a
copy-paste artifact from the immediately preceding W05.P08 atomic-write
Steps this session also executed). The work and step-check target the
correct `W03.P06.S18` step; not amending the already-landed commits per
the project's prefer-new-commits-over-amend discipline, recorded here for
clarity.
