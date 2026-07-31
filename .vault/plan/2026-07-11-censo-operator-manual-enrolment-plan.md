---
tags:
  - '#plan'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:5cb70ef63d707a8cbb8eb8c59e95841014a8699554268a5fd1c34294d9021741'
tier: L2
related:
  - '[[2026-07-11-censo-operator-manual-enrolment-adr]]'
  - '[[2026-07-12-censo-operator-manual-enrolment-research]]'
---

# `censo-operator-manual-enrolment` plan

### Phase `P01` - retire the scrape chain

Delete the dead live-censo scrape chain and the censo pull/compare/apply CLI family atomically (delete-not-stub), preserving the read-only afectacion projection and the operator-manual profile path.

- [x] `P01.S01` - Retire the sede live-censo scrape: delete the launcher drive, the G313 parser, their tests, the censo_g313_launcher constant, and the sede package exports; `src/aeat/adapters/outbound/aeat/sede/_censo_live.py, src/aeat/adapters/outbound/aeat/sede/_censo.py, src/aeat/adapters/outbound/aeat/sede/tests/, src/aeat/adapters/outbound/aeat/sede/__init__.py, src/aeat/core/external_constants.toml`.
- [x] `P01.S02` - Retire the config profile censo pull/compare/apply/show verb family with its payloads and tests, deregister it from the profile app, and narrow CensoSyncService to the read-only afectacion projection the ledger still consumes; `src/aeat/entrypoints/cli/_config/_profile_censo.py, src/aeat/entrypoints/cli/_config/_profile_censo_payloads.py, src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py, src/aeat/entrypoints/cli/_config/__init__.py, src/aeat/application/user_profile/_censo_sync.py, src/aeat/application/user_profile/_censo_errors.py, src/aeat/application/user_profile/tests/test_censo_sync.py`.

### Phase `P02` - sweep the verb-removal blast radius

Sweep every surface that cites the retired verbs or deleted modules: generated CLI reference, locale catalogues, how-to docs and API stubs, agent-harness skills, the pull-and-file rule source, and derived baselines.

- [x] `P02.S03` - Purge the retired verb family from the generated CLI reference generator and its conformance tests, and from the storage write-policy allowlist if enrolled; `dev/docs/cli_reference.py, dev/docs/tests/test_cli_reference_conformance.py, src/aeat/application/storage_write_policy.py, docs/cli/config.rst, docs/cli/schemas.rst`.
- [x] `P02.S04` - Remove the dead censo pull/compare/apply locale key subtree through the locales CLI (keeping the operator-manual advisory strings) and confirm scaffold --check is clean; `src/aeat/locales/en.yml, src/aeat/locales/es.yml, src/aeat/locales/ca.yml, src/aeat/locales/hu.yml`.
- [x] `P02.S05` - Rewrite the censo how-to docs to the operator-manual config profile edit path, drop the retired verbs from filing-calendar, modelo-036, and read-live-aeat-data guides, and regenerate the API stubs so no orphan _censo rst remains; `docs/how-to/censo-update.md, docs/how-to/filing-calendar.md, docs/how-to/modelo-036.md, docs/how-to/read-live-aeat-data.md, docs/api/`.
- [x] `P02.S06` - Re-author the inicio-actividad and cese-actividad agent skills onto the operator-manual censo mirror so the rule-surface conformance gate stays green; `src/aeat/_data/agent/skills/inicio-actividad/SKILL.md, src/aeat/_data/agent/skills/cese-actividad/SKILL.md`.
- [x] `P02.S07` - Update the aeat-cli-pull-and-file-standard rule source (it cites censo pull as a worked example), propagate with vaultspec-core sync, and prune stale terminology relevance rows and complexity-baseline entries for deleted modules; `.vaultspec/rules/rules/project/aeat-cli-pull-and-file-standard.md, src/aeat/_data/terminology/relevance/relevance.json, dev/audit/complexity_baseline.json`.

### Phase `P03` - preserve posture and verify

Pin the honest end state with regressions (calendar enrolment_unverified posture; operator-entered censal facts never AEAT-verified) and run the full gate battery; reconcile the superseded g313 plan honestly.

