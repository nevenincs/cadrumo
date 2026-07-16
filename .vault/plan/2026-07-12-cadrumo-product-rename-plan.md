---
tags:
  - '#plan'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-16'
tier: L4
related:
  - '[[2026-07-12-cadrumo-product-rename-research]]'
  - '[[2026-07-12-cadrumo-product-rename-adr]]'
  - '[[2026-07-12-cadrumo-cli-executable-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `cadrumo-product-rename` plan

## Description

Execute the accepted referent-aware hard cut from the former product identity to
CADRUMO across source, packaging, runtime, persistence, MCP/plugin integration,
automation, locales, and active documentation. Preserve AEAT wherever it denotes
the Spanish authority, its portals, protocols, credentials, legal provenance,
official corpus, registry taxonomy, citations, hashes, and historical evidence.

The plan introduces no import, executable, environment, plugin, MCP, namespace,
or persisted-state compatibility shim. The sole human command is `aeat`;
`cadrumo-mcp` remains the distinct MCP command.
Generated surfaces follow their authored
authorities, public publication remains blocked on evidenced external-name
clearance, and every edit begins with explicit shared-worktree ownership and
scoped-diff inspection.

## Epic intent

Deliver one release-capable CADRUMO identity under GitHub issue #476 and the chore-476 restructure execution project association during this rename campaign. The principal engineer coordinates package/runtime, persistence, agent-integration, release, locale, documentation, and formal-review owners. Completion requires every Step record, issue #476, and the associated chore to report complete; local code completion does not waive the external reservation gate.

## Wave `W01` - freeze boundaries and establish the identity authority

Delivers the executable classification and single identity source on which every later Wave depends.

### Phase `W01.P01` - secure ownership and classify ambiguous names

Establish path ownership and explicit product-versus-authority classification before mutation.

- [x] `W01.P01.S01` - Inventory dirty and untracked paths and record path ownership before rename edits; `shared worktree ownership ledger`.
- [x] `W01.P01.S02` - Classify every public environment variable as product-owned or authority-owned; `product and authority environment-variable matrix`.
- [x] `W01.P01.S03` - Classify every persistence root, database, namespace, session directory, and bundle suffix; `persistence identity matrix`.
- [x] `W01.P01.S04` - Classify external package, repository, marketplace, executable, domain, and trademark reservations; `issue #476 external reservation register`.

### Phase `W01.P02` - create the canonical runtime identity

Create and test the single CADRUMO identity authority.

- [x] `W01.P02.S05` - Add the immutable canonical CADRUMO tuple and authority-boundary vocabulary; `src/cadrumo/core/product_identity.py`.
- [x] `W01.P02.S06` - Expose the public product identity through the package facade; `src/cadrumo/core/__init__.py`.
- [x] `W01.P02.S07` - Add contract tests proving the canonical tuple and rejecting former product aliases; `src/cadrumo/core/tests/test_product_identity.py`.
- [x] `W01.P02.S08` - Codify that CADRUMO names the product and AEAT names the authority; `.vaultspec/rules/cadrumo-product-authority-names.md`.
- [x] `W01.P02.S86` - Reconcile the binding CADRUMO product, aeat human CLI, and AEAT authority naming contract; `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md; .vault/plan/2026-07-12-cadrumo-product-rename-plan.md; .vaultspec/rules/cadrumo-product-authority-names.md; generated provider naming rules; src/cadrumo/core/product_identity.py; src/cadrumo/core/tests/test_product_identity.py`.
- [x] `W01.P02.S87` - Remediate the S86 naming-authority review and retire stale all-caps repair lanes; `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md; .vault/adr/2026-07-13-product-rename-adr.md; .vault/plan/2026-07-12-cadrumo-product-rename-plan.md; .vault/audit/2026-07-13-cadrumo-product-rename-s86-restored-authority-audit.md; S86, S87, S90, and S93 execution records; src/cadrumo/core/product_identity.py; src/cadrumo/core/tests/test_product_identity.py`.
- [x] `W01.P02.S90` - Retire the historical exact-all-caps repair lane under the contextual casing authority; `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md; S90 execution record`.
- [x] `W01.P02.S93` - Retire the historical all-caps regression lane under the contextual casing authority; `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md; S93 execution record`.
- [x] `W01.P02.S94` - Correct S87 cross-carried S37 closure chronology and accepted Stage-A history; `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md; S87, S37, S94, S96, and S97 execution records`.
- [x] `W01.P02.S95` - Repair the 9cb authority regression while preserving reciprocal ADR supersession; `.vault/adr/2026-07-12-cadrumo-product-rename-adr.md; .vault/adr/2026-07-12-cadrumo-cli-executable-adr.md; src/cadrumo/core/product_identity.py; src/cadrumo/core/tests/test_product_identity.py; .vault/plan/2026-07-12-cadrumo-product-rename-plan.md; S95 execution record`.
- [x] `W01.P02.S96` - Document the whole-ADR supersession attempt later corrected to preserve the accepted Stage-A role; `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md; S96 execution record`.
- [x] `W01.P02.S97` - Document the historical-only note later corrected to preserve the accepted Stage-A role; `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md; S97 execution record`.

