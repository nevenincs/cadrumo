---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Make the certificate authenticator and adapter provider factory consume the resolved typed active certificate credential directly, eliminating their independent path and password projection from Settings

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S50` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Make the certificate authenticator consume the resolved typed active certificate credential directly.
- Eliminate the authenticator's independent certificate path and password projection from settings.
- Make the adapter provider factory require and forward the resolved credential when constructing the certificate provider.

## Outcome

The end state is confirmed at HEAD by direct inspection of
`src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`. The module imports
`ActiveCertificateCredentials` from the application credentials module. The
constructor takes `credentials: ActiveCertificateCredentials` as a required
keyword parameter and stores it as `self._credentials`. Every certificate read
in the module goes through that field: the bundle guard tests
`self._credentials.certificate_path` for absence and for file existence and
`self._credentials.password` for absence, and the describe path reads path,
password, and friendly name from `self._credentials` alone. The settings import
survives only under an alias used for an unrelated browser navigation timeout
default and for the type annotation of the separately-passed settings object; no
certificate path or password is projected from it.

Attribution is a single focused commit: `5184f49266`, "refactor(auth):
certificate authenticator consumes one typed credential bundle", dated
2026-07-16.

The originating record reports the adapter authenticator suites green at
sixty-four passing tests across the two authenticator modules and the auth
provider lifecycle, health, and certificate modules.

## Notes

Substantiated on end state and on delivery, but the originating record's
attribution was wrong and is corrected here.

That record attributed this work to commit `f5273bda59` and unnamed subsequent
freeze snapshots. `f5273bda59` does not touch this file. Its diff spans exactly
six paths, all under the application auth package, and none under the outbound
AEAT adapter. The commit that actually performs this refactor is `5184f49266`,
whose subject line names the change precisely. This reconciliation attributes
the step to `5184f49266`.

The originating record also closed this step as verified-complete rather than as
delivered, on the belief that no further source commit was needed. That
conclusion happened to be right, but it rested on a misattribution, so the
record offered no recoverable delivery evidence. It does now.

Two later commits revised this file after the step landed: `d2277aa977`, an
in-flight freeze of the AEAT auth adapter refactor covering browser certificate
lifecycle and provider split, and `a9e22536b0`, a decomposition of the provider
hot paths. Neither reintroduces a settings-sourced certificate projection; the
credential field remains the only source.

The verification figures quoted above are transcribed from the originating
record and were not re-run.
