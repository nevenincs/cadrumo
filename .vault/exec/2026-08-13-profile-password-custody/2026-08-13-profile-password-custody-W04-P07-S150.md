---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f025a49991a3cf21374cc0a8322e8521786d4b55890f17153aa1289eb8703418'
step_id: 'S150'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S150 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have Sol Medium rule on the three remaining error classes that are defined and exported and registered but never raised, each on its own justification rather than on the retention-floor refusal's, since that one was a missing guard while these may be genuine dead code and ## Scope

- `src/cadrumo/core/errors/registry/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium rule on the three remaining error classes that are defined and exported and registered but never raised, each on its own justification rather than on the retention-floor refusal's, since that one was a missing guard while these may be genuine dead code

## Scope

- `src/cadrumo/core/errors/registry/`

## Description

- Re-derived the candidate set from the live registry rather than trusting the row's count: enumerated all 628 declared `(qualname, ErrorCode)` rows across every `registry/*.py` layer file, resolved each to its owning module, and swept 1679 production files plus 3222 test files for a direct `raise <Class>` or a bare construction of it.
- Narrowed to the four candidates carrying the row's own justification pattern (a distinctive, non-generic name, registered under `core/errors/__init__.py`'s own `__all__`, with zero raise sites anywhere including tests): `CoreError`, `CoreNotFoundError`, `FixtureProvisioningError`, `McpLaunchError`.
- Ruled each independently rather than inheriting the retention-floor refusal's missing-guard verdict.
- Traced `FixtureProvisioningError` and `McpLaunchError` through `git log -S` to the commit that removed their only raise sites, confirming the capability itself was retired, not merely the guard.
- Deleted `FixtureProvisioningError` and `McpLaunchError`: their class definitions, `__all__` entries and registry rows in `core/errors/__init__.py` and `core/errors/registry/_core.py`.
- Repaired the one test that used `McpLaunchError` as its stand-in "non-`CoreError` `CadrumoError` subclass" fixture, substituting the still-live `NoActiveProfileError`.
- Confirmed `CoreError` and `CoreNotFoundError` are legitimate architectural roots, not dead code, and made no change to either.

## Outcome

**Re-derivation changed the count.** The row's premise of three was not confirmed: the set that fits the row's own "defined, exported, registered, never raised" description is four, not three, and only two of those four are dead code. The other two are family-root base classes this campaign's own prior measurement (the `history-onboarding` feature's S35 row) already established as a *correct, non-defect* pattern: "50 of 109 no-raise entries are family roots ... its missing suggestion is correct and not a gap." I applied that same precedent here rather than re-litigating it.

**`CoreError` — ruled NOT dead code.** It is registered (`ERROR_CADRUMO_CORE`), exported, and never raised directly in production — but it roots a real subtree: `DecimalFormatError`, `RedactionError`, `CoreValidationError` and `ActiveProfilePointerError` all inherit it directly and are all raised extensively in production. Its own docstring frames it as a catch surface, not a leaf. The only production-adjacent raise of the bare class is inside `application/operations/tests/test_supervisor.py`, which deliberately picks a generic *registered, non-refusal* error to stand in for "a real but boring failure" in a supervisor test — that is a test author reaching for a convenient concrete member of an abstract family, not evidence the family root itself was ever meant to be raised. No change.

**`CoreNotFoundError` — ruled NOT dead code.** Registered (`ERROR_CADRUMO_CORE_NOT_FOUND`), exported, inherits `CoreError` and `KeyError`, and its docstring states its purpose explicitly: "Domain- and application-layer not-found errors should descend from this class ... so callers can catch the whole not-found surface with a single `except CoreNotFoundError` clause." It has two real, cross-layer, production-raised subclasses — `CalculationRevisionNotFoundError` (application/modelo, raised at nine call sites) and `ResourceNotFoundError` (core/resources, raised at two) — which is exactly the cross-layer catch-surface the docstring promises. No change.

**`FixtureProvisioningError` — ruled DEAD CODE, deleted.** `git log -S'raise FixtureProvisioningError'` found its only raise sites in the now-deleted `scripts/provision_google_fixtures.py`. `git show 7eb8c5dc79` (`chore(restructure): commit dirty worktree state — CLI rework prep`) deleted that file, its sibling `scripts/teardown_google_fixtures.py`, and the rest of `scripts/` in one commit, whose own message states the deletion was "per the no-scripts/ policy." No successor Google-Workspace-fixture-provisioning path exists anywhere in `src/` today (confirmed by a tree-wide search for the concept); `src/cadrumo/tests/README.md` still describes "the Google fixture workflow" as though live, which is a dead operator instruction outside my ownership — reported below rather than edited, since `tests/README.md` is documentation, not `core/errors/**`.

**`McpLaunchError` — ruled DEAD CODE, deleted.** `git log -S'class McpLaunchError' --reverse` traced it to `feat(errors): add error code registry and cli boundary (#398)`, which introduced it alongside its one real raise site in `src/aeat/entrypoints/mcp/launch_google_workspace.py` (the repo-managed Google Workspace MCP launcher). The SAME restructure commit `7eb8c5dc79` that deleted the fixture-provisioning scripts also deleted `entrypoints/mcp/launch_google_workspace.py`, its `entrypoints/mcp/_errors.py` re-export bridge, and its test file, in one diff. The MCP surface that exists today is a wholly separate distribution, `src/cadrumo-harness/src/cadrumo_harness/mcp/`, with its own `cadrumo-mcp` console script (per the `pyproject.toml` comment at line 203) and zero references to `cadrumo.core.errors.McpLaunchError` anywhere in its tree — confirmed by grep. The capability the class guarded no longer exists in this codebase under any name.

**Implemented, not just recorded.** Both classes' definitions, `__all__` entries and registry rows are deleted from `core/errors/__init__.py` and `core/errors/registry/_core.py`. The one test referencing `McpLaunchError` (`test_core_error_root.py::test_core_error_does_not_catch_non_core_cadrumo_error`, which used it purely as an arbitrary example of a direct-`CadrumoError`, non-`CoreError` subclass) is repaired to use `NoActiveProfileError` instead, preserving the same non-tautological catch-order assertion.

**Dead operator instructions / locale keys found, not touched (outside ownership):**
- `src/cadrumo/tests/README.md` still tells operators that Google Workspace live tests "require ... project-owned fixtures provisioned via the Google fixture workflow" — that workflow (`scripts/provision_google_fixtures.py`) no longer exists. Worth a documentation-owner follow-up.
- Locale keys `errors.error.error_fixture_provisioning` (en/es/ca/hu) and `errors.fail.fail_mcp_launch` (en/es/ca/hu) now have no registry entry pointing at them, since I deleted the entries that carried those `message_key`s. Per instruction, I did not hand-edit any `.yml` — handing these eight keys to the locale agent for `python -m dev.locales remove` (or `scaffold` to prune) is the orchestrator's call.
- `dev/quality/error_code_default_suggestion_preimage.json` still lists `ERROR_FIXTURE_PROVISIONING` / `cadrumo.core.errors.FixtureProvisioningError` and `FAIL_MCP_LAUNCH` / `cadrumo.core.errors.McpLaunchError` as preimage rows. That file is paired with `dev/quality/error_code_default_recovery_rehoming.py`, explicitly out of my ownership — flagging for whoever owns that tool rather than editing it.

## Notes

**I did not follow S77's pattern, per the row's own instruction, and it changed the answer.** S77 ruled its one class (`RetentionFloorError`) as a missing guard. Blindly extending that verdict to all "remaining" classes here would have been wrong for two of the four: `CoreError` and `CoreNotFoundError` are not missing anything — they are deliberately-unraised catch-surface roots with real, actively-raised descendants, and treating their silence as a defect would have meant either deleting a load-bearing catch surface or fabricating a raise site for a class that exists precisely so that OTHER classes can be raised and caught through it.

**The row's own count (three) does not survive re-derivation.** The set is four (`CoreError`, `CoreNotFoundError`, `FixtureProvisioningError`, `McpLaunchError`), and only half of it is dead code. This is reported plainly rather than silently reconciled to "three," per the standing instruction that a campaign cannot narrow its own completion criterion without saying what the wider question still asks. I did not attempt to reconstruct which three classes the plan author originally had in mind — no prior audit, exec record or vault document names the original set (searched `.vault/` and `git log -S` for the row's own phrasing; nothing found) — so "the three remaining" is undecidable from the record and this Step instead re-derives and rules on the true current set directly.

**Scope held to `src/cadrumo/core/errors/**` and the one in-package test it forced.** No file under any other agent's declared ownership (`adapters/persistence/storage/**`, `application/wizard/**`, `domain/buckets/**`, `entrypoints/mcp/tests/**`, `locales/**`, `tests/test_parity.py`, `core/compatibility_lifecycle.py`, `dev/quality/error_code_default_recovery_rehoming.py`) was touched.

**Unrelated pre-existing failure observed, not fixed.** `test_exception_base_hygiene.py::test_production_exception_classes_do_not_introduce_unregistered_builtin_roots` fails on HEAD (before and independent of this Step's edits) over five exception classes rooting at bare `ValueError`/`RuntimeError` with no `__bare_base_rationale__`, all in `application/calculations/` and `application/user_profile/` — files this Step never touched and outside its ownership. Verified those files carry no local uncommitted changes (`git status --porcelain` empty for each), so the failure is a standing tree state, not something this edit introduced; reported for the owning agent rather than repaired here.

## Verification

    uv run --no-sync pytest -n0 -q src/cadrumo/core/errors/tests/
    53 passed, 1 failed in 81.05s
    (the 1 failure is test_exception_base_hygiene.py::test_production_exception_classes_do_not_introduce_unregistered_builtin_roots,
     pre-existing and unrelated — see Notes)

    uv run --no-sync ruff check src/cadrumo/core/errors/__init__.py src/cadrumo/core/errors/registry/_core.py src/cadrumo/core/errors/tests/test_core_error_root.py
    All checks passed!

    uv run --no-sync ruff format --check src/cadrumo/core/errors/__init__.py src/cadrumo/core/errors/registry/_core.py src/cadrumo/core/errors/tests/test_core_error_root.py
    3 files already formatted

    uv run --no-sync ty check src/cadrumo/core/errors/
    All checks passed!

A tree-wide grep for `FixtureProvisioningError` and `McpLaunchError` across `src/` and `dev/` after the edit returns only the one preimage JSON named above — no other production, test or doc reference to either class remains.
