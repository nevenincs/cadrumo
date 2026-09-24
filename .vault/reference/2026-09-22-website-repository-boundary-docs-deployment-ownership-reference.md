---
tags:
  - '#reference'
  - '#website-repository-boundary'
date: '2026-09-22'
modified: '2026-09-22'
body_schema: 'body-v2'
body_hash: 'sha256:ae49d049a1bf78c9bc79d391cd87da1823db13473b0f0fcf190cd4511b061a08'
related:
  - "[[2026-08-23-website-repository-boundary-adr]]"
---

# `website-repository-boundary` reference: `documentation build and deployment ownership`

This audit pins the product repository at commit
`5b1c188d285f2a62db40594f29324da0fd0a635f`, the marketing repository at
`5c4cefffc76f6d77b1720c07ae69c376ddfae3c1`, and its Cadrumo engine submodule at
`b2831163aa24665eeda982d84e644bfbb081394e`. It inspected the build drivers,
publishers, infrastructure template, Just recipes, tests, GitHub workflows, current
GitHub environment metadata, and the public HTTP endpoints. Secret values were not
read or recorded.

## Summary

The Cadrumo product repository is the authority for authored user documentation,
documentation builds, the AWS delivery stack, and publication of the live
`https://cadrumo.neve.md/docs/` prefix. The marketing repository consumes a pinned
Cadrumo checkout to compose and test a combined local `dist/`, but its live publisher
owns only the site root and excludes `docs/*` from every S3 synchronization pass.
The repositories therefore share one S3/CloudFront distribution while retaining
disjoint object-key and publication authority.

The checked-in automated documentation publication route is not operationally armed
as of 2026-09-22. GitHub's `docs` environment exists and retains a custom branch
policy, but its variable and secret inventories are empty, so
`CADRUMO_DOCS_DEPLOY_ROLE` is absent and the release job refuses before checkout.
Furthermore, the workflow grants `id-token: write` but contains no AWS credential or
web-identity exchange step; the role variable is used only as a non-empty authority
marker, while the publisher invokes the AWS CLI against whatever credential session
is already available. Repository source therefore proves intended ownership and a
fail-closed unprovisioned state, but not an OIDC role assumption or a successful
automated live deployment.

## End-to-end CI/CD control flow

The product repository has one release control plane rather than an independent
documentation deployment workflow:

1. `.github/workflows/release-please.yml:3` watches `main` and supports manual
   dispatch. A release pull request dispatches the merge gate and then the release
   `prove` phase; a created release dispatches the release `publish` phase at
   `.github/workflows/release-please.yml:148` through
   `.github/workflows/release-please.yml:189`.
2. `.github/workflows/merge-gate.yml:40` runs source, format, type, workflow and
   workflow-security checks. Its gate job at `.github/workflows/merge-gate.yml:81`
   runs Semgrep, registry and import-boundary checks, and the change-scoped
   `just test-gate`; `.github/workflows/merge-gate.yml:139` reduces those jobs to
   one required verdict.
3. The `prove` phase in `.github/workflows/release.yml:34` validates the requested
   commit, reuses the full merge gate, runs the Python 3.13/3.14 test cohorts, and
   runs conformance. Documentation enters that proof through
   `just check-docstring-references`, `just docs-build`, and `just docs-check 8` at
   `.github/workflows/release.yml:224` through `.github/workflows/release.yml:229`.
   The blocking cohort then builds and reacquires release artifacts before
   `.github/workflows/release.yml:848` records the proven result.
4. The `publish` phase locates that proven cohort, publishes and reacquires the
   package channels, and only then makes the `publish-docs` job eligible at
   `.github/workflows/release.yml:1411`. That job checks out the proven tag commit,
   enters the `docs` environment, verifies the authority marker, and calls
   `python -m dev.deploy.docs_static_site publish --confirm publish-cadrumo-docs`.
