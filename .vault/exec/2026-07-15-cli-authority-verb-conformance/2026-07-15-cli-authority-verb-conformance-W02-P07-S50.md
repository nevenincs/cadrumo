---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S50'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S50 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Make the certificate authenticator and adapter provider factory consume the resolved typed active certificate credential directly, eliminating their independent path and password projection from Settings and ## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`
- `src/cadrumo/adapters/outbound/aeat/auth/__init__.py`
- `src/cadrumo/adapters/outbound/aeat/auth/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make the certificate authenticator and adapter provider factory consume the resolved typed active certificate credential directly, eliminating their independent path and password projection from Settings

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`
- `src/cadrumo/adapters/outbound/aeat/auth/__init__.py`
- `src/cadrumo/adapters/outbound/aeat/auth/tests`

## Description

- Confirm the certificate authenticator consumes the resolved typed active certificate credential directly, with no independent path or password projection from Settings.
- Confirm the adapter provider factory requires and forwards the resolved certificate credential when constructing the certificate provider.

## Outcome

Verified complete against the committed tree. `AeatAuthenticator.__init__` requires `credentials: ActiveCertificateCredentials`; `_require_bundle` and `describe` read the certificate path, password, and friendly name only from `self._credentials`, not from Settings fields. The adapter factory `select_provider` refuses certificate construction without `certificate_credentials` and passes the typed credential straight through. The adapter authenticator suites are green: `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/auth/tests/test_authenticator_part1.py test_authenticator_part2.py test_auth_provider_real_lifecycle.py test_health.py test_certificate.py -q` reports 64 passed.

## Notes

The authenticator's credential-consumption refactor landed in the W02.P07 credential-unification wave (commit `f5273bda59` and the subsequent in-flight freeze snapshots); this step is closed as verified-complete with its real-behavior adapter suites green rather than by an additional source commit.
