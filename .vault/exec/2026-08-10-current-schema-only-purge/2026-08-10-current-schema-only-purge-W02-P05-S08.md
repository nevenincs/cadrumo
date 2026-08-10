---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:fc73a71d7b68fd1996db4ef69610b636b9a9c29e1f2f9abf3f9d2ef223b5bbfb'
step_id: 'S08'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require and explicitly write the exact current CipherEnvelope marker

## Scope

- `src/cadrumo/adapters/persistence/storage/envelope/_envelope.py`

## Description

- Drop the default from the outer cipher-envelope version field so the marker is
  required.
- Stamp the version explicitly at the writer rather than relying on the field to
  supply it.
- Record in the field docstring why a default equal to the current version is
  the failure being removed.

## Outcome

Landed in `44ead4e` with its proof step.

The equality gate and its ordering were already correct here: the outer version
is compared before the master key is consulted, and a test already asserted that
ordering. What was open is subtler and is the shape this campaign keeps finding.
The field carried a default EQUAL to the current version, so a stored document
omitting the key hydrated as current and the equality gate then passed it. The
gate read as enforcement while the one payload it most needed to catch walked
through it.

That is why the marker being present in the model is not evidence it is enforced,
and why a version check should be read together with the field's default rather
than on its own.

## Notes

The dormant schema-lineage machinery next to this boundary was left untouched:
the empty upgrader registry, the durability floor and the forward ceiling all
read no obsolete shape and are forward-only controls the governing compatibility
decision keeps.
