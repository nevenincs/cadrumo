---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:1d3a675d06feab9e48c78caccf219eb2d6e3473d9f573f64d298e9a8bd40ae7d'
step_id: 'S450'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Name the Home locale-key registries by the scanner's convention, and partition the locale parity extras by evidence instead of pruning them. Six dict constants carried a _KEYS suffix the registry naming gate refuses. Then establish what the remaining extras actually are: which carry no string literal anywhere in the tree, and which are referenced by code the scanner cannot read, since only the first group could ever be safe to remove and the two are indistinguishable in the gate's own output.

## Scope

- `src/cadrumo/entrypoints/tui/home.py`

## Changes

test_no_dict_constant_naming_violations_repo_wide is green: six Home constants
carried `_KEYS` where the registry convention is `_LOCALE_KEYS`. Module-private,
twelve occurrences, one rename. 11 passed on the gate, 7 on the Home surfaces.

I EXPECTED THAT TO REDUCE THE PARITY EXTRAS AND IT DID NOT. The count stayed at
454. Those dicts were already being collected -- by the flow-confirmed SHAPE
rule, which reads a dict literal mapping tokens to dotted keys regardless of its
name -- so the naming gate and the collection are two separate things. The
rename fixed a naming contract, not a visibility problem. Recording the wrong
expectation because it is the same mistake as counting a catalogue instead of
asking the resolver.

WHAT THE EXTRAS ACTUALLY ARE, measured rather than assumed. Every extra key was
checked against every string literal in src, dev and docs:

  262 appear NOWHERE as a literal -- no code names them at all
  192 ARE named in code the scanner cannot read

That split is the whole point, because the gate reports one number and the two
halves need opposite treatment. Pruning the 192 would delete live keys.

WHY THE 192 ARE INVISIBLE, established on a sample rather than generalised: the
CLI command specs pass their key positionally to a helper --
`_blank_default_text_option("note", ("--note",), "cli.app.ledger.counterparty.note_help")`.
The helper's third parameter IS named `help_key`, which the scanner already
recognises, but only as a KEYWORD argument, and the helper is defined in a
different module from the call site. Collecting it needs the callee's signature
across modules, which the per-tree scanner does not do.

## Notes

NOT DONE, and neither is a cleanup:

The 262 unreferenced keys are candidates for removal, not a conclusion. "No
string literal" is strong evidence but not proof of death, and deleting 262 keys
across four locales is 1048 leaves. Twice this session a key that looked
unreferenced was live -- the record-qualified casillas resolve through an
encoded key, and the raw ids I wrote were the dead ones -- so a static literal
scan is exactly the evidence that has already misled me here.

The 192 have two honest routes: teach the scanner to resolve a callee's
signature across modules, or change those call sites to pass `help_key=` by
keyword, which the scanner already collects. The second is a broad edit to
production files for a tool's benefit; the first is a real capability step. Both
are decisions rather than mechanical fixes.
