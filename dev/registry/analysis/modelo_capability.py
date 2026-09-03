"""Screen: what each modelo can actually do, stated rather than inferred.

Not every AEAT modelo is a filing. Some are censal (the alta, modificacion and
baja of 036 and 038), some are informational declarations, some are filed on
AEAT's sede and produce no fichero here at all. A reader asking "which modelos
can this product calculate and file, and for which years" should not have to
reconstruct the answer from grades, layouts and directory listings, and until
this screen existed that is exactly what it took.

The answer is already declared; it was simply never assembled. Five facts decide
it, and each is read from the validated authority rather than a maintained list:

- ``authority_grade`` is the modelo's own claim about the rung it reaches -
  ``filing``, ``calculation`` or ``applicability``. A revision claiming
  ``applicability`` is saying it can tell you whether the modelo applies, not
  that this product can compute or submit it.
- an export layout is what a fichero is rendered from; a filing claim without
  one has nowhere to put the answer.
- a filing envelope is the transport wrapper AEAT's variable-composition
  designs require. It is not universally mandatory: a design declaring no
  envelope is complete as records alone, and an XML-dictionary layout is
  forbidden from carrying one. So its absence is only meaningful where the
  official design declares one.
- a committed generated export tree is the only evidence the bytes have ever
  been produced.
- a deadline window is what says WHEN the filing is due. A revision that can
  render a fichero but cannot say when it must be presented has answered half
  the question a filer asks.

Six conditions are reported, and every row names one:

- ``claims_filing_without_layout`` - a revision at filing grade that declares no
  export layout. The claim has no renderable form behind it.
- ``envelope_spelled_as_record`` - a layout carrying its envelope smuggled into
  the record tuple as an ``envelope_header`` pseudo-record instead of the typed
  ``filing_envelope`` slot. The bytes may look right and the transport is
  invisible to every consumer that asks the layout whether it has an envelope -
  including the export boundary, which then takes the plain-records path and
  REFUSES the product and software identity that an enveloped filing must
  carry.

- ``files_here_without_deadline`` - a revision that reaches filing grade with a
  layout while declaring no deadline window at all. Twenty-two other revisions
  also declare none, and every one of those sits below filing grade, where
  saying nothing about a due date is the correct and complete answer. These five
  claim they can be filed and cannot say by when.
- ``files_here_for_years_it_cannot_date`` - a filing-grade revision whose
  declared window spans years its deadline windows do not cover. The revision
  can be filed for those years and cannot say by when. Nine revisions have this
  temporal gap and six are filing grade; the other three sit below filing grade,
  where the gap costs nothing, and are left to the temporal screen.

- ``claims_calculation_without_formulas`` - a filing-grade revision whose modelo
  declares `calculation_class = filing` while the revision declares no formula.
  Fourteen filing-grade revisions carry no formula and ten of them are right to:
  their modelo declares itself informative, and a declaracion informativa
  transmits data rather than computing a liability. The distinction is read from
  the modelo's own declared calculation class, so an informative modelo is never
  asked for arithmetic it has no reason to do.
- ``tree_ships_below_filing_grade`` - a revision that ships a committed
  generated export tree while declaring a grade below filing. The product is
  shipping the bytes of a filing for a revision whose own declaration says it
  cannot file. One of the two carries a reviewer attestation limiting itself to
  "scheduling and applicability only" and describing a declaration far smaller
  than the one now shipped, so the grade is a stale snapshot of a review the
  later content never received. This condition is deliberately structural
  rather than a reading of that prose: an attestation is a person's signed
  statement at a point in time and must not be rewritten to match the data,
  which makes the disagreement between them the only honest signal.

An earlier revision of this screen reported a fourth condition, a filing-grade
layout with no envelope, and counted 52 of them. That count was mostly noise: it
treated the envelope as universally required, ignored the second legal spelling
``auxiliary_envelope_header``, and counted XML-dictionary layouts that may never
carry one. Grounding each against the bundled official designs left 22 real
cases, all of them the record-spelling above. The condition was replaced rather
than tuned, because a screen whose signal is a third of its rows teaches its
reader to skim.

None of these is automatically a defect. A modelo that is genuinely not filed
here SHOULD sit at applicability with nothing behind it, and that state produces
no row at all. What the screen refuses to do is let a filing claim and the
machinery behind it drift apart silently.

The mirror of that condition - a revision carrying a layout while declaring a
grade below filing - is deliberately NOT reported here. The grade screen already
reports it, as an under-declared grade naming ``export_layout`` as the
prerequisite that supports a higher one, and the two populations were measured
identical: the same twenty-five revisions, with nothing on either side. One
stated the symptom and the other states the conclusion and which prerequisite
drives it, so keeping both was one fact under two names.


The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline._provenance_manifest import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .corpus import bundled_modelo_ids
from .temporal_site_agreement import undated_window_years

__all__ = [
    "ModeloCapability",
    "ModeloCapabilityFinding",
    "capability_census",
    "screen_authority",
]


@dataclass(frozen=True, slots=True)
class ModeloCapability:
    """What one revision of one modelo declares it can do, and what stands behind it."""

    modelo: str
    revision: str
    grade: str
    layouts: int
    envelopes: int
    record_spelled_envelopes: int
    xml_dictionary_layouts: int
    deadline_windows: int
    calculation_class: str
    formulas: int
    committed_tree: bool
    #: Years inside the revision's own declared window that no deadline window
    #: covers, as the temporal screen reports them. Taken from that screen
    #: rather than recomputed: which years a revision serves is stated in three
    #: places the temporal screen already reconciles, and a second reading here
    #: would be a second answer to a question it exists to settle.
    undated_window_years: tuple[int, ...] = ()

    @property
    def files_here(self) -> bool:
        """Whether this revision claims filing grade and carries a layout to render."""
        return self.grade == "filing" and self.layouts > 0


@dataclass(frozen=True, slots=True)
class ModeloCapabilityFinding:
    """One disagreement between a revision's declared rung and its machinery."""

    modelo: str
    revision: str
    kind: str
    detail: str