## Wave `W02` - move runtime and persistence at one breaking boundary

Depends on W01 and establishes the package and state roots consumed by packaging and integrations.

### Phase `W02.P03` - move the Python root and dynamic references

Move the import root and every executable dynamic reference without aliases.

- [x] `W02.P03.S09` - Move the production package root without leaving an aeat import package; `src/aeat to src/cadrumo package tree`.
- [x] `W02.P03.S10` - Move package-local tests and direct imports without shadow modules; `src/aeat tests to src/cadrumo tests`.
- [x] `W02.P03.S11` - Retarget packaged-resource lookup to the CADRUMO root; `src/cadrumo/core/resources`.
- [x] `W02.P03.S12` - Retarget registry callable strings while retaining authority taxonomy paths; `src/cadrumo/_data/registry TOML callable targets`.
- [x] `W02.P03.S13` - Retarget dynamic imports to public CADRUMO facades; `src/cadrumo dynamic import sites`.
- [x] `W02.P03.S14` - Retarget error-registration module paths and structural assertions; `src/cadrumo/core/errors registries`.
- [x] `W02.P03.S15` - Preserve the external authority adapter name under the new product root; `src/cadrumo/adapters/outbound/aeat`.
- [x] `W02.P03.S16` - Preserve the authority registry taxonomy under the new product root; `src/cadrumo/_data/registry/aeat`.

### Phase `W02.P04` - cut product configuration and state

Move product configuration and persistence identifiers at one breaking boundary.

- [x] `W02.P04.S17` - Rename product-owned settings and CADRUMO environment parsing while retaining authority settings; `src/cadrumo configuration consumers/tests; dev configuration consumers; env/.env.example; packaging/mcpb/manifest.json; .github/workflows; justfile; conftest.py`.
- [x] `W02.P04.S18` - Move the platform application-data root to CADRUMO and refuse detected former-product state; `src/cadrumo/core/_config_state_root.py; src/cadrumo/core/tests/test_config_state_root.py`.
- [x] `W02.P04.S19` - Rename the product database filename without fallback; `src/cadrumo core configuration/state routing; persistence SQL and master-key consumers; cohesive database tests/examples`.
- [x] `W02.P04.S20` - Rename product authentication-session storage without reading or moving former state; `src/cadrumo/core/auth_session_keys.py; src/cadrumo/adapters/outbound/aeat/auth/_session_store.py; src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py; src/cadrumo/adapters/outbound/aeat/auth/tests/test_session_store_roundtrip.py`.
- [x] `W02.P04.S21` - Rename product logical storage namespaces without touching authority field names; `src/cadrumo persistence namespace registry/repository and cohesive consumers/tests/examples`.
- [x] `W02.P04.S22` - Rename product bundle suffixes and reject former bundle formats; `src/cadrumo sealed bucket archive writer/reader/header/service and focused storage/application/CLI tests`.
- [x] `W02.P04.S23` - Add real-filesystem tests for fresh CADRUMO state and explicit old-state refusal; `src/cadrumo/adapters/persistence/storage/tests/test_cadrumo_state_identity_acceptance.py`.

## Wave `W03` - rebuild distributions and executable surfaces

Depends on W02 and produces installable local artifacts before integration regeneration.

### Phase `W03.P05` - rename root distribution and scripts

Make the CADRUMO distribution expose the sole human `aeat` command and the
distinct `cadrumo-mcp` command.

