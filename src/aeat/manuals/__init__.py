"""AEAT *Manual práctico* corpus subpackage.

Provides the typed schema, file-backed loader, query API, verification
report, and raw-manual fetcher for the annual AEAT *Manual práctico de
Renta* and *Manual práctico de IVA* handbooks. The handbook is the
*de facto* rule book for every modelo the project files, and every
downstream issue (casilla DB ``#23``, schema extractor ``#9``,
self-healing sync ``#11``, future filing modules) consumes this
schema.

Public surface — callers from outside this subpackage must import
exclusively from ``aeat.manuals`` and MUST NOT reach into private
``_schema``, ``_loader``, ``_verify``, ``_fetch``, ``_ids``, or
``_stubs`` modules.

Example:
    ```python
    from aeat.manuals import ManualId, ManualPart, fetch_manual_part, load_manual

    # Materialise the raw PDF + manifest (first run only):
    result = fetch_manual_part(
        manual_id=ManualId.RENTA,
        year=2025,
        part=ManualPart.PARTE_1,
    )

    # Load a manual after structure/ content has been populated
    # by follow-up extraction/review workflows:
    manual = load_manual(ManualId.RENTA, 2025, ManualPart.PARTE_1)
    ```
"""

from __future__ import annotations

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
from ._ids import generate_rule_id
from ._loader import (
    find_rules,
    iter_sections,
    load_catalogue,
    load_manual,
    load_section,
    resolve_part_root,
)
from ._schema import (
    Chapter,
    FetchedManualPart,
    LLMProvenance,
    Manual,
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
    VerificationIssue,
    VerificationReport,
    raise_on_errors,
    verify_manual_dir,
)
from .errors import (
    ManifestError,
    ManualError,
    ManualNotFoundError,
    ManualParseError,
    ManualReviewRequiredError,
    RuleExtractionError,
)

__all__ = [
    "PART_SPECS",
    "Chapter",
    "FetchResult",
    "FetchedManualPart",
    "LLMProvenance",
    "ManifestError",
    "Manual",
    "ManualCatalogue",
    "ManualError",
    "ManualId",
    "ManualNotFoundError",
    "ManualParseError",
    "ManualPart",
    "ManualReviewRequiredError",
    "Paragraph",
    "PartSpec",
    "Rule",
    "RuleExtractionError",
    "RuleKind",
    "RuleSource",
    "Section",
    "SectionRef",
    "SectionSource",
    "VerificationIssue",
    "VerificationReport",
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