def _typed_envelope(layout: object) -> bool:
    """Whether a layout declares its transport wrapper in either typed slot.

    Two spellings are legitimate: the variable-composition ``filing_envelope``
    and the total-less ``auxiliary_envelope_header`` page-zero header. Counting
    only the first understates the corpus, which is how this screen first
    reported thirty correct declarations as gaps.
    """
    return (
        getattr(layout, "filing_envelope", None) is not None
        or getattr(layout, "auxiliary_envelope_header", None) is not None
    )


def _record_spelled_envelope(layout: object) -> bool:
    """Whether a layout hides an envelope in its records instead of declaring one."""
    if _typed_envelope(layout):
        return False
    return any(str(getattr(record, "record_type", "")) == "envelope_header" for record in layout.records)


def _is_xml_dictionary(layout: object) -> bool:
    """Whether the layout is an XML dictionary, which may never carry an envelope."""
    return str(getattr(layout, "format", "")) == "xml_dictionary"


def _committed_tree(modelo: str, revision: str) -> bool:
    """Whether a PUBLISHED export tree is committed for this revision.

    Tested by the generation provenance manifest rather than by the directory
    holding it. The two agree across the whole corpus today - all 28 export
    directories carry a manifest - but they are different claims: the directory
    is where a revision's authored layout fragments live, and publication writes
    the generated tree into the same place. A revision that declared export
    layouts without ever being published would have the directory and no
    manifest, and the directory test would report it as shipping filing bytes it
    has never produced.
    """
    export_root = bundled_path("registry", "aeat", "modelos", modelo, "revisions", revision, "export")
    return (export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME).is_file()