- [x] `W03.P05.S24` - Rename root metadata, package selection, extras, and URLs to CADRUMO; `expose `aeat` and `cadrumo-mcp` scripts; `pyproject.toml`.
- [x] `W03.P05.S25` - Bind CLI program identity to `aeat` and its version and help product surfaces to CADRUMO; `src/cadrumo/entrypoints/cli and direct CLI structural tests`.
- [x] `W03.P05.S26` - Rename MCP executable refusal and install hints; `src/cadrumo/entrypoints/mcp executable/refusal modules and focused real tests`.
- [x] `W03.P05.S27` - Update the optional-extra authority and every directly generated runtime install remedy to current `cadrumo[...]` metadata, with real degradation tests; `src/cadrumo/core/_optional_extras.py; optional-extra consumers, error registries, agent/MCP/search/corpus degradation surfaces and direct tests`.

### Phase `W03.P06` - rename both companion projects

Move the companion projects and shared namespace coherently.

- [x] `W03.P06.S28` - Move the manuals companion project directory; `packaging/aeat_data_manuals to packaging/cadrumo_data_manuals`.
- [x] `W03.P06.S29` - Rename manuals distribution metadata and repository URLs; `packaging/cadrumo_data_manuals/pyproject.toml`.
- [x] `W03.P06.S30` - Retarget manuals build mapping and plugin name to cadrumo_data; `packaging/cadrumo_data_manuals/hatch_build.py`.
- [x] `W03.P06.S31` - Move the official companion project directory; `packaging/aeat_data_official to packaging/cadrumo_data_official`.
- [x] `W03.P06.S32` - Rename official distribution metadata, repository URLs, and companion install guidance; `packaging/cadrumo_data_official/pyproject.toml; packaging/cadrumo_data_official/README.md`.
- [x] `W03.P06.S33` - Retarget official build mapping and plugin name to cadrumo_data; `packaging/cadrumo_data_official/hatch_build.py`.
- [x] `W03.P06.S34` - Retarget runtime companion discovery exclusively to the `cadrumo_data` PEP 420 namespace and prove byte access across both built wheel portions; `src/cadrumo/core/resources/_boundary.py; src/cadrumo/core/resources/tests/test_corpus_companion_seam.py`.
- [x] `W03.P06.S35` - Update real-wheel companion partition and namespace invariants; `dev/packaging/tests/test_cadrumo_data_distribution.py`.

### Phase `W03.P07` - regenerate and prove artifacts

Regenerate dependency state and prove clean installed artifacts.

- [x] `W03.P07.S36` - Regenerate all root and companion dependency records after metadata converges; `uv.lock`.
- [x] `W03.P07.S37` - Update the slim-wheel clean-install probe to CADRUMO names; `dev/packaging/smoke_core.py`.
- [x] `W03.P07.S38` - Update the extras clean-install probe to CADRUMO names; `dev/packaging/smoke_extras.py`.
- [x] `W03.P07.S39` - Update the Docker clean-install probe to CADRUMO names; `dev/packaging/smoke_docker.py`.
- [x] `W03.P07.S40` - Update the split-companion install probe and wheel globs; `dev/packaging/smoke_split_install.py`.
- [x] `W03.P07.S41` - Build and inspect the root wheel for only cadrumo import members; `local root wheel artifact`.
- [x] `W03.P07.S42` - Build and inspect both companion wheels for disjoint cadrumo_data members; `local companion wheel artifacts`.

## Wave `W04` - project identity through MCP, plugin, and secondary bundle

Depends on locally installable W03 artifacts; generator authorities land before derivatives.

### Phase `W04.P08` - rename MCP wire identity

Project CADRUMO across MCP server, tools, resources, and client behavior.

- [x] `W04.P08.S43` - Rename server, tool prefixes, subprocess argv, and product environment names while retaining authority language; `src/cadrumo/entrypoints/mcp/_server.py`.
- [x] `W04.P08.S44` - Rename MCP resource URI schemes; `src/cadrumo/entrypoints/mcp/_resources.py`.
- [x] `W04.P08.S45` - Rename MCP prompts and product-facing tool copy; `src/cadrumo/entrypoints/mcp/_prompts.py`.
- [x] `W04.P08.S46` - Update MCP allowlists and recompute tool-name budgets; `src/cadrumo/entrypoints/mcp tests`.
- [x] `W04.P08.S47` - Prove a real CADRUMO client initialize, list, call, and shutdown handshake; `src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py`.

### Phase `W04.P09` - change generator authority and regenerate marketplace

Change plugin generation authorities before regenerating and validating marketplace output.

- [x] `W04.P09.S48` - Rename plugin identity, distribution pin, command, source path, metadata, and environment interpolation; `src/cadrumo/agent/_workspace.py`.
- [x] `W04.P09.S49` - Update generator tests for plugins/cadrumo and pinned CADRUMO launcher output; `src/cadrumo/agent/tests`.
- [x] `W04.P09.S50` - Regenerate the marketplace manifest and CADRUMO plugin subtree from the changed authority; `packaging/marketplace generated output`.
- [x] `W04.P09.S51` - Validate the regenerated marketplace and plugin with the live strict Claude validator; `packaging/marketplace validation evidence`.

### Phase `W04.P10` - rename or retire MCPB explicitly

Keep the secondary bundle honest under the CADRUMO identity or explicitly retire it.

- [x] `W04.P10.S52` - Rename the secondary bundle manifest identity and executable; `packaging/mcpb/manifest.json`.
- [x] `W04.P10.S53` - Emit cadrumo.mcpb and CADRUMO diagnostics without overstating installability; `packaging/mcpb/build.py`.
- [x] `W04.P10.S54` - Prove manifest validation, bundle members, and honest signing behavior; `packaging/mcpb/tests/test_build.py`.

## Wave `W05` - converge developer, release, locale, and documentation surfaces

Depends on authoritative runtime and generator identities from W01 through W04.

### Phase `W05.P11` - update automation and publication gates

Converge developer automation, CI, release tooling, and external publication gates.

- [x] `W05.P11.S55` - Update developer recipes, release URLs, companion paths, and rollback commands; `justfile`.
- [x] `W05.P11.S56` - Rename manual publish choices, builders, filename guards, and Trusted Publisher expectations; `.github/workflows/publish.yml`.
- [x] `W05.P11.S57` - Rename packaging smoke labels, commands, and evidence artifacts; `.github/workflows/packaging-smoke.yml`.
- [x] `W05.P11.S58` - Retarget CI source paths and named product jobs; `.github/workflows/ci.yml`.
- [x] `W05.P11.S59` - Retarget agent-harness evaluation to cadrumo-mcp; `.github/workflows/agent-harness-eval.yml`.
- [x] `W05.P11.S60` - Update release-readiness project-name parsing and real behavior tests; `dev/release`.
- [x] `W05.P11.S61` - Block publication until all three PyPI Trusted Publishers and remaining reservation evidence are confirmed; `issue #476 release gate evidence`.

