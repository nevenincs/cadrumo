---
tags:
  - '#audit'
  - '#google-app-identity'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:793832770854d4a3b26de905bf046575e6a3979cc98012c1fb663b8ceadf350e'
related:
  - "[[2026-10-04-google-app-identity-plan]]"
---

# `google-app-identity` audit: `Plan-close review of the Google app identity refactor`

## Scope

Plan-close review of `2026-10-04-google-app-identity-plan`, Steps S01 to S13,
against `2026-10-04-google-app-identity-adr`. An independent reviewer read the
committed range `0d13e26f74..73a64eda93` and nothing from the working tree. It
checked the ten commitments, dangling names of removed surface, the refusal
effect accounting of S12, the sign-in and root-folder logic of S07 and S05,
test quality, and the ledger against the code. It did not run the style,
format or type gates and no live run against Google exists.

Verdict as returned: revision required, on one high finding. The fixes are
recorded under each finding.

The same reviewer re-reviewed the fixes in `8fa0aee6c9..5ded641487` and again
returned revision required, on the finding grant-after-completed-exchange. It
confirmed the stored-root fix and the tests of both commits.

## Findings

### refusal-effect-accounting | high | A lost answer during consent or token exchange settled the sign-in as no effect

S12 released every boundary admitted without a write when a refusal arrived,
on the reasoning that a read cannot change anything. Two boundaries admitted
that way do change remote state: the browser consent and the token exchange
(`src/cadrumo/adapters/outbound/google/oauth_flow.py:338`, `:364`). If the
token request timed out after the user consented, Google could hold a grant
the application never stored while the operation reported that nothing had
happened. That contradicted the constraint S12 was written under.

Resolved by reopening S12: a boundary is now released only when the refusal
itself proves nothing was applied, whatever kind of boundary it was
(`src/cadrumo/application/user_profile/google_configuration_executor.py`,
`settle_refusal`). The test case that had endorsed the wrong behaviour was
replaced by two: an unproven refusal after a token exchange stays unknown, and
a proven one settles with no effect.

### stored-root-not-visible | medium | A stored root folder Drive does not show settled as an error rather than a refusal

`require_owned_folder` let the not-found error from the read-back through.
That error is registered in the error category, and the supervisor settles
only refused-category errors as refusals, so a profile whose folder was
created under another client would have had its spreadsheet operations, the
Sheets export and the archive push settle as failures. That is the case the
decision record resolves with "the user exports again".

Resolved: the read-back now turns not-found into the same refusal as any
other stored root that is not a live folder of this application, with the
fact `visible_to_application` false
(`src/cadrumo/adapters/outbound/google/root_folder.py`).

### environment-template-leftovers | low | The environment template still declared the impersonation test variables

`env/.env.example` kept `AEAT_IMPERSONATION_TARGET_PRINCIPAL` and
`GOOGLE_APPLICATION_CREDENTIALS` after S01 removed everything that read them,
and the environment-reference test allow-listed them. Resolved by another
session in `d4afc04204`, outside this plan.

### withdrawn-names-in-comments | low | Three production comments named surfaces the plan withdrew

`src/cadrumo/application/ledger/evidence.py:86` and
`src/cadrumo/domain/transactions/models.py:596` named `doclink` and
`pull-folder`, and `src/cadrumo/domain/attachments/enums.py:54` described the
source taxonomy as serving re-fetch logic. Resolved with the medium finding.

### live-proof-commit-subject | low | The S10 commit subject claims a proof the ledger records as not run

Commit `0e779076a5` is titled as proving the export against Google, while the
ledger records that the live run has no passing result. The commit is no
longer the branch head and other sessions have committed above it, so it was
not rewritten. The code and the ledger are accurate; the subject overstates.

### removed-commands-cited-as-live | medium | The upgrade section named removed commands in the form the documentation gate resolves against the live CLI

Not found by the reviewer; reported by another session after the review. The
table added in S09 to `docs/how-to/review-with-google-sheets.md` wrote the
five removed commands with the `aeat` executable in front, and
`src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`
checks every such citation against the live command tree, so the page failed
that gate from commit `73a64eda93` onwards. S09 had run the translation and
catalogue checks but not this gate.

Resolved: the removed commands are named without the executable, as the same
section already names the commands whose output changed, and the five rows
were retranslated in the Spanish, Catalan and Hungarian catalogues.

### grant-after-completed-exchange | high | A refusal raised after Google had answered the token exchange still settled as no effect

Found by the re-review of commit `8fa0aee6c9`, which otherwise confirmed that
a lost answer now stays unknown. The token exchange was acknowledged as a
boundary that writes nothing, so once it completed it left no trace in the
effect accounting. A sign-in refused afterwards (a missing scope, a missing
identity claim, no refresh token, a root folder that could not be created)
settled as having changed nothing, while Google held a grant for the account.

Resolved by reopening S12 a second time: the exchange is admitted and
acknowledged as a change (`src/cadrumo/adapters/outbound/google/oauth_flow.py`,
`AdmittedInstalledAppFlow.fetch_token`), so a refusal after it settles as a
partial effect. A test drives the real flow against a local token endpoint
that answers without a refresh token and asserts the boundaries it reported.

### declined-consent-reported-as-unreachable | medium | Declining on Google's consent page failed as an unreachable endpoint with an unknown effect

Found while verifying the finding above, by running the real flow with the
redirect Google sends for a declined request. Every failure of the local
consent server was translated to the network failure, so a declined consent
settled as failed, effect unknown, with a message about the endpoint being
unreachable. It is a definitive answer that no authorization code and
therefore no grant was issued.

Resolved: the declined answer is now the sign-in-required refusal with its own
message in the four catalogue languages and the condition
`google.auth.consent.granted`, and the operation accepts it as proof that
nothing was applied (`src/cadrumo/adapters/outbound/google/oauth_flow.py`,
`_raise_local_server_error`). The locale audit reports the three translated
messages only for the word Google being absent from its spelling dictionary,
as it does for every existing Google message.

## Recommendations

- The high and medium findings needed no new decision and are fixed within
  the existing commitments.
- The live proof remains the one piece of evidence this plan cannot supply.
  Until the operator runs it, the scope change, folder creation, the
  ended-grant mapping and the loopback redirect are unverified against Google,
  and the workbook-creation gap under commitment 7 stays open.
- Whoever next changes the effect accounting of the Google configuration
  operation should treat "admitted without a write" as a statement about the
  request, not about the provider's state. This review found that the two were
  conflated once.
- The import-boundary gate currently fails on a malformed ratchet entry and a
  finding in the LLM adapter tests, neither in this plan's paths. The plan's
  own evidence for that gate is therefore the passing runs recorded under S05
  to S08, not a run at plan close.
