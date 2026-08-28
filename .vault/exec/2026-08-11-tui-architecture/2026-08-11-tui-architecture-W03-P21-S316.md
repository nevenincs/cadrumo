---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:c9f1445a077dfc832a9db7c513656bd8aa4976533da03dbcf16dfc66468cb9fd'
step_id: 'S316'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give `TaxpayerProfile.declaration_roles` an operator-input path, so the M347 filer-role axis can carry a value for a real filer: the field exists (`domain/deadlines/_models.py:697`) and the resolver can read it (`_m347_filer_declaration_roles`), but `taxpayer_profile_from_mapping` neither reads nor writes it, so every persisted profile carries the empty frozenset and only a directly-constructed test object can hold a role -- meaning claves C, D and E would classify on a fact no real filer can ever set, and the affected populations (art. 31.3 fee collectors, art. 31.1 propiedad horizontal and social-character entities, art. 31.2 statutory-duty and public-administration entities) would silently never have their rows declared; add the mapping read/write, a setup wizard question with its `SetupFieldSpec` registration, and locale strings in all four catalogues via `python -m dev.locales set`, then prove a profile persisted through the real operator path round-trips a non-empty role set and reaches the resolver. This Step BLOCKS the completion of S308 and S309 -- neither may be closed while the fact they classify on is unreachable in production

## Scope

- `the taxpayer profile mapping boundary`
- `the setup wizard field registration`
- `the four locale catalogues`
- `and a round-trip proof through the real persisted profile path`

## Changes

- `M` `src/cadrumo/core/setup_answers.py` -- new `declaration_roles: str = ""` field on `SetupAnswers`, its `SETUP_ANSWER_FIELDS["declaration_roles"]` spec entry (`taxpayer_type.declaration_roles`), and a `_validate_declaration_roles` validator mirroring `_validate_irpf_income_categories` (comma-separated `ThirdPartyDeclarationRole` tokens, resolved via a same-package import since the enum lives in `core.aggregation`)
- `M` `src/cadrumo/domain/deadlines/_profiles.py` -- new `_resolve_declaration_roles` (mirrors `_resolve_income_categories`), wired into `taxpayer_profile_from_mapping`'s `TaxpayerProfile(...)` construction as `declaration_roles=declaration_roles`
- `M` `src/cadrumo/application/wizard/catalogue.py` -- new `_THIRD_PARTY_DECLARATION_ROLE_CHOICES` and a CHECKBOX `WizardQuestion` (`declaration-roles`, `taxpayer_type.declaration_roles`) in `_ACTIVIDAD_SECTION`, unconditionally visible (the axis is orthogonal to entity type, so no `visible_when` gate)
- `M` `src/cadrumo/application/wizard/commands.py` -- `--declaration-roles` CLI option and its choice-value derivation (landed by a peer working the CLI-flag half of the same Step in parallel; converged on identical naming)
- `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml` -- new `declaration_roles` field under the `taxpayer_type` section, grounded on RD 1065/2007 art. 31 and LGT arts. 93/94
- `M` `src/cadrumo/locales/{en,es,ca,hu}/wizard.yml` -- prompt, help and five choice label/description pairs for `wizard.setup.taxpayer-type.declaration-roles.*`, set via `python -m dev.locales set` in all four languages, wording grounded on the governing articles' own language per instruction (never paraphrased)
- `M` `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- new `test_m347_filer_declaration_roles_reaches_a_role_set_by_the_real_operator_path`: seeds a real `UserProfileRecord` (the wizard-facts shape) via `seed_test_profile_record`, then proves `_m347_filer_declaration_roles` resolves a non-empty role set through the real `projection_for_taxpayer` path -- not a directly-constructed `TaxpayerProfile`
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py src/cadrumo/domain/deadlines/tests/test_taxpayer_model.py src/cadrumo/domain/deadlines/tests/test_profile_projection_without_wizard.py src/cadrumo/core/tests/test_setup_answers.py -q -m unit` -> `pass` (91 passed)

## Notes

Several unrelated pre-existing test failures were observed while verifying
this Step and are NOT caused by it -- confirmed by reproduction: they occur
at flow positions or in files this Step never touches. Two clusters:

1. `test_extemporaneidad.py` (M210 quarter deadline resolution) and
   `test_plazo_resolution.py` (qualifier-context refusal) -- both red in
   isolation with `-n0`, no reference to anything this Step touches; likely
   fallout from unrelated in-flight registry/deadline work
   (`d287abbe0a revert(registry): drop the supported filing year consumption
   refusal` is the most recent suspect commit touching that area).
2. `test_scripted_parity.py` and `test_wizard_translations_resolve.py` --
   the scripted-walk rejection reproduces at the pre-existing
   `tax-residence-jurisdiction-scope` REQUIRED page (no canonical fixture
   entry, no default), reached and rejected BEFORE the walk ever gets to
   this Step's `declaration-roles` page; the translation-resolve failure is
   the same pre-existing `cli.app.ledger.*` / `cli.config.*` locale drift the
   `dev.locales audit` run for this Step already showed, unconnected to any
   `declaration-roles` key. `test_iva_profile_cutover_static.py` similarly
   traces to an unrelated IVA-presentation-contract feature
   (`f6b4c138ba`/`607e686c4d`).

Not fixed here: absorbing them would be a scope expansion into unrelated
domains (deadline engine, tax-residence wizard defaults, IVA presentation)
this Step's action text does not name. Reported to the coordinating session
rather than silently left for the next reader to rediscover.

This Step's own code landed split across several commits due to concurrent
worktree writes in this shared tree (a `--declaration-roles` CLI flag was
built by a peer in parallel and converged on identical naming with this
Step's wizard question, landing together in one commit); content is correct
and complete at HEAD, verified by the test run above against current HEAD
rather than by diffing local edit history.