### Phase `W05.P12` - regenerate locale-owned product copy

Update product copy through locale authorities while preserving AEAT counterparty language.

- [x] `W05.P12.S62` - Bind command-help invocations to `aeat` and product copy to CADRUMO while preserving AEAT counterparty language; `src/cadrumo entrypoint help authorities`.
- [x] `W05.P12.S63` - Update English product locale messages through the locales CLI; `English locale catalogue`.
- [x] `W05.P12.S64` - Update Spanish product locale messages through the locales CLI; `Spanish locale catalogue`.
- [x] `W05.P12.S65` - Update Catalan product locale messages through the locales CLI; `Catalan locale catalogue`.
- [x] `W05.P12.S66` - Update Hungarian product locale messages through the locales CLI; `Hungarian locale catalogue`.
- [x] `W05.P12.S67` - Regenerate locale scaffold output and pass locale parity checks; `generated locale scaffold`.
- [x] `W05.P12.S88` - Add safe per-locale selection to product-identity canonicalization; `src/cadrumo locale manager, CLI, and cohesive tests`.
- [x] `W05.P12.S89` - Correct locale scalar and placeholder parity through the locale CLI; `English, Spanish, Catalan, and Hungarian locale catalogues`.
- [x] `W05.P12.S91` - Enforce locale scalar and placeholder parity in the production audit; `locale manager, shared interpolation grammar, and cohesive audit tests`.
- [x] `W05.P12.S92` - Remediate formatter-field extraction and strict interpolation postconditions; `shared i18n grammar, locale audit, cohesive renderer and audit tests`.

### Phase `W05.P13` - rewrite active documentation through the mandated workflow

Update active user-facing documentation and regenerate derived references.

- [x] `W05.P13.S68` - Rewrite product branding, badges, install commands, and authority-qualified prose; `README.md`.
- [x] `W05.P13.S69` - Rewrite release, publication, rollback, and old-state cutover instructions; `RELEASING.md`.
- [x] `W05.P13.S70` - Rewrite active user guides with `aeat` invocations, CADRUMO product prose, and preserved AEAT authority language; `docs/how-to`.
- [x] `W05.P13.S71` - Rewrite active explanation and reference pages with the product-authority boundary; `docs/explanation and docs/reference`.
- [x] `W05.P13.S72` - Update documentation site identity, titles, marks, and generated API configuration; `docs/conf.py and docs/_static product assets`.
- [x] `W05.P13.S73` - Update release templates, checklist, and current verification proofs; `docs release and verification surfaces`.
- [x] `W05.P13.S74` - Regenerate API references and documentation indexes from CADRUMO source authorities; `generated documentation surfaces`.
- [x] `W05.P13.S75` - Render and inspect the complete documentation site for stale product identity and broken references; `built documentation site`.

