---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:2744b416c72ef47fd478205b9ac4ffc8935fd52913fea9811066abd249c606ed'
step_id: 'S264'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Stop RelatedPartyOperationObservation defaulting its country to Spain, since modelo 232 declares operations with paraisos fiscales alongside operaciones vinculadas so a silent ES default marks a tax-haven counterparty as domestic on the exact axis the declaration exists to surface - and this registry binding is a SECOND representation distinct from the M232 vinculada row model already made required, so a reader who finds the fixed one concludes the modelo is covered while this one still defaults

## Scope

- `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py`

## Description

- Make `country_code` required on `RelatedPartyOperationObservation` in
  `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py`, replacing the
  `default="ES"` with the reasoning the operator-supplied M232 row already carries.
- Stop the related-party row-set assembler in
  `src/cadrumo/application/calculations/_row_set_assembly.py` injecting the same
  hardcoded `"ES"`, routing the country through the module's existing
  `_optional_text_kwarg` helper instead.
- Add the model refusal gate and a tax-haven retention case to
  `src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py`,
  and the assembler refusal gate plus its positive control to
  `src/cadrumo/application/calculations/tests/test_row_set_assembly.py`.
- Supply the country on an existing amount-validation case that omitted it, so it
  cannot pass for the wrong reason once the field is required.

## Outcome

The country is the axis modelo 232 exists to surface: the declaration covers
operations with países o territorios calificados como paraísos fiscales alongside
operaciones vinculadas, so a default marked a tax-haven counterparty as domestic on
exactly that axis.

The fix had to be two-sited. The scoped model change alone would have been inert: the
assembler is the only production producer of these observations, and it supplied
`"ES"` unconditionally, so the field was never absent at the constructor and the new
requirement would never have reached a row. The module's own
`_optional_text_kwarg` docstring already forbade that fallback in prose — it names
`"ES"` as the example a caller must not supply — while four call sites in the same
file did it anyway.

The second-representation premise in the Step is confirmed, and it is stronger than
"two representations exist". The two constructions are on **disjoint paths that never
meet**: `Modelo232VinculadaRow` — the already-required one — does not appear in
`src/cadrumo/application/calculations/_row_set_assembly.py` at all, reaching the
fichero instead through the CLI row materialiser and the revision replay inputs, while
the observation this Step owns is constructed only in the assembler from the Sheets
Detalle round-trip. They are not alternatives that might both be exercised for one
operation. So the hardened row model could never have compensated for the defaulting
one no matter what the data did: an absent country on the pull path never reaches the
model that would refuse it.

The equivalent consequence the Step asked for is narrower than the M349 one and
should not be overstated: no tax-haven classification rule reads this field anywhere
in the tree — a search for paraíso, tax-haven and equivalent spellings returns
nothing in the package. What the country does reach is the DR23200 país field of the
declared row itself, through the `modelo-232-related-party-row-country` binding. So
the loss is direct rather than derived: the filed record stated Spain for a
counterparty the row never placed there, on a declaration whose stated purpose
includes identifying those counterparties. The absence of any consuming rule is
itself reportable, and is recorded in Notes.

## Verification

Both gate files, after the change:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py src/cadrumo/application/calculations/tests/test_row_set_assembly.py -m unit -q -p no:randomly
    42 passed in 64.05s (0:01:04)

The gates were then proven to bite by a runtime mutation driven from a script outside
the repository, so no tracked file was edited and the window closed with the process.
The mutation reinstated the model default on the imported class, rebuilt the model,
and re-routed the assembler's country kwarg through the old hardcoded fallback. It
proved the window OPEN before running anything, by loading a real observation that
omitted the country and by assembling a real row-set with no country cell:

    model window OPEN: country omitted -> 'ES'
    assembler window OPEN: country cell absent -> 'ES'
    MUTATION APPLIED AND PROVEN OPEN; running gates
    FAILED .../test_detail_record_observations.py::test_related_party_observation_requires_a_stated_country
    FAILED .../test_row_set_assembly.py::test_assemble_related_party_refuses_a_row_with_no_country
    2 failed, 40 passed in 1.19s

