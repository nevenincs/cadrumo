---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:1a04ff2d3418fdcf1980f1e9cfd597f352dbc8b1a35f4cf0e156783b9eaf7b30'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# `registry-authority-artifact-boundary` audit: `installed behavioral proof`

## Scope

## Findings

### refusal-command-reachability | medium | Hostile cases can pass without exercising the authority-dependent CLI or MCP command

`test_installed_cli_and_mcp_refuse_an_unusable_authority_before_durable_work` damages the artifact before calling either complete oracle. Both oracles perform prerequisite profile provisioning before the authority-dependent work command, and the MCP oracle performs that provisioning through the sibling `aeat` executable before it starts the MCP protocol. The test accepts any wrapper exception whose combined diagnostic contains `published authority artifact`; therefore an eager import or other prerequisite failure can satisfy the expected exception while the intended CLI work command or MCP tool call is never reached. The empty-state assertion also succeeds in that early-failure case. Provision the disposable installation and prove a successful authority-dependent workflow before damage, then assert an exact transcript or command/tool identity for the post-damage refusal so the gate cannot pass on setup failure.

Closed on re-review. Each fresh disposable installation now completes the real CLI and MCP authority-dependent oracles and proves the expected `23000.00` result before damage. After removal or corruption, both exception contracts require `modelo.work.create` to precede the artifact diagnostic, which excludes profile provisioning and other pre-command setup failures; the separate storage roots still prove that the refused attempt leaves no work, calculation revision, or observation object. The original false-positive path is no longer present.

Additional artifact-boundary re-review found no further finding. The obsolete cohort stamper and its derived extra-member expectation have been removed together with every packaging caller and the test that existed solely to pin those generated members. The three smoke paths now compare the complete wheel data payload exactly against `expected_wheel_data_paths`, so deleting the union narrows rather than weakens the accepted inventory: tracked runtime data, including the published authority artifact, remains required, while untracked identity and verdict records are unexpected. The existing distribution test independently proves those retired cache records cannot enter either archive. No remaining production-cohort caller imports or invokes the development registry stamper.

### installed-command-spec-probe-import | high | The exact-wheel cohort cannot pass its installed CommandSpec attestation

The serial hostile-artifact proof reached `attest_command_specs` after 845 seconds, then the isolated installed probe failed because it imported `SUPPORTED_OUTPUT_LANGUAGES` from `cadrumo.core.i18n`. The closed-set language authority is published by `cadrumo.core.external_constants`; the installed `i18n` package does not re-export it. This is a genuine exact-wheel failure, not an authority-artifact failure, and it prevents both hostile cases from reaching their test bodies.

Closed locally by importing `SUPPORTED_OUTPUT_LANGUAGES` from `cadrumo.core.external_constants` in both the embedded cohort probe and its distribution-lane oracle, while retaining `lookup_translation_entry` from `cadrumo.core.i18n`. Ruff, formatting, and diff checks pass. The expensive installed cohort must be rerun before this finding and S07 can be closed.

The first re-review showed that closure was incomplete: `lookup_translation_entry` is canonically exported by `cadrumo.core.i18n.render`, while the package namespace is intentionally inert. After correcting both embedded probes, the real distribution test progressed to a second stale surface assumption, importing the Typer application from the inert `cadrumo.entrypoints.cli` namespace. Both probes now import `app` from `cadrumo.entrypoints.cli.main`. The next run then exposed a product defect rather than a probe defect: Typer could not materialise registry-projected opaque string annotations. The CommandSpec runtime now supplies a Pydantic-backed Click converter for non-enum `str` subclasses, preserving the typed annotation and its registry projector without per-token presentation duplication. A real `ledger add --help` materialises successfully, and the authoritative wheel, sdist, and wheel-from-sdist distribution gate passes in 357.48 seconds. Formal re-review found no unresolved issue: the rule covers all 21 current non-enum string-subclass parameters, preserves explicit parser, Click-type, choice, plain-string, enum, and lazy-loading paths, and the reviewed artifact and OSS selectors reconstruct and validate successfully.

### oss-candidate-scope | high | Typed OSS selectors made the republished authority unreadable and would refuse normal runtime use

The first facts-only publication reduced 342 stale-fact validation failures to five OSS selector failures. Review then found two coupled defects: `destination_member_state` bypassed the guarded member-state registry projection, while regime and transaction-kind validators required candidate scope even though the selector is also parsed during normal installed execution.

Closed on rework. OSS selector vocabularies now prefer the candidate facts already in scope during compilation or artifact decoding and resolve through the published authority when invoked at normal runtime. The newly authored EU member-state fact was included through the repository-owned atomic facts publisher. Full artifact reconstruction succeeds, a real runtime `LedgerOssProvider` selector succeeds outside candidate scope, and the focused candidate-scope suite passes all eight tests. Formal re-review found no unresolved issue; the live artifact had advanced to 148 facts and all five shipped OSS selectors validated at review time.

### exact-cohort-tracked-input | high | Live W04 production dependencies are absent from the tracked cohort snapshot

After the real distribution gate passed, the hostile S07 run again reached installed target resolution. It then refused because production `inventory.valuation` imports `inventory_anexo_d_applicability`, while that new module is untracked and therefore intentionally absent from `repository_files` and the clean exact-wheel cohort. The live tree currently contains many such untracked W04 production modules and governed-fact declarations. Including arbitrary untracked files would invalidate the cohort's source-identity and release proof; staging or committing other contributors' work is outside this execution step. S07 remains open until the W04 source set is represented in tracked repository state and the hostile installed cases can run against that exact state.

### stale-artifact-publication-bootstrap | high | Full publication imported validators through the stale artifact it had to replace

When the Lorca supplementary projection gained four required typed fields, the old artifact correctly became unreadable. Full candidate validation could not repair it because importing the authority compiler eagerly imported `RegistryValidator`, which imported applicability constants that immediately resolved governed vocabulary through `bundled_authority`. Publication therefore depended on successfully decoding the stale artifact it existed to replace.

Closed on rework. `RegistryValidator` is loaded only inside full registry validation after candidate facts are in scope; structural candidate compilation and publication no longer import it eagerly. The first formal review found that the imported applicability module still froze candidate-derived entity, income-category, and IVA-regime vocabulary in module globals. The IVA seed mapping now constructs each rule on access, and taxpayer entity vocabulary resolution prefers an explicit or context-scoped candidate authority before the bundled artifact and its date-keyed cache. A two-candidate same-process detector changes entity vocabulary in the first real `CandidateFactAuthority` scope and IVA self-assessment vocabulary in the second, proving neither the first candidate nor the published bundle leaks into the other result. Publication fixtures now carry the mandatory authored tax-ID fact, and the documented provider-free compiler branch retains authored facts rather than discarding them while normal enrolled-provider ownership and convenio refusal remain fail-closed. Full validation and supplementary compilation both receive the final authored-plus-projected fact catalogue. The publication and candidate-scope suite passes all nine tests; formatting, focused lint, and diff checks pass; strict runtime reconstruction succeeds with 58 modelos and 150 facts; and final formal re-review found no unresolved issue.

## Recommendations
