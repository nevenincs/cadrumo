---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:438efba883817569d5febaec824243378fb38acf97092bd02012d0e3b3436498'
step_id: 'S203'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium close the catalogue-key shape that no gate can see, being keys held in a dictionary constant whose name carries no locale-key suffix and read through a lowercase local into the translator, which is invisible to the key scanner because it never sees a literal and out of scope for the constant-naming gate because the constant is not named as one, this shape having caused one of the four known orphaning incidents and being covered today by no gate at all

## Scope

- `dev/locales/_ast_scanner.py`

## Description

- Establish whether the invisible catalogue-key shape is detected at all.
- Verify the detector bites rather than merely existing.
- Fix the real violations it reports.

## Outcome

The detection this row asks for was already built, and it is built the right
way. The scanner recognises a locale-key registry by SHAPE as well as by name:
a dict literal whose every value is a dotted key, confirmed by flow analysis to
actually reach the translator. Its own docstring names the incident -- a dict
constant carrying neither the required suffix nor a literal call site, read
through a lowercase local into the translator, invisible to the declaration
suffix check and out of scope for the call-site naming gate because that gate
deliberately excludes lowercase arguments as genuinely dynamic.

Flow confirmation rather than shape alone is the part worth preserving. A
lookup table mapping one dotted identifier to another, never reaching a
translator, has the identical shape; requiring the flow keeps it from being
misread as a key registry, and the suite proves that both ways -- a
same-shaped dict that never reaches the translator is ignored by the rule AND
by discovery.

The gate is proven rather than merely present: a case asserts the rule fires
on the exact historical orphaning shape, and another asserts discovery now
resolves that shape WITHOUT a rename, so key visibility no longer depends on
anyone remembering the convention.

What remained was the row's actual outstanding work: the repo-wide case was
red, reporting four real registries declared without the required suffix.
Renamed, all sites, no cross-module consumers. The gate is now green at 11/11.

Both halves matter and they are different guarantees. Discovery by shape means
the keys are FOUND regardless of naming, so nothing orphans. The naming rule
means the constant is also legible AS a registry to a human reading it. The
first prevents the incident; the second prevents the next author recreating the
conditions for it.

## Notes

Three failures elsewhere in the locale suite are unrelated and pre-existing:
two dynamic translation prefixes in the errors namespace that are neither
registry-covered nor allowlisted, and one dead allowlist entry the scanner no
longer emits. None involves the four renamed files. They belong to whoever owns
that namespace, and the dead-entry case is the allowlist liveness check working
as intended.
