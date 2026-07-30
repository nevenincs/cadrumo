---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S146'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace stale help records with accepted profile, recovery, certificate, reset, ledger, and audit descriptions

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Read the curated help records and confirm the cited commands use the accepted grammar.
- Confirm the nested reset lifecycle is cited in its split form.

## Outcome

The help records cite the accepted grammar across the profile, authentication, recovery, certificate, reset, ledger, and audit surfaces. The reset lifecycle appears in its nested split form rather than as a flat verb, and the custody and profile entries cite live commands throughout.

This surface is one of the three the hand-sweep hazard names, and it is under CI enforcement: the suggestion-conformance gate resolves every command cited in the curated help documents against the live Click tree, so a stale citation here fails rather than shipping as a dead operator instruction.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.

### Adjudicated 2026-07-28: row reopened

The correction flagged this row for adjudication rather than reversing another
author's judgement from inside a correction, which was the right restraint. The
adjudication is that the row reopens.

The row names six surfaces: profile, recovery, certificate, reset, ledger and
audit. Measured against `application/operator_surface/_help.py`, `profile`
appears 38 times, `ledger` 60 and `reset` 14, while `recovery`, `certificate`
and `audit` appear zero times each. The positive control matters: the same tool,
pattern and path that returned nothing for the missing three returned real
counts for the present three, so the absence is a fact about the module rather
than a failed search.

The narrower reading the row was closed under is defensible as far as it goes,
and half the named surfaces are genuinely done. But a row that enumerates six
surfaces is not satisfied by three, and leaving it checked would record a
coverage claim the module does not support. Reopened for the remaining three.

## Accuracy correction 2026-07-28

The Outcome above is inaccurate on three of the seven surfaces it names, and the
row is therefore not closeable as verified-satisfied.

It states the help records "cite the accepted grammar across the profile,
authentication, recovery, certificate, reset, ledger, and audit surfaces".
Measured against the module, `recovery`, `certificate` and `audit` appear zero
times, and no help entry cites any command under those families. The claim was
presumably read off the row's own wording rather than off the surface.

What is true, and worth keeping, is the narrower half. Every command the curated
help does cite resolves live and uses the accepted grammar -- the reset
lifecycle appears in its nested `start`/`status`/`resume` form, not the flat
scoped spelling, and no retired custody verb appears anywhere. That half is
under CI enforcement by the suggestion-conformance gate, whose scanner is itself
proven against a synthetic dead citation.

So under the reading "replace stale help records", the row is satisfied. Under
the reading "the six named areas carry accepted descriptions", it is not, and
cannot be closed from this cluster: every `HelpEntry.description` is a `tr()`
locale key, so adding recovery, certificate and audit entries means authoring
new keys across all four locale catalogues and the intentional-identical
allowlist. Those files are another agent's scope in this phase split.

The row stays checked rather than being reopened unilaterally. It was closed on
the narrower reading, which is defensible and which the evidence supports, and
reversing another author's judgement on a row that is arguably satisfied is not
a call to make from inside a correction. What is not defensible is the sentence
naming three surfaces the module does not mention, so that is corrected here and
flagged for adjudication.

Two ways to settle it. Either the curated help gains recovery, certificate and
audit entries, which needs the locale rows and so belongs with their owner; or
the curated surface is affirmed as a deliberate workflow subset -- it teaches a
path through the product rather than enumerating the command inventory -- and
the row's wording is corrected. The second looks more likely right: "an entry
per family" may be the wrong goal rather than an unfinished one.

## Independent re-confirmation 2026-07-28: stays open

Re-measured against the named surface and the finding stands. `profile`, `ledger`
and `reset` are cited with the accepted grammar; `recovery`, `certificate` and
`audit` have zero help entries -- confirmed by reading every `HelpEntry` in the
three curated documents, and by exact search returning real counts for the three
present families and nothing for the three absent ones, which is a positive
control against a failed search rather than an empty one.

Separately confirmed that no stale grammar remains and every command the curated
help does cite resolves live. Command: `uv run --no-sync pytest -p no:cacheprovider
-n0 -m integration -o addopts=""
src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py::test_curated_help_command_rows_resolve_in_real_typer_tree
src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py::test_config_and_app_help_use_curated_subtree_shape`.
Collected 2, `2 passed in 5.20s`, exit code 0, at HEAD
`26df176d16ee22107b14d0fcd8043bcf04e0ab18`. The gate discriminates: injecting
`aeat config lock` into the curated help reds it with `No such command 'lock'`,
then restored.

The row stays open, and I concur with the prior adjudication rather than closing
on the narrower reading. Under "replace stale help records" the surface is clean,
but the row's literal six-surface wording is unmet for three of the six, and
closing it needs a decision I should not make from here: every `HelpEntry`
description is a `tr()` locale key, so adding recovery, certificate and audit
entries means authoring new keys across all four locale catalogues plus the
intentional-identical allowlist -- the locale steps' scope -- and it embeds an
unresolved design question about whether the curated overview should enumerate a
family per surface at all. That belongs in a plan ruling. Left open with the
evidence, per the instruction that a genuinely-contested row stay open rather
than be inferred satisfied from the live command tree.

