---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:302aa2434e75be47aff79017b8f9157dd14923290283736ab565e9ddd2643b7c'
step_id: 'S11'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then prove real TUI scripted CLI and all-language parity at scalar byte surrogate and exact-Unicode boundaries with no persistence on refusal

## Scope

- `profile credential inbound tests`

## Description

- Add a strict bounded profile-creation secret-stdin channel using the existing hardened reader.
- Prove missing/mismatched confirmation, malformed JSON, extra fields, and the 8 KiB bound refuse without echo or profile creation.
- Prove all supported locales interpolate complete, distinct real prospective and authentication messages.
- Run the combined real TUI and scripted creation boundary lane.

## Outcome

Scripted profile creation now accepts exactly one strict machine payload containing a passphrase and its confirmation. The lazy command exposes one `--secrets-stdin` option without changing the interactive arm. Locale parity covers all five stable credential messages across English, Spanish, Catalan, and Hungarian.

The real scripted matrix covers 14/15/256/257 scalars, 1,024/1,025 strict UTF-8 bytes, both surrogate halves, and composed/decomposed accepted sequences. The real headless TUI accepted matrix covers 15/256/1,024 and both composition forms alongside its refusal matrix. Every accepted profile unlocks with the exact submitted sequence; composition counterparts do not unlock it.

Ruff passes. Five language-parity cases and 44 combined TUI/scripted integration cases pass serially in 36.08 seconds. The focused locale lane passes in 3.36 seconds.

## Notes

The live CLI had no creation secret-stdin capability at the start of this step; the minimal production addition was explicitly authorized. Locale catalogues were not changed. The previously classified unrelated Modelo 036/390 scaffold/audit drift remains outside this step.

Review remediation added the missing cross-surface boundary matrix and command-contract bite. The original 14-scalar refusal is exercised under every supported language; every refusal excludes message keys, raw custody English, traceback, INTERNAL guidance, the candidate, and internal type markers while leaving storage empty. Lazy command help proves the option appears exactly once.

The second review remediation pins the complete real JSON refusal envelope for each supported language, including the exact selected translation, exclusion of the other three translations, stable category/code/action/context, and the standard non-retryable metadata. This bite exposed a genuine scripted-dispatch defect: the create diversion had bypassed the canonical subcommand output-language activation, so non-Spanish requests inherited the ambient Spanish locale. The diversion now activates its declared language before resolving or assessing the credential.

Creation-channel tests now prove both mismatched submitted values and the actual 9,000-character over-bound value are absent from stdout and stderr, with no profile created for missing, malformed, extra-field, over-bound, or mismatched payloads. The live help and lazy verb-input schema independently expose exactly one `--secrets-stdin` parameter.

Serial verification passes 44 real scripted/TUI integration cases in 39.02 seconds and five locale parity cases in 3.63 seconds. Ruff check and format-check pass on all changed production and test paths. `uv run python -m dev.locales scaffold --check` continues to report only the already-classified unrelated Modelo 036/390 catalogue drift; the subsequent full audit was stopped after it continued traversing that same large unrelated drift without feature-local findings.
