---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:29f13f71237f705052d8880cf534f23caaed91150bc8074435d772290ce8d64f'
step_id: 'S461'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read the CLI help keys from the live command-spec registry rather than from source text, since a spec table builds an options help key from the option name so no literal exists and fifty-eight shipped keys the CLI resolves on every run were indistinguishable from keys nothing uses; establish on the same evidence that the live registry declares none of the 125 cli catalogue extras

## Scope

- `dev/locales/_command_spec_scanner.py`
- `dev/locales/manager.py`
- `dev/locales/tests/test_command_spec_key_source.py`

## Changes

A FIFTH DISCOVERY PATH, and the first that does not read source text.

Every other path reads what somebody wrote down, which works only while a key
is written at the site that uses it. A spec table builds one:

    _key(f"cli.app.modelo.work.{help_name or name}_help")

Fifty-eight live command and option help keys were in that position -- shipped
in all four catalogues, resolved by the CLI on every run, and to a text scan
indistinguishable from a key nothing uses. `scan_command_spec_keys` imports the
live `COMMAND_SPECS` and takes the fields the codebase ANNOTATES
`TranslationKey`. All 1,093 are now visible; none was before.

EXTRAS ARE UNCHANGED AT 167, and that is the honest result: those 58 keys were
never extras, because they are in the catalogue. What this buys is that they
can no longer become extras, and that the CLI surface is now measured against
the registry that serves it rather than against a text search for it.

I MADE BOTH AVAILABLE MISTAKES FIRST, and both are now pinned as teeth.

* Reading `help_key` as a `str` returned NOTHING: the field holds a
  `TranslationKey` value object, and the probe cheerfully reported zero keys
  from a registry that declares a thousand.
* Walking every dotted string reachable from the registry instead swept up
  command paths (`app.diagnostics.errors`) and module names as though they
  were keys -- it claimed 504 catalogue keys were missing, every one of them a
  phantom. Reading the ANNOTATED fields is what makes the result a key set,
  which is the same lesson as the union-of-signatures over-collection earlier
  in this campaign: what a declaration IS decides what may be derived from it.

Teeth: three defects, each restored by copy -- read the field as a bare string,
collect any dotted attribute, and unwire the source. Each fails the new gates,
and the roots assertion (`{cli, wizard}` exactly) is what catches the second.

## Notes

TARGET 2 REMAINS OPEN at 167 extras. Same two failures as before this step --
the parity gate and the shadow gate. No new breakage.

EVIDENCE FOR A DECISION THAT IS THE OPERATOR'S, NOT MINE. The live registry
declares ZERO of the 125 `cli.*` catalogue extras. Spot-checking agrees: the
live command tree has no `config init` and no `config get`, yet the catalogue
ships `cli.config.init.*` and `cli.config.get.*` -- copy for retired commands.

This is a materially stronger claim than the one available before. "No literal
found" was weak evidence and has been wrong five times in this campaign, each
time because the scanner could not see a live call. "The live registry that
serves this surface does not declare it" is decidable and comes from the
authority itself.

It is still not my call to delete 125 shipped translations, and the same
evidence does not cover the 26 `docs.*`, 11 `tui.*`, or 5 `application.*`
extras, which have no comparable registry. Recommendation for the operator:
authorise pruning the `cli.*` extras that the live registry does not declare,
gated by `test_every_key_the_live_registry_declares_is_translated` so the
reverse direction stays proven.

Residue: 9 full-literal, 60 tail-only, 98 no-trace.
