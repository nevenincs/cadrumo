---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s91-validator'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:17295f582a15e375040fb49fe178318b4acc2269fc805c5ce21fd5f61194e529'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s91-validator` audit: `S91 locale validator code review`

## Scope

- Independently review commit `ee4bb7f9ad9d772461b8ef7f7cd46a14fa70b6ed` against S91's validator contract, execution record, plan state, production interpolation behavior, manager architecture, CLI delegation, tests, and committed catalogues.
- Probe simple, converted, formatted, attribute, indexed, and nested format fields; escaped, positional, prose, JSON, and malformed braces; strict-renderer failure behavior; deterministic structured diagnostics; exact scalar types; symmetric key drift; all-locale placeholder variants; live CLI behavior; and test-policy compliance.
- Make no implementation fix and preserve all concurrent shared-tree work; create and commit only this audit record.

## Findings

### s91-formatter-field-coverage | high | The shared extractor omits fields consumed by the production renderer

`extract_placeholders` accepts only a complete identifier as the field name returned by `string.Formatter.parse`. Production interpolation delegates to `rendered.format(**values)`, which also consumes attribute fields such as `{user.name}`, indexed fields such as `{items[0]}`, and replacement fields nested inside format specifications such as `{amount:{width}.{precision}f}`. Independent probes show the first two render successfully while the extractor returns an empty set, and the nested case renders while the extractor reports only `amount`. The manager, call-site parity tests, and strict renderer therefore share one implementation but not the renderer's actual grammar: they can miss absent or renamed root kwargs and nested-spec kwargs. This defeats S91's central validator guarantee and blocks S67.

### s91-strict-survivor-regression | high | Strict mode permits unresolved named placeholders after format-pass failure

S91 replaces the post-interpolation surviving-placeholder check with a pre-interpolation set difference. Python's format pass is all-or-nothing: JSON-like braces, prose braces, a positional field, or a malformed brace can raise `KeyError`, `IndexError`, or `ValueError`, after which `_interpolate` returns the unresolved string. If the caller supplied the simple named kwarg, the precomputed missing set is empty and strict mode returns the surviving `{name}` instead of raising. For malformed input, `extract_placeholders` discards every format-style name and strict mode also returns `{name}` when no kwarg was supplied. This regresses the previous strict postcondition and contradicts the claimed safe handling of literal, JSON, positional, and malformed braces. It blocks S67.

### s91-record-new-test-count | low | The execution record overstates the number of added audit tests

The new `test_audit.py` module collects eight tests, including the two parameter variants, not eleven. The complete requested slice still collects and passes exactly 53 tests from the exact S91 tree, so this is a nonblocking evidence-count defect rather than a behavior failure.

No critical or medium findings were found. Verdict: **FAIL** because the two HIGH findings invalidate the shared grammar and strict-renderer acceptance contract.

The remaining architecture is sound. `extract_placeholders` is exported from the public i18n facade and is reused by the renderer, manager, and parity tests. Extraction stays behind the strict test flag in `tr`, so production rendering does not pay the parser cost. Manager records are frozen dataclasses containing tuples and frozensets; repeated audits are equal and deterministically ordered. Independent real-filesystem probes reproduce exact `NoneType` and `bool` scalar violations, union-based inter-locale missing keys, complete sorted placeholder variants for all four locales, and immutable results without selecting a canonical locale.

The CLI receives a manager-owned `LocaleAuditResult`, renders without recomputing policy, emits codebase, inter-locale, scalar-type, and complete placeholder-variant findings, and exits one on failure. `scaffold --check` delegates to the same audit path. Tests import production `extract_placeholders` and `LocaleManager`, use real temporary YAML and the live Typer runner, and introduce no fake, mock, stub, patch, monkeypatch, skip, xfail, mirrored parser, or tautological business assertion. S91 changes no YAML catalogue.

From an exact archived S91 tree, all 53 requested i18n, audit, and parity tests pass. Ruff check, Ruff format check, Ty, and `git diff --check` pass on all six changed Python paths. With isolated CADRUMO storage and database settings, live `python -m cadrumo.locales audit` and `scaffold --check` both report `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` as `ok`. A later shared-branch identity commit makes the same test command report two unrelated casing failures in the current checkout; the exact S91 tree establishes that those are not part of this commit.

The plan closes S91 while retaining S62-S67 open. The execution record correctly describes the manager, CLI, YAML scope, 53-test result, static gates, live commands, and storage isolation apart from the LOW test-count statement above.

## Recommendations

- Keep S67 open and remediate both HIGH findings before accepting S91.
- Define extraction in terms of kwargs consumed by the complete formatter grammar: attribute and indexed fields should report their root kwarg, and nested format specifications should be parsed recursively for their own named fields.
- Restore a strict postcondition that rejects surviving supported placeholders after any failed format pass, or replace the all-or-nothing format pass with a renderer whose explicitly supported literal/JSON behavior and extractor grammar are identical.
- Add production-importing acceptance tests proving `{user.name}`, `{items[0]}`, and `{amount:{width}.{precision}f}` extraction, cross-locale audit drift, missing strict kwargs, and successful rendering when supplied.
- Add strict tests for `{name}` combined separately with JSON, prose, positional, and malformed braces; no case may return an unresolved named placeholder silently.
- Correct the execution record's new-audit-test count from eleven to eight.
