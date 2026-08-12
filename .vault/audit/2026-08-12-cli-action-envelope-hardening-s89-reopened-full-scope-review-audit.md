---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:17bdc7d541bbc31aa4910dbb065b532bf9956e34a0bd5c76f138c82fca8c3036'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
  - "[[2026-08-09-cli-action-envelope-hardening-W05-P10-S89]]"
---
# `cli-action-envelope-hardening` audit: `S89 reopened full-scope independent review`

## Scope

Independent current-tree review of `W05.P10.S89` against the accepted action-envelope ADR and the reopened execution record. The review covers the complete `entrypoints.cli._config` production module inventory, its strict `config check` transport projection, terminal action/no-recovery invariant, localisation ownership, raw-command and exception-flattening absence, and the real isolated configuration, bundle, profile, and Google routes.

## Findings

### s89-reopened-full-scope | low | PASS: configuration guidance is catalogue-derived and schema-resolved

Fresh semantic discovery located the canonical configuration projection at `application.preflight`, `_config._check_payloads`, and `_config._check_cli`; the accepted ADR confirms that the application owns the failed condition while the CLI resolves a declared action. The complete config conformance test derives its production-path set from the package and fails on drift. It rejects source-language translation defaults, runtime command prose outside declared provenance, raw Notice messages, unresolved Notice actions, and caught exception text copied into context.

`CheckPreflightPayload` validates the required state invariant: healthy rows carry neither projection and unhealthy rows carry exactly one resolved precondition action or an explicit no-recovery outcome. The current `config check` consumer intentionally drops the upstream S66 `detail` and `remediation` prose, supplies no invented facts or command, and uses `operator_decision` until the producer supplies a typed verdict. This preserves the no-invention boundary and leaves the source remediation work explicitly with S66.

The independently run integration selection passed 45 tests. It exercises `config check` as JSON and text in ca, en, es, and hu, and covers representative profile, bundle, and Google error paths on isolated real storage. The reviewed conformance tests parse production syntax and load the actual locale authority; they contain no fake, mock, stub, patch, monkeypatch, skip, xfail, or duplicated configuration business logic.

## Recommendations

- Keep S89 open until the coordinator performs the separately authorized plan lifecycle transition.
- Preserve the explicit S66 dependency: replace the producer's free-form preflight detail/remediation only with real typed facts and verdicts, never by deriving an action from discarded prose.
