---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:5191896a579cdc25d3550f06c7b52a61d1fe37c605123f26d8de9e096092e124'
step_id: 'S09'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Establish whether Modelo 200 and Modelo 202 can declare the authenticated filed-declarations read surface at all, keeping this separate from the consumption question S08 asks. The nine structurally excluded carry slots are a coverage gap in what the pull can FETCH, not a wiring gap in what the engine CONSUMES, and the two must not be ruled on as one. Determine from AEAT published material whether filed Sociedades declarations are exposed at the consulta view the reader is pinned to. If they are, the registry revisions are missing a live cross-reference and the nine become reachable. If AEAT does not expose them there, the nine are correctly unreachable and the honest output is a documented refusal naming the reason rather than a fix. Gate: the verdict cites AEAT published material rather than an inference from the registry silence, no live submission or remote mutation is performed, and either outcome lands as a change to the tree - a declared read surface or a recorded refusal - never as an open question

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200`
- `src/cadrumo/_data/registry/aeat/modelos/202`

## Description

- Read the pull-support boundary at its single decision point rather than inferring it, and confirmed by a real planner call that modelo 200 and modelo 202 yield no queryable pair.
- Compared how the 23 declaring modelos carry the read surface against how modelo 200 and 202 carry cross-references at all, to test whether the absence looks principled or merely unauthored.
- Searched the modelo 200 and 202 registry trees for any recorded rationale for the absence.
- Searched the bundled AEAT corpus for published material bearing on the consulta surface's modelo coverage.
- Ran the projection behind the one operator surface that speaks to a missing AEAT history, which the sibling row could only reason about.
- Recorded the refusal the gate permits, and named exactly what an operator would have to supply to settle the question.

## Outcome

THE VERDICT IS A RECORDED REFUSAL. Whether AEAT exposes filed Sociedades declarations at the consulta view cannot be established from anything in this repository, and no live read was performed or attempted. What follows is what IS established, so the refusal is bounded rather than a shrug.

THE BOUNDARY HAS ONE AUTHORITY, NOT TWO. The diversion is derived, not hardcoded: the unsupported-reason helper reads each in-range revision's live cross references and asks for one whose surface is the authenticated read surface and whose id ends with the filed-declarations read. There is no second site listing unsupported modelos by hand, so the reconciliation risk the row raised does not exist. A real planner call over modelo 200 and 202 for filing years 2023 to 2025 returns zero queryable pairs and six typed unsupported rows.

THE ABSENCE IS UNDOCUMENTED AND DOES NOT LOOK PRINCIPLED. The declaration is all-or-nothing per modelo: every one of the 23 declaring modelos declares on every revision it has, and not one declares on only some. Modelo 200 has one revision and modelo 202 has three, and none of the four declares it. They are not blank records that nobody annotated: each carries a live cross reference, but only for static official documentation. That is not a marker of deliberate exclusion, because 26 of the declaring revisions carry a static-documentation reference too. Nothing in either modelo's registry tree records a reason for the absence.

SO THE TWO HYPOTHESES REMAIN OPEN, AND THE TREE CANNOT SEPARATE THEM. Nothing in the registry, and nothing in the bundled corpus, says whether AEAT serves these modelos at the consulta view. The bundle carries no modelo 200 instructions at all. The modelo 202 instructions mention consulta three times, and all three are about consulting applicable tax rates or a Dirección General de Tributos binding ruling, none about the sede consulta-de-declaraciones-presentadas service. Inferring AEAT's coverage from our own silence is precisely what this row forbids, so the honest output is that it is unresolved.

WHAT THE OPERATOR WOULD HAVE TO SUPPLY, and it is small. The register's own modelo combobox is the authoritative list of what the consulta view serves, and this application already reads and parses it: the availability reader returns the offered modelo options from that surface. One authenticated, read-only run of the discovery verb, performed by the operator, would answer it outright. If 200 or 202 appears among the offered modelo options, our registry is missing a declaration and the nine slots become reachable. If neither appears, the nine are correctly unreachable and this refusal becomes the documented answer. No new capability is needed, no submission occurs, and the read stays pinned to the consulta view the reader already fails closed on.

A DEFECT FOUND ALONG THE WAY THAT DOES NOT DEPEND ON THE ANSWER. The refusal an operator actually reads says that the AEAT declarations register does not offer the modelo, and only then gives the real reason, that the registry revision declares no such surface. The first clause asserts a fact about AEAT's coverage which is only a fact about our own registry, which is the exact inference this row exists to forbid, shipped in operator-facing text and backed by nothing. It is wrong whichever way the underlying question resolves, so it is opened as its own row rather than left inside this one.

THE SURFACE THE SIBLING ROW COULD NOT MEASURE IS WORSE THAN IT ASSUMED. That row asked whether the no-AEAT-history notice is rendered to a Sociedades-only filer and marked the question as reasoning rather than measurement. Measured here: the notice builder has NO production caller. It is defined in the overview evidence module, re-exported through the calendar module and the package facade, and referenced nowhere else in shipped code except its own test. Zero callers is not evidence of dead code, it is evidence of no wired consumer, and that is what this is. So the question resolves in an unexpected direction: the notice does not misdirect a Sociedades filer, because it does not reach any operator at all. The concern about its suggestion naming a verb that cannot fetch modelo 200 or 202 stands for the moment it IS wired, which is why it belongs in the row that owns wiring it.

## Verification

    uv run --no-sync python -c "<real planner call over modelo 200 and 202, 2023-2025>"
    queryable pairs: []
    FAILURE modelo=200 year=2025 ... AEAT declarations register does not offer modelo '200'
    total unsupported rows: 6

    uv run --no-sync python -c "<read-surface declaration shape over the loaded authority>"
    modelos declaring on >=1 revision: 23
      declaring on ALL their revisions: 23
      declaring on SOME only: 0
      modelo 200: 1 revision, 0 declaring, surfaces=['static_official_documentation']
      modelo 202: 3 revisions, 0 declaring, surfaces=['static_official_documentation'] each

    among revisions that DECLARE the read surface:
        26  also carry static_official_documentation
        11  read surface only

The 26 figure is what refutes the tempting reading that carrying only a static-documentation reference marks a modelo as deliberately excluded. It does not: most declaring revisions carry one as well.

Corpus search for published material: no modelo 200 instructions are bundled, and the three consulta mentions in the modelo 202 instructions were read individually rather than counted, and none refers to the sede declaraciones-presentadas service.

No pytest lane was run. This step changed no production code and wrote no test.

NO LIVE READ WAS PERFORMED. No AEAT endpoint was contacted, the live-tests opt-in was never set, and no authenticated session was resolved at any point.

## Notes

WHAT I COULD NOT ESTABLISH, stated plainly rather than inferred. Whether AEAT serves modelo 200 and 202 at the consulta view. Whether the absent declaration was a deliberate authoring decision or an omission, since no rationale is recorded either way and the person who authored those revisions is not available in the tree. Both are answerable only by the operator-authorised capture described above.

AN ADJACENT FINDING, reported rather than chased because it is outside this row. All four locale catalogues carry the notice's message key with its value equal to the key itself, which is the self-referencing scaffold placeholder shape the locale honesty ratchet exists to refuse. The notice's own test asserts the rendered message does not contain the raw key, so the default text is winning at runtime today, but the catalogue entries are placeholders rather than translations. Whoever wires the notice should land real values in all four catalogues in the same change.

A ROW THAT MAY BE CHECKED WITHOUT ITS DELIVERABLE. The history-onboarding plan carries a closed row for adding this overview notice. The builder and its test exist, so the row is not fraudulent, but nothing calls the builder, so no operator can receive the notice the row was opened to give them. That is the delivered-narrower shape rather than delivered-as-specified, and it is named here because this row's own question ran into it.