5. The publisher performs a fresh strict multi-root build, validates artifacts and
   Pagefind records, resolves and verifies the CloudFormation target, synchronizes
   only `docs/`, invalidates only `/docs/*`, probes the public site, and compares
   served search records with the built records. A failure reaches the optional
   alert webhook but never transfers authority to the marketing repository.

The marketing workflow is a separate verification lane. Its sole job in
`.github/workflows/ci.yml:20` recursively checks out the pinned product submodule,
installs Node, Python, uv, Just and Chrome, runs `just check-all`, runs the required
audits, and treats the live-link audit as advisory. It has no publish job. Thus a
green marketing build proves that product docs can be composed with the landing
site; it is not a route to the live `docs/` prefix.

## Public command surface

The product repository's documentation commands have deliberately different
mutation and authority boundaries:

| Command | Owner and effect |
| --- | --- |
| `just docs-build` | `dev.docs.build`; full disposable Sphinx build, no upload. |
| `just docs-page PAGE` | `dev.docs.build --single-page`; isolated page build. |
| `just docs-lang LANG` / `just docs-langs` | user-scope localized build for one or all translated roots. |
| `just docs-serve [PORT]` | `dev.docs.serve`; local live-reload resident server. |
| `just docs-site-preview` | `dev.deploy.docs_static_site dry-run`; exact multi-root publication build and all pre-upload validations, with no AWS write. |
| `just docs-check [workers]` | focused docs pytest population, doc8 and interrogate. |
| `just check-docs-api` / `just check-api-stubs` | verify committed API stub projection through `dev.docs.apidocs`. |
| `just check-docs-synonyms` | validate the reviewed terminology synonym queue. |
| `just check-docstring-references` | resolve every Sphinx symbol reference in product docstrings through `dev.quality.docstring_reference_targets`. |
| `just docs-sequences-check [ARGS]` | re-execute committed CLI sequences without rewriting their goldens. |
| `just docs-terminology-report` | read-only Terminology Handbook audit. |
| `just report-terminology-coverage` | write a disposable coverage report below `.logs/`. |
| `just docs-generate-api-stubs` | regenerate committed API-reference stubs. |
| `just docs-generate-sequences` | regenerate committed CLI-sequence goldens. |
| `just docs-generate-catalogs` | regenerate committed gettext catalogues. |
| `just docs-locales-set-batch MANIFEST` | apply a validated PO update manifest; the `-dry-run` form previews it. |
| `just docs-terminology-maintain` | scaffold/reconcile curated handbook state. |
| `just docs-synonyms-maintain OBSERVATIONS` | mine observations into the reviewed synonym queue. |
| `just docs-stack-provision` | confirmed external mutation: provision/update the fixed AWS stack. |
| `just docs-publish` | separately confirmed external mutation: build, validate and publish the live docs prefix. |

The marketing repository exposes `just check-build`/`just docs-build` for the
landing-plus-pinned-docs artifact, `just check-docs` plus the links/navigation
aliases for composition checks, `just docs-preview` for the combined local origin,
and `just check-all` for its deterministic CI umbrella. `just deploy-dry-run` and
`just deploy` belong to the root-site publisher; the latter is local-human-only and
neither command publishes product documentation.

## Build and deployment module map

- `dev/docs/build.py` is the orchestration boundary. It plans targets, isolates
  storage, cleans orphaned output, invokes Sphinx with `-n -W` for strict builds,
  generates the sitemap, and builds Pagefind in either page or injected-record
  mode. `CADRUMO_DOCS_LANGUAGE`, `CADRUMO_DOCS_JOBS`,
  `CADRUMO_DOCS_PAGEFIND_MODE`, and `CADRUMO_DOCS_BASE_URL` are consumed here
  rather than by CI-specific wrappers.
- `docs/conf.py:111` owns the Sphinx/MyST extension and user/full-scope policy. Its
  `setup` function at `docs/conf.py:1411` wires API/docstring handling, generated
  CLI, glossary, casilla and legal references, CLI-tree emission, sequence-golden
  checks, cross-reference resolution, the `paramref` role, the `legacy` directive,
  and the `cli-sequence` directive.