## Wave `W06` - run residue audit, formal review, and epic closure

Depends on all implementation Waves and distinguishes valid AEAT authority uses from stale branding.

### Phase `W06.P14` - run referent-aware residue and behavior gates

Prove CADRUMO behavior and classify every retained `aeat` occurrence by
contract and referent.

- [x] `W06.P14.S76` - Audit remaining `aeat` tokens and classify each as the sole CLI, authority, historical evidence, immutable corpus, or defect; `repository rename residue report`.
- [x] `W06.P14.S77` - Prove no `aeat` import root, second human CLI alias, dual environment reader, namespace fallback, or state migration remains; `compatibility absence gate`.
- [x] `W06.P14.S78` - Run focused runtime, persistence, CLI, MCP, agent, and packaging tests with real behavior; `CADRUMO feature test surface`.
- [x] `W06.P14.S79` - Run installed-wheel, split-companion, Docker, MCP handshake, locale, and documentation gates; `CADRUMO artifact acceptance surface`.
- [x] `W06.P14.S80` - Run the path-scoped feature-surface quality gate for every file owned by issue #476; `feature-surface gate evidence`.

### Phase `W06.P15` - obtain independent formal review and close

Resolve review findings, reverify, audit ownership, and close the Epic association.

- [x] `W06.P15.S81` - Perform the mandatory vaultspec formal code review for safety, intent, architecture, and quality; `CADRUMO rename change set`.
- [x] `W06.P15.S82` - Resolve every actionable formal-review finding without introducing compatibility shims; `formal review remediation set`.
- [x] `W06.P15.S83` - Rerun affected focused and artifact gates after review remediation; `post-review verification evidence`.
- [x] `W06.P15.S84` - Confirm every edited path is owned, every unrelated dirty path remains untouched, and commits use explicit pathspecs; `shared-worktree delivery audit`.
- [x] `W06.P15.S85` - Close issue #476 and the chore-476 restructure execution association only after all Steps and external release gates are complete; `Epic project-management association`.

## Parallelization

Waves are hard-sequenced from W01 through W06. In W01, classification may proceed
alongside identity-authority work only after the ownership inventory. In W02, the
package-move and persistence Phases may use separate agents after disjoint path
ownership is recorded, but they land together and no downstream Wave consumes a
half-renamed tree.

In W03, root metadata and companion projects may proceed concurrently; artifact
regeneration waits for both. The two companion lanes are independent. In W04, MCP
wire work and MCPB work may proceed concurrently after W03; marketplace generation
waits for both MCP identity and generator authority. In W05, automation, locale,
and documentation research may run on disjoint paths; documentation authoring waits
for help/locale authorities and generated integration output. W06 is serial:
residue audit, behavior gates, formal review, remediation, reverification, ownership
audit, and project closure.

Before every edit, the executor repeats `git status --short` and scoped
`git diff -- <owned paths>`, stopping on overlap. No state-clearing command is
permitted.

## Verification

1. `import cadrumo` succeeds from source and installed wheel, `import aeat`
   fails, and the wheel contains no former product import root.
2. `aeat --version` and `cadrumo-mcp` work from clean installs. There is no
   `cadrumo` human CLI or `aeat` Python import package.
3. The root and companion wheels share a version, remain within size budgets,
   install together, expose only `cadrumo_data`, preserve disjoint corpus
   ownership, and retain byte-exact official evidence.
4. Fresh state uses only CADRUMO roots and namespaces; detected former-product
   state is refused and never read, moved, re-keyed, or deleted.
5. Product controls use `CADRUMO_*`; every retained `AEAT_*` setting is proven
   to configure the authority.
6. MCP exposes CADRUMO server, tool, and resource identities, passes a real-client
   handshake and name-budget gates, and preserves safety and identity rails.
7. The generated plugin launches pinned `cadrumo[agent]` through
   `cadrumo-mcp`; strict marketplace validation passes; retained MCPB output is
   honestly validated.
8. Locale parity, documentation build, link, command-conformance, and rendered
   inspection gates pass.
9. The residue report contains no unexplained former product identity; retained
   AEAT occurrences are classified authority, historical, or immutable evidence.
10. Lock, focused pytest, packaging smoke, Docker smoke, feature-surface, and
    post-review gates pass without prohibited test shortcuts.
11. Formal code review has no unresolved actionable findings, and the explicit-
    path ownership audit is clean.
12. Publication remains blocked until exact external names and trademark positions
    are evidenced as reserved or cleared. Epic completion also requires issue #476
    and the chore-476 association to be complete.
