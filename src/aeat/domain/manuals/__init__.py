"""AEAT *Manual práctico* corpus subpackage.

Provides the typed schema, file-backed loader, query API, verification
report, and raw-manual fetcher for the annual AEAT *Manual práctico de
Renta* and *Manual práctico de IVA* handbooks. The handbook is the
*de facto* rule book for every modelo the project files, and the
registry definitions, schema extractor, and downstream filing modules all
consume this schema.

Public surface: callers from outside this subpackage must import
exclusively from :mod:`aeat.domain.manuals` and MUST NOT reach into the
private :mod:`~aeat.domain.manuals._schema`,
:mod:`~aeat.domain.manuals._loader`, :mod:`~aeat.domain.manuals._verify`,
:mod:`~aeat.domain.manuals._fetch`, or :mod:`~aeat.domain.manuals._ids`
modules.

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