- `dev/docs/apidocs/`, `dev/docs/cli_reference.py`, `dev/docs/cli_tree.py`,
  `dev/docs/casilla_reference.py`, `dev/docs/env_reference.py`,
  `dev/docs/glossary_reference.py`, `dev/docs/legal_reference.py`, and
  `dev/docs/download_matrix.py` own generated reference projections.
- `dev/docs/i18n.py` and `dev/docs/locale_mutations.py` own gettext catalogues and
  validated locale edits. `dev/docs/sequences/` plus
  `dev/docs/sequence_build_gate.py` own executable CLI examples and their build
  gate. `dev/docs/terminology/` and `dev/docs/terminology_handbook/` own vocabulary
  evidence. `dev/docs/pagefind_index.py` and `dev/docs/pagefind_inject.py` own the
  record-bearing search contract.
- `dev/deploy/docs_static_site.py` is the sole product docs deploy service and
  command-line entry point. `infra/docs-static-site.yaml` is its CloudFormation
  authority for the private versioned bucket, origin access control, CloudFront
  distribution, certificate/alias integration, and bucket policy.
- In marketing, `dev/docs_composition.py` validates the pinned `.cli-src/engine`
  gitlink, invokes the product build in user scope, stages only `dist/docs`, and
  checks the composed artifact. `dev/deploy/publish_site.py` is a distinct
  landing-site publisher whose protected-prefix rule excludes `docs/*` on every
  synchronization pass.

## Quality gates and test ownership

`just docs-check` directly selects `dev/docs/tests`, `dev/docs/apidocs/tests`, and
`src/cadrumo/tests/test_docstring_core_struct_links.py` under the docs/unit/nonserial
integration marker expression, then runs doc8 over `docs/` and interrogate over
`src/cadrumo`. The current collection contains 417 tests. These cover build modes,
localization and language switching, generated references, executable sequences,
Pagefind/search parity, browser-facing navigation, and built-site resolvability.
The doc8 configuration deliberately excludes generated output and generated API/CLI
trees; interrogate and pydoclint policy live in `pyproject.toml:1274` and
`pyproject.toml:1296`.

That focused command is not the whole repository test population. `just test-tooling`
routes all of `dev/docs` through the repository-contract lane at `justfile:921`, so
the sibling preprocess, sequence, terminology, and handbook suites are covered by
the full proof. `just test-ci-contracts-gate` first single-page-builds the docs and
then selects `dev/deploy/tests` at `justfile:949`, covering target identity,
authority refusal, lane isolation, artifact and search preflights, S3/CloudFront
scope, and published-content checks. The release prove workflow invokes this via
`just test-ci-contracts` in its full cohort as well as invoking the focused docs
commands in conformance.

Marketing's `just check-all` joins lint, TypeScript, Vitest, Python publisher/docs
tests, generated-evidence checks, font checks, deterministic artifact assertions,
browser checks, composed-link/navigation checks and Vaultspec health. Its CI then
adds dependency, capability, Nu HTML, axe WCAG and Lighthouse audits. The live-link
audit is intentionally advisory because it depends on the network.

## Product repository pattern

- `dev/docs/build.py:121` owns build planning; `dev/docs/build.py:401` owns build
  controls such as jobs, language and Pagefind mode; `dev/docs/build.py:628` owns the
  strict full/user/localized Sphinx execution path. `docs/conf.py` is the Sphinx
  configuration consumed by that driver.
- `justfile:1319` exposes `docs-build`; `justfile:1337` exposes `docs-serve`;
  `justfile:1371` and `justfile:1380` expose one-language and all-language builds;
  `justfile:1394` exposes the deploy-faithful, non-uploading `docs-site-preview`;
  `justfile:1405` exposes `docs-check`.
- `dev/deploy/docs_static_site.py:28` fixes the canonical docs URL, host, stack name,
  and region. `dev/deploy/docs_static_site.py:125` pins the deployment build to the
  canonical URL, serial execution, and full record-injected Pagefind contract.