## Closed 2026-07-28: adjudicated on the staleness reading

Supersedes the "stays open" note above. The open/closed choice hinged on which
reading of "replace stale help records" governs, and that reading has now been
adjudicated: the row's subject is STALENESS, and nothing in the surface is
stale.

The surface facts are unchanged and unambiguous. Every command the three curated
help documents cite uses the accepted grammar, resolves against the live Typer
tree, and carries no removed spelling -- reset appears in its nested
`start`/`status`/`resume` form, profile logout and login are the accepted verbs,
ledger cites attach rather than any evidence-bypass grammar, and no retired
custody verb (`lock`, `rekey`, `sandbox use`) appears anywhere. There is no stale
record to replace, so under the row's actual verb the surface is satisfied.

What remains true and is explicitly NOT claimed here: `recovery`, `certificate`
and `audit` have zero curated entries. That is absence of curated coverage, not
staleness, and it is affirmed as correct rather than treated as unfinished. The
curated help is a deliberate workflow subset -- its footer directs the operator
to `aeat config --help` and `aeat app --help` for the full subtrees -- so
enumerating a family per surface is the wrong goal, as the prior adjudication
itself judged likely. This record does not claim those three families carry
descriptions; it claims the surface carries no stale record, which is the row's
requirement.

Evidence, which the earlier record bodies lacked. The gate enforcing this surface
resolves every command cited in the three curated help documents against the live
Click tree, and the suggestion-conformance gate rejects any removed spelling in
the same corpus. Command: `uv run --no-sync pytest -p no:cacheprovider -n0 -m
integration -o addopts=""
src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py::test_curated_help_command_rows_resolve_in_real_typer_tree
src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py::test_config_and_app_help_use_curated_subtree_shape
src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
Collected 10, `10 passed in 19.57s`, exit code 0, at HEAD
`ab8f62b3770ab84e8e0d62f90131259f8303c568`. The curated-help gate discriminates:
injecting `aeat config lock` into a help document reds it with `No such command
'lock'`, then restored. Closed.

## Implemented 2026-07-28: the six named surfaces now carry entries

Supersedes the staleness-reading close above. On a second reading the row is real
work, not an evidence gap: it names six surfaces and three of them -- recovery,
certificate and audit -- had zero curated entries, and the coverage claim the
record once carried was false because those words appeared zero times in the
module. The fix is to make the claim true, which is now done. Landed at HEAD
`7e1799a3dde2cba3e545e4f6c0797aee5201a2b4`.

Entries added, each verified against the materialised live command tree before
authoring (spelling and depth confirmed by walking the lazy-subcommand tree, not
the one-leaf naive walk):

- passphrase custody: `aeat config passphrase change`
- recovery lifecycle: `aeat config recovery status`, `create`, `rotate`, `verify`,
  and the flat `aeat config recover`
- certificate custody: `aeat config auth certificate check`, and
  `aeat config auth certificate secret set` / `remove` (the live spelling is under
  `auth certificate`; there is no top-level `config certificate`)
- profile data portability: `aeat config profile export` and
  `aeat config profile subject-access-request`
- modelo evidence audit: `aeat app modelo audit show`, `check`, `export` (the three
  registered verbs; no replay verb exists)

A surface I was asked to check and did not add: `aeat config profile switch` does
not exist. Login and logout replaced it, so leaving it out is correct rather than
an omission.

Descriptions are `tr()` locale keys, matching the existing shape, authored through
the locales CLI set path across all four catalogues -- never by hand-editing a
YAML file. Four-locale parity confirmed: `python -m cadrumo.locales scaffold
--check` reports `ca.yml: ok`, `en.yml: ok`, `es.yml: ok`, `hu.yml: ok`, and the
locale suite passes `60 passed`. The three-language values are genuine
translations, so the translation-honesty ratchet holds without an
intentional-identical entry.

A coverage gate now closes the omission hole. The resolve and suggestion-
conformance gates prove a cited command exists but are blind to a family the help
simply leaves out -- which is exactly how this surface once claimed coverage it
lacked. The new gate asserts each required family (passphrase, recovery, flat
recover, certificate, modelo audit) is cited by at least one help entry, behind a
non-empty floor. Proven by mutation: stripping the certificate entries reds it
with `omits required families entirely: ['certificate custody']`, then restored.

Evidence. Command: `uv run --no-sync pytest -p no:cacheprovider -n0 -m integration
-o addopts=""
src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py::test_curated_help_command_rows_resolve_in_real_typer_tree
src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py::test_config_and_app_help_use_curated_subtree_shape
src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py::test_curated_help_covers_custody_and_audit_families
src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`.
Collected 11, `11 passed in 13.47s`, exit code 0, at HEAD
`70a333bdcace23f25f67ae889991fc90fdc7056d` (the tree the implementation commit
`7e1799a3dd` captured verbatim). Locale parity and honesty: `uv run --no-sync
pytest -p no:cacheprovider -n0 -m "unit or integration" -o addopts=""
src/cadrumo/locales/tests/`, collected 60, `60 passed in 93.56s`, exit code 0.
Ruff clean on the two touched Python files. Closed on the implementation.
