---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8ed9edbcd9e6afad949ce784a504b52342b89dce676601d8b49e5618d5d8d687'
step_id: 'S15'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and project and regenerate safe conditional leaf machine-secret metadata and root profile_authentication posture across registration metadata, command schemas, CLI tree artifacts, and their tests

## Scope

- `dev/quality/generate_command_registration_metadata.py and generated CLI metadata artifacts`

## Description

- Ground the retired registration-cache history and current immutable command-graph authority through semantic code and ADR discovery, exact-symbol search, current-HEAD inspection, and the earlier S03-S05, S07, and S20 records.
- Extend direct registration metadata with the bounded strict-object and same-scope collision guarantees for every conditional leaf payload.
- Carry graph-derived `profile_authentication` posture and its value-free root contract through every verb-input schema.
- Expose the projection through the public command-contract API and enrich the build-time `cli-tree.json` discovery surface with exact leaf payloads, leaf posture, and the root collision contract.
- Add exact-set parity gates for five leaf adopters, both restore variants, self-authenticating rotation, all other command postures, root-only contract placement, strict bounds, value absence, deterministic serialization, and no outside adopters.
- Regenerate the gitignored CLI-tree through its canonical build-time generator and retain physical-absence gates for the retired registration JSON, lazy manifest, and both obsolete generators.
- Run focused tests, lint, typing, import-boundary inspection, generated-tree inspection, reference drift probing, and an independent SOL architecture review.

## Outcome

Machine discovery now derives exclusively from the immutable command graph. The five scalar-secret leaves expose field names, JSON types, conditional restore selection, the 8 KiB limit, same-scope exclusivity, duplicate-key refusal, and extra-field refusal without projecting values, defaults, examples, hashes, runtime lengths, or credential state. Every command-registration row and verb-input schema carries its graph-derived root authentication posture; passphrase rotation remains `self-authenticating`. The build-time CLI tree projects the exact same leaf contracts and postures and places the root profile-authentication contract only on `aeat`.

The retired registration cache and generator are not restored. Their names remain only in negative distribution and source-authority gates that prove those files cannot re-enter the runtime or shipped cohort. `docs/_static/cli-tree.json` remains gitignored and build-generated rather than becoming a committed cache.

## Notes

- Focused metadata, command-graph, profile-authentication, CLI-tree, sequence-build, and authority suites passed 65 tests, followed by 38 tests after the final public-API adjustment. Scoped Ruff and `ty` passed with zero findings.
- A broader mixed test command selected four unit tests under the repository marker policy; three passed and the existing profile-guard recovery test failed because it still expects implicit profile-create secret fallback removed by this campaign. The failure has no S15 source overlap.
- The import-linter retained nine contracts and reported the repository's existing application-to-adapter boundary debt; no reported edge names an S15-owned module.
- The CLI reference drift command could not start its formatter because the current environment lacks the `mdformat` module. S15 changes no Typer signature and no managed reference region; the canonical CLI-tree generator itself completed and its emitted secret projection was inspected directly.