- `dev/deploy/docs_static_site.py:232` invokes the strict build driver;
  `dev/deploy/docs_static_site.py:248` through `dev/deploy/docs_static_site.py:331`
  require the deploy artifacts, canonical sitemap and substantive search records;
  `dev/deploy/docs_static_site.py:334` through `dev/deploy/docs_static_site.py:529`
  build and validate every language root and the apex language entry.
- `dev/deploy/docs_static_site.py:601` provisions the fixed `cadrumo-docs`
  CloudFormation stack. `infra/docs-static-site.yaml:28` declares a private,
  encrypted, versioned S3 bucket; `infra/docs-static-site.yaml:50` declares the
  CloudFront origin access control; `infra/docs-static-site.yaml:94` declares the
  distribution and `cadrumo.neve.md` alias; `infra/docs-static-site.yaml:140`
  restricts bucket reads to that distribution.
- `dev/deploy/docs_static_site.py:646` reads bucket and distribution identifiers from
  stack outputs and `dev/deploy/docs_static_site.py:678` refuses the wrong alias.
  `dev/deploy/docs_static_site.py:701` synchronizes generated HTML only to
  `s3://<stack bucket>/docs/`; `dev/deploy/docs_static_site.py:719` limits cache
  invalidation to `/docs/*`.
- `dev/deploy/docs_static_site.py:972` composes the exact dry-run and publish build;
  `dev/deploy/docs_static_site.py:1004` validates it without AWS or upload;
  `dev/deploy/docs_static_site.py:1033` performs authority check, target validation,
  build, pre-upload validation, S3 synchronization, CloudFront invalidation, public
  endpoint checks, and built-versus-served search-index verification in that order.
- `justfile:1445` exposes the explicitly confirmed `docs-stack-provision` command and
  `justfile:1450` exposes the separately confirmed `docs-publish` command. Neither is
  reachable from the local check umbrellas.

## CI and operational authority

- `.github/workflows/release.yml:5` makes the release workflow manually dispatched
  with separate prove and publish phases. Its prove path runs `just docs-build` and
  `just docs-check 8` at `.github/workflows/release.yml:226`.
- `.github/workflows/release.yml:1411` is the only automated docs publisher. It runs
  only in the publish phase after the package publication and reacquisition jobs,
  uses the `docs` environment, runs on the self-hosted Linux fleet, and grants
  `id-token: write` plus `contents: read`.
- `.github/workflows/release.yml:1425` fails when the environment-scoped
  `CADRUMO_DOCS_DEPLOY_ROLE` variable is empty. `.github/workflows/release.yml:1455`
  passes that name to `dev.deploy.docs_static_site publish`; failure alerts use the
  optional `CADRUMO_ALERT_WEBHOOK` variable at `.github/workflows/release.yml:1462`.
- `dev/deploy/docs_static_site.py:915` treats the deploy-role value only as the marker
  that an automated run came from the provisioned environment. The AWS commands use
  the ambient AWS CLI credential chain at `dev/deploy/docs_static_site.py:545`; no
  checked-in workflow or setup action configures AWS credentials or exchanges the
  GitHub OIDC token for that role.
- GitHub API inspection on 2026-09-22 found repository variables only for unrelated
  release destinations and repository secrets only for those same destinations.
  The `docs` environment existed with a custom branch policy and no variables or
  secrets. This observation is reproducible with `gh variable list`,
  `gh secret list`, and the environment variables/secrets endpoints; those APIs
  disclose names and timestamps, not secret values.
- `dev/deploy/tests/test_publish_authority.py:48` proves an automated run proceeds
  only when the marker is non-empty; `dev/deploy/tests/test_publish_authority.py:69`
  proves an unprovisioned run refuses before a cloud call. The test does not and
  cannot prove role assumption.
