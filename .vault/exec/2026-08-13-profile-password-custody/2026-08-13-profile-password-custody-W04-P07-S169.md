---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d5b66c86c78a0f62144b0f7e05a10dd90f49bc475a16d26700c95e9f382d419f'
step_id: 'S169'
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
     The S169 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Sol Medium repair the command-line test helper that still constructs the retired bucket manifest inside a deferred function-local import, which hides it from collection so it passes every collect-only proof and fails only at run time, and which needs the capsule discovery-marker replacement rather than a manifest write and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_active_profile_env_override_name.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium repair the command-line test helper that still constructs the retired bucket manifest inside a deferred function-local import, which hides it from collection so it passes every collect-only proof and fails only at run time, and which needs the capsule discovery-marker replacement rather than a manifest write

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_active_profile_env_override_name.py`

## Description

- Read the helper's subject: a second live bucket whose label collides with the first, forged directly because no operator action can mint it.
- Located the established collision mechanism already shipping three tests in the sibling ambiguity-refusal module: register a real second profile under a distinct placeholder label, then forge its committed custody capsule label onto the target via the named capsule test-support fixture. Copied that mechanism rather than inventing a new one.
- Rewrote the helper to register a real second profile and forge its committed label through the capsule fixture, removing the deferred function-local import that built the retired `BucketManifest` / `write_manifest` call.
- Removed the now-unused retired-manifest imports and the `_DUPLICATE_MANIFEST_CREATED_AT` constant from the module.
- Ran collect-only and the full module under `-m integration`; ran the untouched sibling ambiguity-refusal module as a control; wrote and ran a scratch, non-tracked pytest file exercising the copied mechanism directly against the real resolver, including an anti-tautology restore step.

## Outcome

The helper no longer constructs the retired plaintext bucket manifest, and no longer hides that construction behind a deferred function-local import: `--collect-only` now sees the same production-current custody-capsule symbols the rest of the module imports at module scope, closing the exact collection-invisibility the row exists to fix.

Mechanism copied: `src/cadrumo/entrypoints/cli/_config/tests/test_profile_label_ambiguity_refusal.py`'s `_provision_casefold_collision` registers two real profiles via `register_cli_profile` and then calls `forge_colliding_capsule_label(profile_id=..., label=...)` (`src/cadrumo/tests/profile_capsule.py`) to overwrite the second profile's committed custody capsule label onto a colliding value. The rewritten `_write_second_live_bucket_sharing_label` in this module does the same: register a real second profile under `f"{label}-forged"`, then forge its committed label onto `label`.

Two of the module's five tests (the two ambiguity-refusal tests exercising `_write_second_live_bucket_sharing_label`) currently fail, and the failure is NOT the construction mechanism: `register_cli_profile`'s second call raises `ActiveProfilePointerTransactionError` ("pointer no longer matches either witnessed handover state") out of `login_profile` -> `_prepare_login_attempt` -> `_recover_interrupted_handover` in `src/cadrumo/application/user_profile/_login_session.py`, a file outside this Step's ownership. This is confirmed ambient, not introduced by this change: running the untouched control module `test_profile_label_ambiguity_refusal.py` (which never touched the retired manifest and already used this exact copied mechanism before today) reproduces the identical `ActiveProfilePointerTransactionError` at the identical call site, for all three of its tests, none of which this Step edited. A scratch, non-tracked pytest module (outside the repository's test tree, never collected by the suite) proved the copied mechanism itself is sound independent of that ambient defect: it seeds two committed capsules through `register_minimal_profile` + `open_test_profile_session` (which never call `login_profile` and so never touch the broken handover path), forges a collision with the same `forge_colliding_capsule_label` fixture, asserts `read_profile_bucket` raises `ProfileLabelAmbiguousError` once forged, then restores a distinct label and asserts the ambiguity clears (the anti-tautology half). That scratch proof passed.

Whether a future hidden construction of this shape would be caught: no, not automatically, and this Step does not build a new mechanism to change that (a related row already covers detection capacity in this area). `--collect-only`, the tree's `test_every_test_module_is_collectable` gate, and the full-corpus collectability lane all prove only that a test MODULE imports; none of them execute a test's function body, so a deferred function-local import that builds broken state stays invisible to every one of them exactly as this one did. Detection depends entirely on someone actually RUNNING the module. This module is `pytestmark = [pytest.mark.integration]`, and this campaign's own audit trail records repeatedly, across many unrelated closures, that the repository's default marker selection excludes integration-marked tests and exits green with nothing selected rather than red — so an ordinary default-marker run would not have caught this either. The only reliable detector already in use is a routine full-suite run with an explicit `-m "unit or integration"` override, which is manual discipline in this campaign's own gate list, not a standing automated gate.

## Notes

Ambient, out-of-ownership failure recorded above rather than absorbed: `ActiveProfilePointerTransactionError` from `src/cadrumo/application/user_profile/_login_session.py` when `login_profile` is called a second time for a distinct profile within one process. Reproduced identically by the untouched control module. Not fixed here — `application/user_profile/**` is owned by another agent on this campaign.