- [x] `P03.S08` - Pin the calendar censo.enrolment_unverified posture with a regression: the warning is present and strict projection refuses for modelos 100/130/303/390 when censo is unverified; `src/aeat/application/overview/tests/`.
- [x] `P03.S09` - Pin that operator-entered censal facts are never stamped AEAT-verified: nothing writes the aeat_censo_read or aeat_censo_derived source tags, so the calendar verified-key set stays empty; `src/aeat/application/user_profile/tests/test_censo_sync.py`.
- [x] `P03.S10` - Run the full gate battery (collect-only, ruff, documented-command conformance, rule-surface conformance, locales and apidocs scaffold checks) and record the honest reconciliation of the superseded g313 plan as an exec note without fabricating completion; `src/aeat, .vault/exec/2026-07-11-censo-operator-manual-enrolment/`.

### Phase `P04` - re-seat afectacion ratio and delete the snapshot substrate

Complete the accepted decision: re-seat the surviving home-office ratio read onto operator-declared profile facts and delete the now-producerless censo snapshot substrate, reconciling the retired provenance enum.

- [x] `P04.S11` - Re-seat bound_raw_afectacion_ratio onto operator-declared vivienda_office m2 profile facts, delete the producerless censo snapshot substrate (module, namespace, custody resolver, re-exports, error entry + locale leaves, api stub, tests), reconcile away CENSO_CORROBORATED + censo_snapshot_id, and add real-behavior guard tests; `src/aeat/application/user_profile/_censo_sync.py, src/aeat/application/live/_censo.py, src/aeat/adapters/persistence/storage/_namespace_registry.py, src/aeat/application/calculations/_cross_period_models.py`.

## Description

Implement the accepted Option-4 direction of
`2026-07-11-censo-operator-manual-enrolment-adr`: censal facts are
operator-supplied through `config profile edit`; the live censo scrape is
retired because the only AEAT surface that renders census data is the
"Censos WEB" modification tool, which the safety gates prohibit driving.
The retirement is delete-not-stub: the sede launcher drive and G313
parser, the `censo_g313_launcher` constant, and the whole
`config profile censo pull/compare/apply/show` verb family are removed,
with `compare`/`apply` retired rather than re-seated (a live snapshot was
their second operand; one enrolment path, no parallel write route). The
read-only home-office afectacion projection over any captured
`CensoSnapshot` survives for the ledger ratios path, and the snapshot
persistence layer is untouched. The blast radius enumerated by the
`aeat-cli-pull-and-file-standard` rule is swept in full: generated CLI
reference, locale catalogues, how-to docs, API stubs, agent-harness
skills, the rule source itself, and derived baselines. The calendar keeps
its `censo.enrolment_unverified` posture and operator-entered censal
facts stay a non-official evidence tier; both are pinned by regressions.
The superseded `2026-07-10-censo-g313-launcher-fix-plan` is reconciled
honestly: its remaining steps are retired-not-implemented, never checked.

## Steps

## Parallelization

P01's two Steps are one atomic relocation-style landing: the sede chain
(S01) and the CLI verb family (S02) reference each other through the
application layer, so they land together in one explicit-path commit per
the atomicity mandate. P02's Steps are independent of each other and may
run in parallel once P01 has landed (they all sweep references to the
now-deleted surfaces); S03 is the most urgent because the generated CLI
reference imports the deleted payload module. P03 depends on P01+P02:
the regressions (S08, S09) pin the post-retirement state and the gate
battery (S10) closes only when the whole tree is green.

## Verification

- No production or test module references `parse_g313_html`,
  `_G313_LABELS`, `censo_g313_launcher`, the deleted `_censo_live` /
  `_censo` sede modules, or the `config profile censo pull/compare/apply/
  show` verbs (rg sweep clean outside `.vault/` history).
- `uv run --no-sync pytest --collect-only -q src/aeat` collects clean;
  ruff clean on touched files.
- Documented-command conformance
  (`test_documented_command_conformance.py`) and rule-surface conformance
  (`src/aeat/agent/tests/test_rule_surface_conformance.py`) pass with the
  verbs removed.
- `python -m aeat.locales scaffold --check` and
  `python -m dev.docs.apidocs scaffold --check` exit clean.
- A regression pins the calendar `censo.enrolment_unverified` warning and
  the strict-projection refusal for modelos 100/130/303/390.
- A regression pins that no code path stamps `aeat_censo_read` /
  `aeat_censo_derived` on operator-entered facts.
- The superseded g313 plan's S02-S07 remain unchecked with the
  supersession note in place; an exec note records the reconciliation.
- `vaultspec-core vault check features --feature
  censo-operator-manual-enrolment` is clean and every closed Step has an
  exec record.
