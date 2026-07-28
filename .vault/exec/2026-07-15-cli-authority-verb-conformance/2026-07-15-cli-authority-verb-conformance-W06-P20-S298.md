---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S298'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S298 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Remove the two feature-owned size-budget regressions this campaign introduced, the payload module pushed to 1251 by the wizard-bridge guard comment and the config help builder pushed to 195 by the custody and audit rows, since the campaign close claims no feature-owned regression exists and ## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/application/operator_surface/_help.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove the two feature-owned size-budget regressions this campaign introduced, the payload module pushed to 1251 by the wizard-bridge guard comment and the config help builder pushed to 195 by the custody and audit rows, since the campaign close claims no feature-owned regression exists

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Trace each size-budget breach to the commit that crossed the ceiling rather
  than accepting the recorded attribution.
- Remove the two this campaign caused, without weakening what they were added
  for.

## Outcome

SATISFIED. Two feature-owned regressions found and removed. The campaign's
"no feature-owned regression" close position was FALSE when I started this
check and is true now.

BOTH WERE THIS CAMPAIGN'S, and both landed today. The payload module went from
1248 to 1251 lines at the wizard-bridge guard commit, one over its 1250
ceiling. The config help builder went from inside its band to 195 lines against
a 180 ceiling when the custody and audit rows were added.

The second one is mine twice over: the help expansion happened because I
pressed a dispatched agent to treat that row as real work against its own
correct reading, and the expansion then broke a budget. The agent's original
analysis was right and my pressure produced both the feature and the breach.

Neither fix weakens what the change was for. The payload comment was compressed
from five lines to four while keeping every load-bearing claim: that the two
profile schemas register through the sibling module, that there is no re-export
in this one, and why it moved. That comment is the only thing standing between
a tidy-up and silently dropping both profile verbs from the MCP surface, so
deleting it was not an option. The help builder had its custody family
extracted into a named function - the remedy the gate's own failure message
recommends - and the extraction is cohesive rather than arbitrary: every custody
verb operates on the secret store rather than on profile content. Coverage is
unchanged, with the recovery, certificate, audit and passphrase families all
still cited.

Gates at HEAD `84856eab5efed44d40d9d483ddfa5875ce83172f`:

- Payload module: 1250 lines, at its ceiling rather than over it.
- `uv run --no-sync pytest src/cadrumo/tests/test_codebase_size_budgets.py
  -n0 -m ""` collected 16, exit line `1 failed, 15 passed in 25.00s`. The
  callable-band case now PASSES; the single remaining failure is the module
  band, carrying only the two peer-owned breaches.
- `uv run --no-sync pytest test_root_help_shape.py
  test_suggestion_command_conformance.py -n0 -m ""` collected 24, 23 passed.
- `ruff check` and `ruff format` clean on both files.

## Notes

The two surviving module breaches are peer-owned and were attributed by
trajectory, not by commit subject: the Clave Movil adapter crossed at 1268 in
an auth-campaign commit today, having been at 1060, 1141 and 1214 before, and
the config facade crossed at 1252 in a peer refactor that added 47 lines while
splitting complexity hotspots.

The one failing help case is also peer-owned and is worth flagging beyond this
row: it expects product version 0.2.1 and the installed console now reports
0.1.0, because a release commit landed mid-campaign and set the package version
DOWNWARD. That is a release-tooling question, not a help-surface one, and my
change touched neither file.

Recorded because of how nearly this was missed. A prior record attributed the
size gate wholly to peers, and it was right about the modules it examined. The
callable band and the payload module were not in that record at all, and the
close position would have shipped as true on a check that never looked at them.