- `dev/deploy/tests/test_deploy_lane_isolation.py:256` keeps local check lanes away
  from deploy verbs; `dev/deploy/tests/test_deploy_lane_isolation.py:322` asserts no
  Just recipe depends on a deploy verb; `dev/deploy/tests/test_deploy_lane_isolation.py:399`
  permits only the release delivery workflow to invoke the publisher;
  `dev/deploy/tests/test_deploy_lane_isolation.py:430` pins the documentation
  publisher as the only workflow-invoked publisher in this repository.
- `dev/deploy/tests/test_docs_static_site.py:133` through
  `dev/deploy/tests/test_docs_static_site.py:444` cover language roots, canonical
  URLs, full search, required artifacts, sitemaps, dry-run composition and refusal
  before upload. `dev/docs/tests/test_deployment_search_parity.py:175` through
  `dev/docs/tests/test_deployment_search_parity.py:640` cover record-bearing search
  parity and localization across the deploy matrix.

## Marketing repository pattern

- `.gitmodules:1` pins `.cli-src/engine` to the Cadrumo repository. The committed
  gitlink was `b2831163aa24665eeda982d84e644bfbb081394e` at the audited marketing
  commit.
- `dev/docs_composition.py:392` runs the pinned engine's
  `python -m dev.docs.build --scope user`; `dev/docs_composition.py:430` resolves an
  optional `CADRUMO_ENGINE` override or the pinned submodule; and
  `dev/docs_composition.py:442` validates project identity and gitlink equality.
- `dev/docs_composition.py:2830` safely replaces only `dist/docs`, and
  `dev/docs_composition.py:2877` builds the landing site, builds pinned user docs,
  normalizes the staged copy, and composes both into one local `dist/` artifact.
  `justfile:58` exposes this as `check-build`; `justfile:84` adds composed-link and
  browser-navigation checks; `justfile:175` aliases it as `docs-build`.
- The marketing root CI is verification only: `.github/workflows/ci.yml:6` runs on
  dispatch and pushes/pull requests to `main`; `.github/workflows/ci.yml:65` installs
  the pinned engine environment; `.github/workflows/ci.yml:68` runs deterministic
  checks with page-only search. It contains no deployment job and no secret
  reference.
- The live marketing publisher deliberately does not call the composition builder.
  `dev/deploy/publish_site.py:99` runs only the landing `npm run build` into `build/`.
  `dev/deploy/publish_site.py:79` declares `docs/*` protected, and
  `dev/deploy/publish_site.py:172` applies that exclusion to every S3 sync pass.
  `dev/deploy/publish_site.py:413` refuses all automated environments;
  `justfile:186` exposes a local AWS dry run and `justfile:190` exposes a separately
  confirmed, local-human-only root publish.
- `dev/deploy/tests/test_publish_site.py:47` pins the protected docs prefix, and
  `dev/deploy/tests/test_publish_site.py:196` proves every root-publisher sync pass
  excludes it. Marketing can build a docs-bearing local artifact but cannot publish
  live documentation through its deployment command.

## Observed public surface and limits

On 2026-09-22, read-only HTTP probes returned HTTP 200 for
`https://cadrumo.neve.md/`, `https://cadrumo.neve.md/docs/`, and the docs sitemap;
the responses carried Amazon S3 and CloudFront headers. The legacy
`https://neve.md/cadrumo/docs` route returned HTTP 308 to the canonical docs URL.
This proves the shared AWS delivery surface exists, but HTTP cannot attribute the
last writer or identify the deployed commit. The current-source localized
`/docs/es/` path returned HTTP 404, so the live surface must not be represented as a
proven deployment of the audited product commit.

The focused product suites
`dev/deploy/tests/test_docs_static_site.py`,
`dev/deploy/tests/test_publish_authority.py`,
`dev/deploy/tests/test_deploy_lane_isolation.py`, and
`dev/docs/tests/test_deployment_search_parity.py` passed 55 tests. The marketing
composition and publisher suites in `dev/docs/tests/test_docs_composition.py` and
`dev/deploy/tests/test_publish_site.py` also exited successfully. These results prove
the checked-in boundaries and fail-closed behavior; they do not substitute for a
successful credentialed dry run, CloudFormation inspection, or release publish.
