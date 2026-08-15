---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:17a4ea07ba9cecec2ffd6cb2bd47ec243f6e422733d35a87d99cd00290841a3f'
step_id: 'S115'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium decide whether per-profile session windows survive the cutover as a capsule field or drop to settings only

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/core/config/`

## Description

- Establish whether any profile has ever carried a session window differing from
  the configured default, rather than arguing the question on principle.
- Rule on whether the capsule needs a field for it.

## Outcome

**Ruled: drop to settings-only. The capsule does not get the field.**

The question asked whether any profile has ever carried a non-default window.
The available answer is stronger: **no profile ever could have, because the
field has no producer and never had one.**

Four measurements, verified independently of the reporting agent. The manifest
model is constructed nowhere in production -- every construction is in a test.
Its writer is called only from its own package's tests. The last writer the
cutover removed was a passthrough that copied an existing value forward and
never originated one. And no operator surface sets it: zero references anywhere
in the entrypoints tree, with settings exposing global defaults only and no
per-bucket setter.

So a non-default value could only ever have arrived by hand-editing a plaintext
file. That is not a capability the application offers; it is an accident of the
schema -- two optional fields that readers honour and nothing can produce.
Adding a capsule field would therefore be **building a capability that has never
existed rather than preserving one that does.**

**The distinction this establishes matters beyond the row.** A
reader-without-writer is not an orphaned capability, it is a HALF-BUILT one.
That separates it cleanly from the two profile verbs restored earlier in this
campaign, where the implementation survived and only the operator door was
missing. The two are indistinguishable from the tree -- both present as a
surface honouring something nothing currently drives -- and only the presence or
absence of a producer separates them. The no-legacy ruling covers a half-built
surface directly, with none of the carve-out reasoning the orphaned capabilities
required.

A reader that honours a value no writer can originate is not preserving
behaviour. It is advertising one.

## Notes

The ruling materially simplifies the implementing step that waits on it. That
step was described as a deletion carrying a hidden behaviour change, because
removing the reader appeared to collapse every profile to the configured
default. With no profile able to differ from that default, it becomes a plain
deletion with nothing to disguise. The difference is entirely this measurement,
which is the argument for measuring before proposing made concrete.

The measurement also had to work around the same vocabulary collision recorded
against this campaign four times now: a search for writers of "the manifest"
returns the attachment manifest's writer among the first hits. The bucket
manifest, the attachment manifest and at least four other artefacts share the
noun, so every count here had to be filtered by which artefact it was about
before it meant anything.
