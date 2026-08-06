---
tags:
  - '#audit'
  - '#result-summary-locale-behaviour'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:4e14329feb44fae578b92c1a5dc10b858cd54563a37b5ccafefb7cb7db12fa28'
related: []
---



# `result-summary-locale-behaviour` audit: `Result-summary label locale behaviour: measured, not adjudicated`

## Scope

**This document records what the code DOES. It is not a verdict on what the code is
MEANT to do, it is not the localization-cascade owner's confirmation, and it does not
discharge the open ci-lane-deconflation row that asks whether this behaviour matches the
intended contract. That row stays open. A reader who needs the intent question answered
must look for a decision record authored by the cascade owner; nothing measured here
substitutes for one.**

The reason for the separation: a behavioural fact cannot answer an intent question. The
row in question was previously mis-closed when three commits merely consistent with a
confirmation were read as the confirmation. This document is deliberately filed on its
own surface, away from that row, so proximity does not recreate that error.

What was measured: whether the modelo result-summary row label follows the active output
language, and whether the properties asserted by the commit that repaired the covering
test are true of the tree. The covering test is
`src/cadrumo/entrypoints/cli/tests/test_modelo_result_summary_labels.py`; the resolution
site is `calculation_result_summary` in
`src/cadrumo/application/modelo/_result_summary.py`.

## Findings

### label-follows-active-output-language | low | The label resolves once, in the application layer, from the active output language

The row label is built as `casilla.get_label(output_language())` inside the per-row
constructor of `calculation_result_summary`. There is one resolution, at the application
layer; the row carries a resolved string and no locale map. The CLI renderers in
`src/cadrumo/entrypoints/cli/_modelo_rendering.py` pass `row.label` through unchanged to
both the text block and the JSON payload, applying no second localization. `output_language()`
resolves an explicit settings override first, then the active profile's language key, then
the settings default.

### four-locales-render-four-distinct-labels | low | The positive control holds; no assertion branch is trivially true

Measured against modelo 130, filing year 2026, period 1T, revision `2019-y-siguientes`,
casilla `03`, the label is distinct in each of the four supported locales: `Net yield`
(en), `Rendimiento neto` (es), `Rendiment net` (ca), `Nettó jövedelem` (hu). Four inputs
produce four distinct outputs. This is the control that matters for this measurement: had
two locales rendered the same string, a correct probe and a broken one would produce
identical output and the covering test's assertions would be trivially satisfied on those
branches. They are not.

### no-output-language-cache-artefact | low | Per-process and sequential in-process sweeps agree

The output-language resolution is cached, and its cache key uses the identity of the
active settings-override object. Because interpreter object identities are reusable after
collection, a sequential in-process sweep across locales could in principle read a stale
language while a single-locale process could not. Both were run: four single-locale
processes and one process sweeping all four locales in sequence produced identical
`(active language, label)` pairs for every locale. No caching artefact is present at the
measured commit, and the resolved active language equalled the requested locale in every
case.

### commit-claims-corroborated | low | No contradiction between the tree and the repairing commit's stated rationale

The commit that repaired the covering test asserts four things: that the label resolves
once via `get_label(output_language())`, that the renderer passes `row.label` straight
through, that the label differs in all four supported locales, and that the test no longer
depends on the ambient default language. All four are true of the measured tree. The
contradiction check this measurement was commissioned to perform returns nothing; there is
no finding of disagreement between the commit's rationale and the tree's behaviour.

## Recommendations

No code change is recommended. The measurement found no defect, no contradiction, and no
trivially-satisfied assertion.

The open intent question is untouched by all of the above and still needs an owner's
decision: whether resolving the label from the active output language is the intended
contract for this row, given that the Spanish label is the registry-grounded channel
regulatory and export consumers read while the summary is an operator display surface.
That decision belongs in a record authored by the localization-cascade owner. This
document supplies only the behavioural facts such a decision would rest on.

## Method

Measured at commit `92f4c3730391cd04e86e691e3714f8632da8f24c`, extracted with
`git archive` into a clean directory and executed with the extraction ahead of the
editable install, so the reading reflects committed state rather than the working tree.
Every run carried a guard asserting that the imported package resolved inside the
extraction, writing its verdict to a file rather than stdout; each run's guard recorded
that it did. The guard was proven capable of firing by a positive control that shadowed
the extraction with the working tree and was refused. The covering test module was
additionally executed at the extraction under the same guard and passed in full, once the
integration marker was supplied — a first attempt selected nothing, which the repository's
own harness reported rather than returning a misleading green.
