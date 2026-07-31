---
tags:
  - '#exec'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:0d09db4c17d4ea8811569f8233af4e1b48113c1814d5dd39c036abcd68d9aed2'
step_id: 'S05'
related:
  - "[[2026-07-25-code-dedup-sweep-plan]]"
---

# Record the inner-re-stamp obligation on the upgrader registration surface so the first registered hop inherits it explicitly, without fabricating an old-shape fixture that no-legacy-compatibility forbids

## Scope

- `src/cadrumo/adapters/persistence/storage/_schema_lineage.py`

## Description

Record the obligation that a registered upgrader must re-stamp the payload's
inner envelope version, on the registration surface itself, so the first
registered hop inherits it explicitly rather than by luck. Do not fabricate an
old-shape fixture to prove it.

## Outcome

Landed in commit `b45ac7fecc`, a docstring-only change to `_schema_lineage.py`.

The obligation is recorded in three places, each chosen rather than duplicated.
The `SecureObjectSchemaUpgrader` type alias is the load-bearing one: it read
"pure bytes-to-bytes, never touches ciphertext or row metadata", which implied
version fields were out of scope for a hop. They are not — the inner envelope
version is payload CONTENT, not row metadata, and re-stamping it is part of the
hop's job. That misleading sentence was the most likely cause of a future
half-written upgrader, so correcting it is the substance of this step rather
than the surrounding prose. `register_secure_object_schema_upgrader` carries the
normative obligation and the asymmetry that makes forgetting it silent; the
module docstring points at it.

The asymmetry is stated because it is the whole reason the obligation needs
recording. The row codec re-stamps the OUTER record to current unconditionally,
so a row whose upgrader forgot the inner stamp has already been declared current
by layer one before anything reads it. The inner stamp moves only if the hop
moves it, and the equality predicate landed in S01 is therefore the only
read-time detector — layer one cannot see the fault, because from layer one's
perspective nothing is wrong.

## Notes

The obligation is honestly VACUOUS today and the docstring says so in its own
words rather than implying coverage it does not have. No hop is registered while
every namespace sits at its from-birth version, and there is no way to prove the
rule executably without an old-shape payload — which the pre-release regime
forbids inventing, since it would be a shape nothing ever wrote. The docstring
therefore names what the first real hop owes in the same commit: the upgrader, a
committed pre-bump serialized fixture, and a restorability test that loads those
bytes through the real production read path. The proof arrives with the first hop
that can actually carry it.

No executable gate was added for this step, deliberately. A test asserting the
upgrader registry is empty would red on the first legitimate hop, which is a gate
failing on correct work — the same wrong-reason failure this campaign rejected
elsewhere. The existing chain-completeness gate already reds on a bump without an
upgrader; what it cannot check, and what nothing can check before a hop exists, is
whether that upgrader re-stamps.
