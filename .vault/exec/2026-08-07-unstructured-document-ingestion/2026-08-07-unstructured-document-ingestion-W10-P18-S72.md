---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ad1902796361d262fb7c257d540bf285643515840ef285de43274596c93340f0'
step_id: 'S72'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Complete the per-profile cloud-consent eligibility bar. The resolver already exists at application/user_profile/_capabilities.py, is exported, keyword-only, defaults off as the one capability that does, and is gestor-barred outright, with its own test file covering the bar. Do NOT rebuild it. What remains is the config check row surfacing the capability state to the operator, which does not exist on any CLI surface, and the surface sweep proving no consent gate is offered anywhere while the capability is off. Derive that surface set from the production mechanism that offers the acknowledgement rather than from a list written while building, and log anything excluded, since a silent cap reads as covered everything

## Scope

- `src/cadrumo/application/user_profile`
- `src/cadrumo/entrypoints/cli`

## Description

The standing per-profile eligibility bar for the off-host evidence read, one
layer above the per-invocation acknowledgement: eligibility asks whether this
profile may ever be asked, the acknowledgement asks whether the operator agrees
to one read.

## Outcome

`CLOUD_EVIDENCE_UPLOAD` is a live `ServiceCapability` again, and the only member
whose `default_enabled` is `False` -- an unanswered question anywhere else costs
a working feature, and here it would decide by silence that a taxpayer's
document may leave the machine.

Gestor mode is a bar rather than a strong default. The resolver applies it
BEFORE the profile fact is read and returns, so the opted-in branch is
unreachable rather than overridden, and the decision reports `SAFETY_FLOOR` as
its source. The barred set is one derived frozenset the resolver and its gate
both read, not a second list to forget.

The completeness claim -- no consent gate offered on any surface while the bar
is off -- is carried by the MINTING PATH rather than by each surface. A surface
can only offer a working acknowledgement by obtaining a token, and
`mint_evidence_consent_token` is the sole constructor, so routing the bar
through it makes the claim true by construction: a surface that forgot to hide
its prompt still obtains no token, and the operator is misled at most into an
acknowledgement that changes nothing. `profile_eligible` is keyword-only with no
default on both the gate and the minter, so omitting it is a TypeError.

The operator-facing half is `aeat config check`: the capability row already
rendered from the enum, and this adds the inconsistency the operator could not
otherwise see -- the profile opted in while the deployment never did, so every
read refuses with nothing naming which switch is closed.

Modified files:

- `src/cadrumo/core/_capabilities.py`: the reinstated member and the
  per-member default.
- `src/cadrumo/application/user_profile/_capabilities.py` and its facade: the
  gestor-barred set, the floor branch, and
  `cloud_evidence_upload_eligible_for_active_profile` as the single production
  reading.
- `src/cadrumo/llm/_consent.py`: `profile_eligible` on the gate and the minter.
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml` and the four
  locale catalogues: the profile fact and its labels.
- `src/cadrumo/entrypoints/cli/_config/_check_cli.py`: the check row.
- `src/cadrumo/tests/test_cloud_transport_fully_deleted.py`: the symbol moved
  from the deleted set to the reinstated set, with the presence assertion
  pinning the property it was reinstated FOR (it defaults off) rather than mere
  membership.
- New tests:
  `src/cadrumo/application/user_profile/tests/test_cloud_evidence_eligibility_bar.py`
  and `src/cadrumo/entrypoints/cli/_config/tests/test_check_cloud_evidence_row.py`.

## Verification

`pytest -n0 -p no:cacheprovider -m unit` over the eligibility gate, the
capability resolver, the consent gate, the enum/schema parity gate, the deletion
gate, the overview localization gate and the locale catalogues: `68 passed`.

`pytest -n0 -p no:cacheprovider -m integration` over the config-check row:
`4 passed`. The `unit` lane is the default and silently deselects `integration`,
so the two lanes are run and reported separately.

How the surface set is DERIVED: an AST walk of every shipped module for calls to
`mint_evidence_consent_token`, requiring each to source `profile_eligible` from
the canonical resolver. EXCLUDED, and stated in the test rather than capped
silently: `tests/` trees, because a test legitimately mints with a literal to
exercise the gate. The set is EMPTY today, since no CLI verb mints yet, so the
sweep is paired with a signature assertion that keeps it from being vacuous --
`profile_eligible` cannot be defaulted, so a future surface cannot omit it -- and
with an anchor test that the resolver still reads the capability it is named
for, so a rename cannot make the sweep pass over nothing.

The gate's condition matrix is now exhaustive: all sixteen states of
(deployment opt-in, gestor, profile eligibility, acknowledgement) are covered,
fifteen asserted to refuse via a comprehension filter and the sixteenth asserted
to mint, so the two together partition the space with no state untested and none
tested for both outcomes.

## Notes

NOT COVERED END TO END: the config-check issue FIRING needs a registered,
unlocked profile carrying an explicit opt-in fact, and this CLI lane has no
fixture for one -- every test in it runs with no active profile. Rather than
assert a condition that cannot arise and let it read as coverage, that branch is
pinned structurally (it must read the capability AND the deployment flag, since
either alone misfires) and the gap is named in the test's own docstring.

The enum landed ahead of its profile-schema field through a peer sweep, leaving
the enum/schema parity gate red at HEAD until the pair was completed; that is
recorded because the pairing, not either half, is the unit.
