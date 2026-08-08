---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:702b3346d254f863af3315f17f108c043d8b6d2e2422fbb7b866247af3be8bad'
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

The second-representation premise in the Step is confirmed and worth stating
precisely: the operator-supplied CLI row and this registry-side observation are two
independent constructions of one M232 operation, the CLI row reaching the fichero via
operator key-value pairs and this one via the Sheets Detalle round-trip. Only the
first had been made required, so the modelo read as covered from either surface alone.

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

**Four sibling observation models were deliberately left defaulting.** Modelos 182,
184, 190 and 193 each carry a `country_code` field defaulting to Spain, and none is
tightened. The reason is structural rather than a judgement call: only modelos 232
and 720 declare a country row_field binding anywhere in the registry authoring tree,
so for the other four no producer can populate the field and requiring it would
refuse every row while naming a fact no surface records. Modelo 182 is the extreme
case — its row-field literal does not admit a country at all, so the field is
unreachable by construction and permanently carries Spain. The upstream fix for the
modelo 184 arm is already rowed independently.