Exactly the two refusal gates red and nothing else, so the mutation flipped the
result in one direction only. The two positive controls — the baseline fixture that
must validate, and the assembler case carrying a stated country — stayed green under
the mutation, which is what separates "the gate refused" from "the call was broken
for any input".

That mutation restored both halves of the default at once, which proves the pair was
load-bearing but not which half was. Because the construction site was
double-defaulted — the assembler supplied a country AND the model declared one —
removing either half alone could have been a no-op, and a green suite would look
identical. So the halves were then measured separately, each scenario in its own
process so no model rebuild bled between them, driving the real assembler on a real
row-set carrying no country cell:

    both-fixed      direct_construction=REFUSED (ValidationError)  assembler_no_country=REFUSED    control_KY=KY
    model-only      direct_construction=ES                         assembler_no_country=ES         control_KY=KY
    assembler-only  direct_construction=REFUSED (ValidationError)  assembler_no_country=ES         control_KY=KY
    both-restored   direct_construction=ES                         assembler_no_country=ES         control_KY=KY

The finding is that **neither half was load-bearing alone; they are jointly
load-bearing**. Restoring only the model default and restoring only the assembler
fallback both return the row to Spain, and only the fixed pair refuses. Had this
Step's declared scope been honoured literally — the model file alone — the change
would have been observable only under direct construction and would never have
reached a row, because the assembler is the sole production producer and it supplied
the country unconditionally.

`control_KY=KY` in every row is the positive control: the same row with a country
stated assembles successfully under all four scenarios, so `REFUSED` in the first row
is a refusal on the absent country and not a call that was broken for any input. The
`direct_construction` column isolates the model half, which does flip on its own —
just not on any path a filing travels.

## Notes

**No commit of its own, and not by choice.** All four file edits were swept into a
peer's bare sweeping commit, `feat(cadrumo): land the in-flight source work`, between
the gate run and the attempt to commit them. They are in HEAD and verified there by
reading the code rather than the metadata, but the separate commit the Step was to
land does not exist and cannot be reconstructed without taking peer content. Reported
rather than worked around.

**A field no rule reads.** Nothing in the package classifies a country as a paraíso
fiscal — not under that spelling, not under tax-haven, not under any equivalent. So
the country's only consumer is the DR23200 país field of the row itself. That is a
real loss and the fix stands, but the sharper M349-style consequence, where an
omitted country silently exempted a counterparty from a verification it had to pass,
has no counterpart here. Stated so a later reader does not assume one was found.

**A second site of the same defect, fixed alongside.** The modelo 720 branch of the
same assembler carried the identical `"ES"` fallback while
`Modelo720RowObservation.country_code` was already required — so the requirement was
defeated by its only producer, and the value substituted was the one a declaration of
bienes situados en el extranjero cannot carry. Landed separately as
`fix(modelo-720): stop the row-set assembler declaring a foreign asset as Spanish`.

**The sibling observation models were deliberately left defaulting, and nothing here
rules on their declarable populations.** The donativo and withholding country
defaults are gated on a tax review under a separate row, and that review is not a
code reading; no ruling is made or implied here. What this Step can contribute is
purely structural evidence for it, stated as measurement rather than conclusion: only
modelos 232 and 720 declare a country row_field binding anywhere in the registry
authoring tree, so for the other families no producer can populate the field. The
donativo case is the extreme one — its row-field literal does not admit a country at
all, so the field is unreachable by construction and permanently carries Spain. The
withholding observation's country is consumed by modelos 190 and 193 only; modelo 216
carries no `bindings/` directory in any revision and so declares no bindings at all,
which means it does not reach this defaulting field on any path. The attribution
family's arm stays optional with its upstream fix rowed independently.
