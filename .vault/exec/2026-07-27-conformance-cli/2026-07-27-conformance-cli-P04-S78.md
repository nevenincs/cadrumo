---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:39e2e23df2b754aff233d1b7c29006df688e599c78c85f6fadb532d3824da96f'
step_id: 'S78'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# give the conformance tool a reachable operator page covering the stamp vocabulary, the operator-signoff hand-edit path, the registry-root flag and the baseline re-record procedure, since the prose exists only inside module docstrings

## Scope

- `REGISTRY-CONFORMANCE.md`
- `CONTRIBUTING.md`

## Description

- Read the live help for the command group and all four verbs, and run each
  command, before writing any of it down.
- Write the runbook: what the tool reports and what it does not, how to read a
  row, the four verbs and their posture, the stamp procedure, the review
  vocabulary and the hand-edit signoff path, and the baseline re-record with
  the accept-weakening decision.
- Measure where the page can live, rather than assuming.
- Link it from the contributor entry point.

## Outcome

### The verified surface is larger than the brief described

Nothing was transcribed from a docstring. The group help, all four verb helps,
and every documented invocation were run first, and several claims changed as a
result.

The registry-root flag is no longer optional-with-a-default: the verb now
requires exactly one of `--registry-root` or `--bundled-registry` and refuses
with exit code 2 when neither is given. Pointing `--registry-root` at the
shipped tree is ALSO refused, so there is one unmistakable door to shipped data
rather than two, one of them silent. Both refusals were driven and their exit
codes recorded.

The report format was measured rather than described. Every line carries its
kind as its first token, and a real run emits more kinds than a reader would
guess:

```
summary 1 | census 3 | row 90 | unused_axis 5 | note 1
```

The closing `note` is load-bearing and is now called out before any number:
`n/a` means not measured or no claim made, never zero, and `-` means a real
empty list. A reader who takes `n/a` for zero draws the opposite conclusion
from the one the row states, which is precisely the failure the whole
conformance surface exists to prevent.

The `coverage` caveat is quoted verbatim rather than paraphrased, because the
paraphrase is where "coverage of checking" quietly becomes "correctness".

The stamp was exercised end to end against a byte copy of the Modelo 130 tree
in a scratch directory, and the shipped registry was confirmed untouched
afterwards. The `--baseline` isolation claim was likewise proved rather than
asserted: a real `--record` to a scratch path, then a byte comparison showing
the committed baseline unchanged and `git status` empty for it.

### Where the page can live was measured, not assumed

The obvious home was `docs/`, beside the authoring guide, which is the existing
precedent for a contributor tool page. That was wrong, and the tree said so
rather than a reviewer:

```
FAILED dev/docs/tests/test_docs_localization.py::test_every_user_page_is_fully_translated[es]
E   es: 1 of 59 page catalogue(s) incomplete:
E       registry-conformance.md: catalogue missing at docs/locales/es/LC_MESSAGES/registry-conformance.po
[ca] and [hu] identically
3 failed, 7 passed
```

Everything under `docs/` except the generated and infrastructure trees is the
localized, taxpayer-facing surface, and a page added there must ship complete
Spanish, Catalan and Hungarian catalogues or the completeness gate reds. That
gate is right to refuse: gettext falls back to English silently, so an
untranslated page serves a reader the wrong language with no signal anywhere.

Machine-translating a technical contributor runbook into three languages nobody
on this change could review would have satisfied the gate and defeated its
purpose. The page moved to the repository root instead, beside `RELEASING.md` —
which is the exact precedent: a substantial contributor procedure, split out of
`CONTRIBUTING.md`, linked from it, outside the localized surface. Reachability
is preserved through the contributor entry point, which is the audience this
page has.

After the move the gate is clean and `docs/index.md` is byte-identical to HEAD:

```
uv run --no-sync pytest dev/docs/tests/test_docs_localization.py -q -n0
10 passed in 3.59s

git diff --stat -- docs/index.md   ->   empty
```

### Verification

Every documented command, run:

```
python -m dev.registry.conformance --help                      -> exit 0, 4 commands
python -m dev.registry.conformance report                      -> exit 0, 100 lines
python -m dev.registry.conformance coverage                    -> exit 0, 26 axes
python -m dev.registry.conformance audit                       -> exit 0
python -m dev.registry.conformance audit --check               -> exit 0
just audit-registry-conformance                                -> exit 0, 90 row lines
```

The stamp verb, including both refusals:

```
stamp 130 2019-y-siguientes --engineered-by ... --registry-root <scratch>/aeat
  -> exit 0
  stamped modelo=130 revision=2019-y-siguientes manifest=revision.toml
    engineered_by="agent:docs-probe" review_status="agent_reviewed"
    reviewed_by="agent:docs-probe" reviewed_at=2026-07-28 removed=-

stamp ... (no root flag)              -> exit 2, names both flags and why there is no default
stamp ... --review-status operator_reviewed
  -> exit 2, "'operator_reviewed' is not one of 'pending_review', 'agent_reviewed'"
stamp ... --registry-root src/cadrumo/_data/registry/aeat
  -> exit 2, names --bundled-registry as the flag that states the act

git status --short -- src/cadrumo/_data/registry/aeat/modelos/130  ->  empty
```

The baseline verbs:

```
audit --record --baseline <scratch>/probe-baseline.json   (no --note)
  -> exit 1, "--record requires --note ... an unexplained re-record is
     indistinguishable from silencing a real regression"

audit --record --note "..." --baseline <scratch>/probe-baseline.json
  -> exit 0, recorded baseline recorded_at=2026-07-28 rows=90
  probe baseline written; committed baseline byte-identical; git status empty
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. Grounding was by
whole-file reads and `rg`.

The runbook's prose is largely the module docstrings' argument restated for a
reader who is not reading source. The stamp module's explanation of why an
agent may not write `operator_reviewed` is the strongest of them and is carried
over in substance rather than rewritten: an `--i-am-the-operator` switch is as
assertable by an agent as the value itself, so it would add the appearance of
assurance and none of the substance. What the page adds is the other half a
docstring cannot give — where the operator actually types the signoff, which is
`revision.toml` by hand.

The `--accept-weakening` section is deliberately written as two lists, cases
where it applies and cases where it does not, because the flag's whole hazard
is that the situation in which a contributor most wants it is the situation in
which it is most wrong. A lowered floor is silent forever; a raised ceiling is
self-correcting on the next honest capture. The asymmetry is stated so the
decision does not rest on judgement alone.

The working tree broke under peer edits twice during this Step, both times in
the registry package a sibling Step owns — first a verification-predicate
extraction mid-flight, then the export-format enum lift. Neither is a HEAD
property and neither was touched. Each was attributed by comparing the working
tree against `git show HEAD:<file>` and then waited out; the commands were
re-run once the tree settled, so no documented output was captured from a
half-landed tree.

A residual `.git/index.lock` blocked the commit for seven minutes. It was
diagnosed by rename probe rather than by elapsed time, and moved aside rather
than deleted. No destructive git operation was run.
