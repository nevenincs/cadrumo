---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:3eaf6871603dc393aea6f8a490dca77631555be77b7a6953dd65cd685da67e33'
step_id: 'S66'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule on the profile bundle transfer surface and delete the two tests that prove nothing, since the interactive collection flow serves two verbs that do not resolve, a second narrower interactive collection path for the same operation is live in the manager actions with the transport hardcoded, and two tests invoke the unregistered verb asserting only a non-zero exit so they pass on the unknown-command error and would pass forever whatever happened to the verb

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py and src/cadrumo/entrypoints/cli/_config/_manager_actions.py and src/cadrumo/entrypoints/cli/_config/tests/test_config.py`

## Description

- Read the prior per-family ruling that deferred this surface's disposition
  to this row, and confirmed each of its three load-bearing claims against
  source rather than accepting them on report: the application layer is
  alive, the old CLI wiring is recoverable from history, and a narrower
  working equivalent runs today in the manager.
- Established that the interactive collection module had ZERO importers
  anywhere in the tree. The only occurrence of its name outside itself was
  a filename string in the config package's own module-scope conformance
  allowlist.
- Confirmed both verbs it serves are absent from the live surface:
  `config profile --help` lists capabilities, censo, create, descendiente,
  edit, history, list, preflight, show, status and validate, and neither
  export nor import.
- Probed the unregistered verb directly and captured what it actually
  returns: click's `No such command 'import'.` at exit 2.
- Ran the two suspect tests and observed both PASS today, which is the
  reading the row proposed: each asserts only a non-zero exit, and click's
  unknown-command refusal is non-zero, so they pass on a code path that has
  nothing to do with the boundary their own docstrings claim to cover.
- Traced the application layer's real consumers: the export entry point has
  exactly ONE production caller, the manager's export action; the
  deserialize entry point has NONE outside its own package facade. There is
  no inbound bundle path in production at all.
- Deleted the interactive collection module, both worthless tests, and the
  module docstring clause that advertised the deleted third contract.
- Corrected the four stale module names the config package's conformance
  allowlist still carried from the capsule cutover, which had been reddening
  four of that module's tests before this row touched it.
- Rewrote the two manager docstring passages that instructed a reader to
  send the operator to verbs that do not resolve.

## Outcome

**Ruling: the manager's narrower path SURVIVES; the interactive collection
module is residue and has been deleted. The declared-unimplemented entries
for both verbs STAY, unchanged.**

### Which of the two paths survives, and why

Both paths collect the same answers for the same operation — a destination,
a transport, a passphrase — and both terminate in the same application-layer
export call. That is the duplication this campaign exists to remove, and one
of them had to go.

The decisive asymmetry is not breadth, it is reachability. The manager's
path is reached by an operator today. The collection module was reachable
only through two verbs that do not exist, and could not acquire a caller
without those verbs being restored first. It was not a shared component the
restored verbs would have to reuse; it was wizard scaffolding for a Typer
command's missing-argument case, and the command it scaffolded is gone. A
restored verb needs its command wiring before it needs a flow, and the
recovery source for that wiring — the 897-line CLI module in history — is
strictly more complete, because it carried this module's own callers with
it.

So the choice was between a broader-but-unreachable surface and a
narrower-but-live one, and narrower-and-live wins. Keeping 427 lines of
unreachable code against a future that may not arrive is a compatibility
bridge in everything but name, and the zero-legacy mandate says delete
outright rather than preserve.

The manager path is genuinely narrower and this ruling does not pretend
otherwise: it exports the active profile only, offers no profile selection,
offers no transport choice, and has no import counterpart. Those are real
capability gaps. They are gaps in the CAPABILITY, which the declared
register already records, not defects in the surviving path.

### The two tests that prove nothing

Both invoked the unregistered verb and asserted only `exit_code != 0`.
Confirmed by running them (both green) and by probing the verb directly
(click refuses with an unknown-command error at exit 2). Their docstrings
claimed to cover a parse-failure boundary that wraps a non-typed exception
into a typed refusal; that boundary never executed, because argument parsing
refused before any handler ran. They would have stayed green if the boundary
had been deleted, inverted, or had never existed.

Both are deleted. Neither was rewritten into coverage of the unregistered
verb, per the row's explicit instruction: there is nothing to cover until a
verb exists. The module docstring's third numbered contract, which
advertised them, is replaced by a statement of why that boundary is
deliberately uncovered — so the absence is legible rather than merely
missing.

### The declared-unimplemented register: entries STAY

Both verbs' entries in the register of capabilities removed without a
decision are left exactly as they are. This is a deliberate position, not an
omission.

The entries' own stated removal condition is restoration of the verb. This
row does not restore a verb, so the condition is not met. More importantly,
each entry records that whether the capability returns is an OPEN question
and that deleting the declaration would answer it by making it invisible.
Deleting a dead flow module does not answer that question — the capability
question and the residue question are separate, and this row settles only
the second. Removing the entries because the last dead code around them was
swept would be exactly the retirement-by-tidying the register exists to
prevent.

One inaccuracy in the export entry is worth recording rather than editing,
since that file is outside this row's ownership. Its reason reads as though
the capability itself were absent. It is not: profile bundle export runs in
production today through the manager's action. What is absent is the CLI
VERB. The distinction matters to whoever answers the capability question,
because the honest question is not "should this capability exist" but
"should it be reachable from the command line as well as from the manager
screen".

### Handed to the row that owns single-verb restoration

Restoration is not built here, per the row's own instruction. What that row
inherits, established rather than assumed:

- The application layer is complete and needs nothing built. Export is
  exercised in production today. Import's deserializer is intact but has
  never had a production caller since the cutover, so the inbound half is
  wiring against a proven-by-inspection rather than proven-by-use primitive.
- The interactive collection module is gone as of this row, so it is
  recoverable at this commit's parent, and the fuller CLI wiring remains
  recoverable at the cutover commit's parent. Restoring from the older,
  fuller source is the better route; this module was a subset of it.
- Restoring export must decide the transport question deliberately. The
  cleartext transport writes the taxpayer's financial data as plain JSON. It
  used to be held behind an explicit command-line flag, and that flag no
  longer exists on any surface, so the manager's hardcoded encrypted
  transport is currently the SOLE guard against writing cleartext. A
  restored verb that re-exposes transport selection re-opens that door and
  owes it an explicit safety argument. This is now stated at that call site.
- Restoring either verb removes its register entry, per the entry's own
  terms.
- Twelve locale keys are now orphaned by this deletion and are reported to
  the campaign lead rather than removed here, since the catalogues are
  outside this row's ownership. If restoration lands, they are wanted; if it
  is refused, they go.

## Notes

An unrelated defect was found and is NOT fixed here, because fixing it needs
a locale-catalogue change this row does not own. The config package's
conformance gate forbids a translation fallback, and the manager frontend
carries one on a next-step advisory. The key it falls back FROM is absent
from all four catalogues, verified by loading each catalogue and inspecting
the namespace, so the fallback is not a safety net — it is the only reason
the advisory renders at all, and it renders untranslated English in every
locale. Its interpolation syntax is also the wrong one for these catalogues,
which is a further sign it has never been reconciled against them. Removing
the fallback before the key exists would make the surface render a raw key,
which is worse than today, so the code is left alone and the key with real
values for all four locales is handed to the campaign lead. That gate test
therefore remains red for a cause this row did not introduce and cannot
close alone.

Four of that same gate's tests were red on arrival for a different and
closable cause: the module-scope allowlist still named four modules the
capsule cutover deleted. Absorbed rather than reported, since the allowlist
had to be edited for this row's own deletion anyway. Three of the four
tests are now green; the fourth is the translation-fallback failure above.

Two locked-store login tests in the edited test module fail against current
behaviour: they stage a store they expect to be locked and expect a
passphrase refusal, and login succeeds instead. Attributed to the custody
authority change rather than to this row — nothing changed here touches
login, and the surfaces they name belong to another owner. Reported, not
touched.

A concurrent peer landing broke the whole test tree mid-run at one point:
an error subclass had been added without its registry entry, which the
registry's own failure message anticipates as a mid-flight symptom. Waited
for the working tree to settle and re-ran rather than triaging it as a
regression.

No verb was restored, no register entry was changed, no locale catalogue was
touched, no commit was made, and no plan checkbox was set. Every capture
lives under the session scratchpad, not the repository.
