---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e868b1115feac8bc6b9f9d562ba4c5edc23799dfec135ec90a8d8c81bf82f190'
related:
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]"
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# `quality-gate-zero-closure` audit: `never emitted decidability measurement`

## Scope

The audit tested whether the proposed never-emitted-literal class is decidable
enough to support a zero-finding per-push gate. The measured detector accepted
only exact string-literal `not in` assertions over captured output. It then
required the asserted literal to occur exactly once in its own module and
nowhere in the declared `.py`, `.yml`, `.yaml`, `.toml`, `.json`, and `.md`
corpus under `src` and `dev`. This is stricter than the originating probe,
which excluded the whole asserting module and reported 83 candidates.

## Findings

### never-emitted-decidability-measurement | critical | corpus absence does not decide assertion blindness

The refined live sweep read 3,972 test modules and 29,845 corpus files and
still reported 22 assertions. Several are demonstrably meaningful guards. The
plain-help test positively asserts the complete long option spellings and
negatively asserts Rich's ellipsis-truncated renderings; those truncated forms
can be produced by runtime layout even though their literal text appears
nowhere in the corpus. The startup smoke test rejects interpreter and
environment failures such as an import-name failure and a missing secret
variable; those messages can originate outside the repository. Both shapes
are mechanically identical to a product-owned absence literal with no possible
producer in the inspected corpus.

The discriminator is therefore provenance and runtime semantics, not corpus
membership. A broader join produces known false positives. A narrower textual
join preserves the same false positives whenever a renderer, dependency,
interpreter, operating system, user-controlled value, or composed helper can
produce the text. No AST or source-corpus fact distinguishes the meaningful
case from the blind case.

### never-emitted-decidability-measurement | high | a zero-finding detector would encode suppression as precision

Making the 22 live findings pass would require site exemptions, an accepted
population, or intent declarations that the detector cannot validate. Those
are respectively an exclusion, a baseline, or an unchecked allowlist under the
campaign constraints. Treating the diagnostic floor as proof would instead
force deletion of valid regression and confidentiality assertions. The
prototype was deleted after measurement so it cannot survive as a second,
knowingly weaker mechanism.

## Recommendations

Contract the never-emitted-literal detector step under the governing decision's
explicit undecidable-class rule. Retain corpus absence only as optional
diagnostic evidence during human or mutation triage; do not install it as a
pass/fail gate. Amend the accepted decision and plan record so they no longer
claim this class is decidable, while preserving the original measurement as
historical evidence.