def capability_census(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ModeloCapability, ...]:
    """Return what every revision of every named modelo declares it can do."""
    rows: list[ModeloCapability] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision_id, revision in definition.revisions.items():
            layouts = revision.export_layouts
            rows.append(
                ModeloCapability(
                    modelo=modelo_id,
                    revision=str(revision_id),
                    grade=str(revision.authority_grade).rsplit(".", 1)[-1],
                    layouts=len(layouts),
                    envelopes=sum(1 for item in layouts if _typed_envelope(item)),
                    record_spelled_envelopes=sum(1 for item in layouts if _record_spelled_envelope(item)),
                    xml_dictionary_layouts=sum(1 for item in layouts if _is_xml_dictionary(item)),
                    deadline_windows=len(revision.deadline_windows),
                    calculation_class=str(definition.calculation_class).rsplit(".", 1)[-1],
                    formulas=len(revision.formulas),
                    committed_tree=_committed_tree(modelo_id, str(revision_id)),
                    undated_window_years=undated_window_years(revision),
                )
            )
    return tuple(rows)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ModeloCapabilityFinding, ...]:
    """Report every revision whose declared rung and its machinery disagree."""
    findings: list[ModeloCapabilityFinding] = []
    for row in capability_census(authority, modelo_ids):
        if row.grade == "filing" and row.layouts == 0:
            findings.append(
                ModeloCapabilityFinding(
                    modelo=row.modelo,
                    revision=row.revision,
                    kind="claims_filing_without_layout",
                    detail="declares filing grade and no export layout to render it from",
                )
            )
        if row.files_here and row.calculation_class == "filing" and not row.formulas:
            findings.append(
                ModeloCapabilityFinding(
                    modelo=row.modelo,
                    revision=row.revision,
                    kind="claims_calculation_without_formulas",
                    detail=(
                        "the modelo declares a filing calculation class while this revision "
                        "declares no formula, so nothing computes what the filing reports"
                    ),
                )
            )
        if row.files_here and not row.deadline_windows:
            findings.append(
                ModeloCapabilityFinding(
                    modelo=row.modelo,
                    revision=row.revision,
                    kind="files_here_without_deadline",
                    detail=(
                        "reaches filing grade with a layout but declares no deadline window, "
                        "so it cannot say when the filing is due"
                    ),
                )
            )
        if row.files_here and row.undated_window_years:
            findings.append(
                ModeloCapabilityFinding(
                    modelo=row.modelo,
                    revision=row.revision,
                    kind="files_here_for_years_it_cannot_date",
                    detail=(
                        f"reaches filing grade and declares no deadline window for "
                        f"{len(row.undated_window_years)} year(s) of its own window: "
                        f"{list(row.undated_window_years)}"
                    ),
                )
            )
        if row.committed_tree and row.grade != "filing":
            findings.append(
                ModeloCapabilityFinding(
                    modelo=row.modelo,
                    revision=row.revision,
                    kind="tree_ships_below_filing_grade",
                    detail=(
                        f"ships a committed export tree while declaring {row.grade} grade, "
                        "so filing bytes are shipped for a revision that declares it cannot file"
                    ),
                )
            )
        if row.record_spelled_envelopes:
            findings.append(
                ModeloCapabilityFinding(
                    modelo=row.modelo,
                    revision=row.revision,
                    kind="envelope_spelled_as_record",
                    detail=(
                        f"{row.record_spelled_envelopes} layout(s) carry an envelope_header record "
                        "instead of a typed envelope, so the export boundary cannot see the envelope "
                        "and refuses the product identity an enveloped filing requires"
                    ),
                )
            )
    return tuple(findings)


def main() -> int:
    """Print one row per revision, then the findings and a closing census; always exit 0."""
    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    census = capability_census(authority, modelo_ids)
    for row in census:
        sys.stdout.write(
            f"capability modelo={row.modelo} revision={row.revision} grade={row.grade} "
            f"layouts={row.layouts} envelopes={row.envelopes} tree={row.committed_tree} "
            f"files_here={row.files_here}\n"
        )
    findings = screen_authority(authority, modelo_ids)
    tally: dict[str, int] = {}
    for finding in findings:
        tally[finding.kind] = tally.get(finding.kind, 0) + 1
        sys.stdout.write(
            f"capability_finding modelo={finding.modelo} revision={finding.revision} "
            f"kind={finding.kind} detail={finding.detail!r}\n"
        )
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(tally.items()))
    filing = sum(1 for row in census if row.files_here)
    sys.stdout.write(f"summary revisions={len(census)} file_here={filing} findings={len(findings)} {kinds}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
