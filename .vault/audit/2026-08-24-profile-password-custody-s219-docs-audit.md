---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:709ad5fd1bf8d2928e22d040d3f556f852d344ab6ae128d0edff8af6fdf04c12'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `profile-password-custody` audit: `S219 mandatory recovery documentation`

## Scope

Audit the S219 operator-facing custody documentation, locale-owned CLI help,
and regenerated sequence evidence against the accepted mandatory verified
recovery-at-creation, cannot-add-later, restore-only, and password-login-
independence decisions.

## Findings

### generated-profile-setup-sequences | high | Five committed sequence contracts cannot execute under the mandatory secret and recovery channels

The generated-source check `python -m dev.docs.sequences check --page
how-to/profile-setup` reports five divergences. `profile-setup-multiple`,
`profile-setup-worked-example`, `profile-setup-capabilities`, and
`profile-setup-history` still invoke headless `profile create` without a
passphrase channel or the paired recovery handoff and verification channels;
`profile-setup-logout` expects a successful status response after the seeded
profile has no resumable login session. The committed JSON goldens therefore
do not currently witness the live mandatory-recovery CLI. The sibling
`how-to/protect-data-access` sequence page checks cleanly.

### unavailable-recovery-artifact-export | medium | Operator guidance requires an artifact that no live CLI command can export

`docs/how-to/protect-data-access.md` tells the operator to keep the phrase with
its separately exported recovery artifact, and the reference repeats that the
artifact is required for the explicit restore proof. The live CLI exposes
`profile restore --artifact` but no recovery-artifact export command. The only
callers of `export_profile_recovery_artifact` are tests; no production CLI
surface gives an operator the artifact the guide requires. The restore-only
description is semantically correct once an artifact exists, but the documented
operator journey is not executable and leaves the mandatory creation phrase
without its documented portable proof.

## Recommendations

- Update every affected profile-setup sequence contract to use a real bounded
  passphrase channel and paired recovery handoff/verification channels, or a
  truthful seeded-profile prerequisite where creation is not the subject;
  regenerate through `python -m dev.docs.sequences refresh --page
  how-to/profile-setup`, then require the corresponding `check` command to pass.
- Add and document the accepted authenticated, exclusive recovery-artifact
  export surface, or state the current capability gap instead of instructing
  operators to perform an unavailable export. Keep the artifact explicitly
  restore-only and separate from normal archives.
