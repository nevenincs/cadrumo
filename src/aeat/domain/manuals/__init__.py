"""Public facade for the AEAT *Manual práctico* handbook corpus.

This package exposes the strict manual schema (:class:`Manual`,
:class:`Chapter`, :class:`Section`, :class:`Paragraph`, :class:`Rule`,
:class:`ManualCasillaReference`), handbook identifiers (:class:`ManualId`,
:class:`ManualPart`), file-backed loaders, rule queries, verification reports,
and manifest-backed raw-PDF fetch results for the annual *Manual práctico de
Renta* and *Manual práctico de IVA* handbooks.

Manual records are public authority corpus data, not operator bucket state.
Source PDFs are represented by :class:`FetchedManualPart` manifests; structured
rules carry :class:`LLMProvenance`, source pointers, casilla/legal references,
and human review fields before they can pass the manual verification gate.
Registry definitions, calculation grounding, and user-facing handbook lookup
consume these records as evidence, while live AEAT access and any persisted
operator workflow remain outside this domain surface.

Callers outside this subpackage import exclusively from
:mod:`aeat.domain.manuals` and must not reach into private modules such as
:mod:`~aeat.domain.manuals._schema`, :mod:`~aeat.domain.manuals._loader`,
:mod:`~aeat.domain.manuals._verify`, :mod:`~aeat.domain.manuals._fetch`, or
:mod:`~aeat.domain.manuals._ids`.

Examples:
    >>> from aeat.domain.manuals import (
    ...     ManualId, ManualPart, fetch_manual_part, load_manual,
    ... )
    >>> result = fetch_manual_part(
    ...     manual_id=ManualId.RENTA,
    ...     year=2025,
    ...     part=ManualPart.PARTE_1,
    ... )
    >>> manual = load_manual(ManualId.RENTA, 2025, ManualPart.PARTE_1)
"""

from __future__ import annotations

from ._errors import (
    ManifestError,
    ManualError,
    ManualNotFoundError,
    ManualParseError,
    ManualReviewRequiredError,
    RuleExtractionError,
)
from ._fetch import (
    PART_SPECS,
    FetchResult,
    PartSpec,
    fetch_manual_part,
    load_manifest,
    lookup_spec,
    verify_fetched_pdf,
    write_manifest,
)
from ._loader import (
    find_rules,
    iter_sections,
    load_catalogue,
    load_manual,
    load_section,
    resolve_part_root,
)
from ._rule_id import generate_rule_id
from ._schema import (
    Chapter,
    FetchedManualPart,
    LLMProvenance,
    Manual,
    ManualCasillaReference,
    ManualCatalogue,
    ManualId,
    ManualPart,
    Paragraph,
    Rule,
    RuleKind,
    RuleSource,
    Section,
    SectionRef,
    SectionSource,
)
from ._verify import (
    ManualVerificationIssue,
    ManualVerificationReport,
    raise_on_errors,
    verify_manual_dir,
)

__all__ = [
    "PART_SPECS",
    "Chapter",
    "FetchResult",
    "FetchedManualPart",
    "LLMProvenance",
    "ManifestError",
    "Manual",
    "ManualCasillaReference",
    "ManualCatalogue",
    "ManualError",
    "ManualId",
    "ManualNotFoundError",
    "ManualParseError",
    "ManualPart",
    "ManualReviewRequiredError",
    "ManualVerificationIssue",
    "ManualVerificationReport",
    "Paragraph",
    "PartSpec",
    "Rule",
    "RuleExtractionError",
    "RuleKind",
    "RuleSource",
    "Section",
    "SectionRef",
    "SectionSource",
    "fetch_manual_part",
    "find_rules",
    "generate_rule_id",
    "iter_sections",
    "load_catalogue",
    "load_manifest",
    "load_manual",
    "load_section",
    "lookup_spec",
    "raise_on_errors",
    "resolve_part_root",
    "verify_fetched_pdf",
    "verify_manual_dir",
    "write_manifest",
]
