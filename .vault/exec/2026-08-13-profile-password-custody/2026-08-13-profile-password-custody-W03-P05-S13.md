---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:a5d87496753fa833d6aa57f0cdde4e0e5babf47b954166ad3f0bdd298e6084df'
step_id: 'S13'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh rebuild deterministic sealed archive transport framing without recovery.wrap, shared-master assumptions, or retired format parsing

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/`

## Description

- Confirm before deleting that nothing produces a recovery wrap: the
  maintenance service retains no export or import surface, and the archive
  command family is no longer registered.
- Remove the recovery-wrap member, its writer parameter, its four
  header-agreement refusals, its reader, and the presence flag it carried
  through the header and both consumer payloads.
- Remove the member-cardinality rule, which existed only because the member
  set was negotiable.
- Replace the negotiable member set with one fixed tuple compared whole.
- Pin the archive schema version with a validator refusing in both directions.
- Keep the former-product marker and its pre-check, which refuse without ever
  parsing.

## Outcome

The framing carries one fixed member set and one pinned version.

The removed cardinality rule was itself the defect. The permitted tail meant
the code deciding whether to read a member consulted only the header, so
undeclared bytes could ride inside an archive that still read back valid.
Comparing the member set whole closes that.

The version pin makes the no-retired-format clause real. The reader previously
accepted any version at or above one and would parse a superseded framing,
while the error surface already claimed to refuse exactly that. The pin is a
forward marker; no branch reads an older shape.

The former-product marker was deliberately kept. It refuses and never parses,
opens, migrates or adopts, which is the existence-only detector the removal
step expects to still find, and a separate campaign pins it as a
product-identity guarantee. Deleting it would have removed another campaign's
guarantee under this row.

Verification: the bucket suites, crash windows, state identity and maintenance
pass together in under fifteen seconds. Three deliberate mutations, applied
from outside the repository so nothing under source was touched, each made a
gate fail to raise: restoring the permitted tail, admitting a version-tolerant
header, and returning the header unvalidated. All three passed again once
restored. The roundtrip asserts strict header equality across the real archive
boundary, every header field is required so none can be under-populated, and
the anti-tautology proof deletes a digest from the on-disk bytes and requires
refusal. Determinism is untouched and no clock entered the archive.

## Notes

The four stale archive locale keys were not removed. They were already stale
before this step, their producing code having been deleted earlier, and all
four catalogues currently carry uncommitted work from other campaigns while the
locale tool rewrites whole files — removing them would have captured peer work.
The catalogue drift check is already failing tree-wide from several campaigns,
so removing these could not have greened it. They are handed forward to the
step that owns the locale surface.

The archive roundtrip test is entirely dead and was not resurrected. Every case
fails because the command-line profile creation verb no longer resolves, which
also reds every acceptance wall on that surface and leaves orphaned schema
registrations for deleted commands. That is a separate, larger regression than
this step, now tracked on its own row. The recovery-wrap dimension was stripped
from the test and the acceptance catalogue pointer updated to match, so the
capability stays guarded and reports as regressed rather than missing once the
verbs return.

An earlier report from this step of a tree-wide registry import cycle and a far
larger collection-error count was a transient peer mid-save and is withdrawn;
the count matches the concurrent campaign's own eighteen.
