---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:fece52cfe983edd6d89e15a10b83b5c2fea2d30fadaeaedf010c2c4f7b6f3bf2'
step_id: 'S73'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium reconcile the two accepted decision records that now assert incompatible things about the bucket manifest

## Scope

- `.vault/adr/`

## Description

- Measure what actually reads the manifest before ruling on its future.
- Amend the earlier record so the corpus stops asserting both positions.
- Open the implementing row in the same action rather than leaving the
  amendment to execute itself.

## Outcome

The retirement wins and the corpus no longer contradicts itself. The manifest is
recorded as retired but present: no longer a durable format earning a version
ceiling, with the enrollment half of the earlier record withdrawn rather than
deferred.

**The row's own consumer count was wrong, and the amendment corrects it inside
the governing record rather than only in this one.** The earlier decision states
that the manifest reader is the sole ingress for sixteen production consumers.
The measured number is three, in two modules. The inflation is name-based: this
tree uses "manifest" for at least six unrelated artefacts -- attachment,
manual-fetch, orden, registry loader, corpus and blob-store -- so a census by
name counts all of them. That the wrong figure sat in an accepted record rather
than in someone's working notes is what makes it worth correcting there: it had
been re-read and reasoned from repeatedly.

The measurement also settles the hazard the row was written around. **A
pre-capsule bucket is unreachable through every operator path.** Profile listing
and profile resolution both project committed custody capsules, so a bucket
carrying a manifest and no capsule cannot be listed, cannot be resolved by
identifier or label, and cannot be authenticated into. Nothing that finds or
opens a profile reads the manifest at all. Such buckets hold their bytes and no
code path reaches them.

Of the three real consumers, two are per-bucket session-window overrides that
already fall back to configured settings when the manifest is absent, and the
third has no production caller. So the manifest's last functional dependency is
the session windows.

## Notes

The reader was deliberately NOT removed in this step, and the implementing row
was opened instead. Removing it would silently collapse per-profile session
windows to settings-only for every profile, which is a behaviour change disguised
as a deletion; whether those windows should survive the cutover as a capsule
field is a decision and now has its own row. The orchestration rule that an
amendment ruling on code is not self-executing is the reason the row was opened
in the same action rather than afterwards.

The two session-window readers also live in the module a concurrent step is
deleting from for unrelated reasons, so the sequencing was coordinated rather
than left to chance.

A second false justification was found in the bootstrap-exempt allowlist, which
explains one exemption by asserting the command reads plaintext manifests. It no
longer does. The exemption remains correct on other grounds -- the capsule
projection is also plaintext -- but its stated reason is false, and this is the
second such comment found in that one file in a day, the other citing a test that
was never written. A file whose exemptions are correct and whose reasons are
false is worse than one with no comments, because the next reader inherits the
reason instead of re-deriving it.
