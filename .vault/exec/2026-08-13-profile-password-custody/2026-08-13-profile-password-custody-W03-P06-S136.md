---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S136'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh finish the creation-door conversion enumerated by CALL SITE of the creation verb rather than by named helper

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/entrypoints/cli/_config/tests/`

## Description

- Enumerate by invocation rather than by definition.
- Convert only where the invocation is a precondition, refusing with a stated
  reason everywhere else.
- Read each unmapped flag's fact path from the authority that declares it.

## Outcome

**The convertible population is exhausted, and the row closes on a measured
state rather than on a claim of completion.** Re-measured against the same census
that opened it: 99 call sites down to 65, and the success-expecting target — the
actual conversion set — down from 55 to 23.

Every one of the 23 remaining is refused for a stated reason rather than left
pending. Four read the invocation's result afterwards, so the test observes the
CLI surface and converting would silently delete that observation. Three sit in
a shape the gate does not recognise. One builds its profile name from an
expression, so there is no literal to map. The rest are in the four
creation-surface modules that are out of scope by ruling.

**The gate is what makes those refusals results rather than remainder.** It
refuses any site unless the invocation's result is asserted for a zero exit AND
never read again — because a result read later means the test is observing the
surface rather than provisioning through it. Eleven sites were refused across
the row. Eleven quietly forced conversions would have read as complete in a
diff and deleted surface assertions nobody would have missed until much later.

Ten flags were read from the wizard catalogue, which declares each flag's
identifier and its profile key together. **Not one turned out to be a dead
flag**, so the gap was in the conversion map every time rather than in the CLI
surface — the flag set and the catalogue agree, and all the drift was test-side.
That is only visible because the alternative was checked each time rather than
assumed.

The sweep removes more than it adds: inline invocations of eight to twenty lines
collapse to four-line registrations.

## Notes

**The enumeration was wrong twice before it was right, and both corrections are
the row's real content.** A census of functions matching a provisioning NAME
cannot see a test that invokes the verb inline in its own body, and a text
pattern over modules answers a question that does not determine the work — a
module with four inline invocations needs four fixes, not one. Thirty named
helpers, fifty-one modules, ninety-nine call sites: three numbers, each correct
about its own question, only the last of which sizes the work.

Seventy of the original ninety-nine sites were inline, so helper conversion
could ever have reached at most twenty-nine percent of it. That converts an
argument about method into a measurement about coverage.

The remaining thirty-six sites assert no exit code at all — they assert on
output or on later state — and are rowed separately rather than absorbed. They
are a reading job rather than a sweep, and sizing that honestly before starting
is the same discipline that produced the third census instead of acting on the
first.

Four module-scope constants are named individually by file and line rather than
counted, because an argument list outside any function is invisible to a
converter walking helper bodies, and that blind spot has already produced one
wrong-and-green fixture in this campaign.
