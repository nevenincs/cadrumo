---
tags:
  - '#audit'
  - '#distribution-installation-readiness'
date: '2026-07-15'
modified: '2026-07-17'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
  - "[[2026-07-16-distribution-harness-identity-adr]]"
  - "[[2026-07-17-distribution-installation-readiness-audit]]"
---

# `distribution-installation-readiness` audit: `distribution installation readiness code review`

## Scope

Fresh-context, read-only campaign-close honesty review of the distribution-installation-readiness S58 closeout against `HEAD` `363213aee0`, per the campaign-close honesty-review discipline. The review re-confirmed every finding against the current tree and covered five axes: the publish hold, distribution-identity honesty, test integrity, completeness, and secret/data safety. No production code was modified.

**Verdict: PASS.** No Critical or High findings. All findings confirmed against `HEAD` `363213aee0`.

Evidence run: `test_publish_workflow` and `test_verify_distribution_identity` — 9 passed; `promote_python_cohort`, `distribution_readiness`, `readiness`, and `justfile_release_guidance` — 44 passed; a grep of all distribution test files returned zero `skip` / `xfail` / `mock` / `monkeypatch` occurrences.

## Findings

### publish-hold-fail-closed | confirmed | Publish workflow is fail-closed with no upload path

Axis 1 confirmed the publish hold is fail-closed. `publish.yml` carries no upload path: no `uv build` or publish invocation, no `id-token: write`, and workflow permissions restricted to `{actions: read, contents: read}`. It is a single `validate` job that only echoes that publication remains blocked. The job is run-bound: it rejects any triggering run whose conclusion is not `success` or whose `workflow_path` is not `packaging-smoke.yml`, checks out the exact `head_sha`, and validates through `promote_python_cohort --check-pypi`. The S44 guardrail test is non-vacuous — it makes parsed-YAML structural assertions on the permissions block, the job set, and the inputs, plus the run-bound checkout ref.

### identity-honest-failure | confirmed | Distribution identity verifier fails truthfully, not vacuously

Axis 2 confirmed the identity verifier fails honestly. `report.ok` ANDs five sub-checks and `main()` returns `1` when the report is not ok. S67 (7 personas, 7 rules, and 34 skills lacking the `cadrumo-` prefix) and S68 (5 client-display descriptions English-only, `translation_approved` False) both fail truthfully — genuinely blocked on operator authorization rather than skipped. The `product_identity` check correctly passes against its accepted tuple. The English-only model-facing versus bilingual client-display boundary is coherent with the `cadrumo-product-authority-names` discipline.

### test-integrity-real-behavior | confirmed | Distribution tests exercise real behavior with no doubles

Axis 3 confirmed real-behavior testing: real workspace, plugin, and marketplace generators; a real MCP subprocess projection; real wheel and sdist builds plus their refusal paths. No test doubles were found.

### completeness-honest-open-steps | confirmed | Open steps carry faithful failing evidence

Axis 4 confirmed completeness. S67 and S68 remain open with faithful failing evidence, and the S60 execution records are correctly still open — the plan-closure mechanism keeps the campaign honestly incomplete until the authorization-gated work lands.

### secret-data-safety-clean | confirmed | No publish secret or sensitive-financial-data path

Axis 5 confirmed secret and data safety is clean: the only credential used is `github.token` (ephemeral, read-only), there is no PyPI or publish secret, and no sensitive-financial-data path is touched.

### low-1-substring-only-build-guard | low | Build/publish prohibition rests on exact-substring guards a differently-spelled command evades

The "cannot build or regenerate" claim is enforced only by exact-substring `not in workflow_text` guards. A differently-spelled build or publish invocation inside the `validate` job — `python -m build`, `twine upload`, or a double-spaced `uv  build` — would slip past both the substring guard and the parsed-YAML presence checks. Remediation: add a structural assertion that no step in the `validate` job invokes a build or publish tool, by denylist-scanning each step's `run` / `uses`, or by pinning the full step allowlist. Enrolled as a gated hardening step in the cli-authority-quality-backlog plan.

### low-2-description-sha-drift-lock | low | Model-facing description SHA256 pin is a drift-lock, not a correctness oracle

The model-facing description SHA256 pin locks against drift; it does not assert correctness of the description text. No action required.

### low-3-justfile-token-argv | low | Local justfile release recipe passes gh token via argv

The local `justfile` release recipe passes the `gh` token via `argv`. This is pre-existing, local-only, a `--dry-run` PR-preview path, and out of publish scope. No action required.

## Recommendations

Enroll LOW-1 as a gated hardening step (done: cli-authority-quality-backlog plan) adding a structural no-build / no-publish assertion to the publish-workflow guardrail test. LOW-2 and LOW-3 need no enrollment and are recorded here only. The campaign is otherwise honestly closeable: the S67/S68 identity work and S60 execution records remain open on genuine operator-authorization and plan-closure grounds, not on hidden gaps.
