---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S182'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run evidence service and modelo audit suites and prove the replay method, command, schema, event, tests, and documentation cannot execute or be discovered

## Scope

- `src/cadrumo/application/evidence/tests/test_evidence.py`
- `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`

## Description

- Run both named suites under an explicit execution-marker selection covering both lanes.
- Confirm a non-zero collected count before reading the result line.
- Search the source, schema registry, and shipped documentation independently of the suites for surviving references to the retired replay surface, since the Step's claim covers documentation the suites do not read.
- Distinguish the retired evidence-bundle replay from the unrelated replay facilities the retiring Step deliberately preserved.

## Outcome

Verdict: SATISFIED for code, command, schema, and tests; FAILED for documentation.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/application/evidence/tests/test_evidence.py src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.

Collected 25, passed 25, failed 0, skipped 0. Exit line: `25 passed in 12.81s`, exit code 0. HEAD at run time was `1844ef2ea03314f47bfb0cdcfaac17d0fe08be26`. The serial and OS-keychain selections both collected nothing.

The executable half of the claim holds. The audit verb suite proves the retired leaf is gone from the command tree and that its result schema is absent from the schema registry. The evidence application package carries no replay method: the only surviving occurrence of the word there is a docstring sentence describing manifest verification, which is a different operation. The preserved facilities the retiring Step called out are intact and correctly distinct: the registry parity replay command, and the CLI determinism replay enrolment, neither of which is the evidence-bundle replay.

The documentation half does not hold. A shipped contract sequence for the annual IVA summary records-audit walkthrough still instructs the reader to inspect, check, export and replay an evidence bundle by id. The verb it then shows is the export verb, and its own blocked-annotation says only the show, check and export verbs exist, so the prose contradicts the annotation immediately beneath it and advertises a verb the CLI refuses. The line is present at HEAD, not introduced by uncommitted work.

Attribution: owner surface. The retiring Step named documentation in its own claim, and this is the documentation surface it missed.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. The documentation residue was found by direct search and confirmed against the committed file, not by semantic search.

The residue is one word in one prose line and is not a functional regression, but the Step's claim is explicitly that the retired surface cannot be discovered, and an operator reading that walkthrough would discover it.

## Re-measurement at HEAD `1437055950`

Verdict: SATISFIED.

The documentation residue closed before this re-measurement. Commit `4cb601d10d` dropped "replay" from the step description in the model-390 records-audit sequence, rewriting it to "Inspect, check, and export an evidence bundle by id." The word "replay" no longer appears anywhere in the sequence file, and the prose now matches the blocked annotation immediately beneath it.

Test command: `uv run --no-sync pytest -q -p no:cacheprovider -n auto --dist=loadfile --tb=no -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/application/evidence/tests/test_evidence.py src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.

Collected 14, passed 14, failed 0, skipped 0. Exit line: `14 passed in 14.37s`, exit code 0. HEAD at run time was `1437055950f5b8f4082d323578294fc32ad1d9fe`.

Verified by direct inspection: `grep "replay" docs/_sequences/contracts/how-to/modelo-390/modelo-390-records-audit.seq` returns no output at HEAD.
