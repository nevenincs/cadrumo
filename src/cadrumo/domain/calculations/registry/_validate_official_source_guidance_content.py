"""Registry-build gate: an ``official_source_guidance`` claim must back its usage.

``evidence_tier = "official_source_guidance"`` is checked at four sites --
cross-reference applicability predicates, application links, verification
expectations, and deadline windows (``_validate_surfaces.py``) -- but every one
of those checks only asks whether a cited source carries the *tier*, never
whether the source's own text supports the specific claim the site is making.
That is precisely where ``layout_authority`` stood before
:func:`cadrumo.domain.calculations.registry.validate_layout_authority_content.validate_layout_authority_content`
closed it, and that fix's calibration history is the cautionary lesson here:
its first draft (a dispositive-content regex in ``_legal.py``) false-fired on
630 of 633 legal-catalogue entries, and a second, narrower attempt still
mis-fired on 59. A single generic "does this official_source_guidance source
carry guidance prose" probe runs into the same wall for a different reason:
the tier backs FOUR structurally different claims (a filing deadline, a
verification expectation, an application-link surface, an applicability
predicate), a bare-law source like the LIRPF (``ley-35-2006.html``) is cited
by many unrelated modelos without ever needing to spell out which one, and a
correctly-cited amending article need not literally restate the numeral of
the modelo it amends (Orden HAC/1526/2024's own article 1 modifies "los
articulos 14, 15 y 16" of an earlier order without ever writing "037" -- the
modelo it suppresses -- so a naive "the source must name its own modelo
number" check mis-fires on the CORRECT citation and would have been a third
instance of the same failure class).

What survived calibration is two independently testable, single-purpose
sub-checks, each scoped to exactly the claim the site is honestly making --
the same discipline ``_legal.py``'s narrow ``_MODELO_ANCHOR`` scoping used to
land its own dispositive-content check after the broad version failed twice:

* :func:`validate_suppression_notice_content` -- ``kind = "suppression_notice"``
  asserts the cited document is where a modelo's SUPPRESSION is recorded. The
  claim is testable directly: the text must carry a suppression-establishing
  stem (``suprim*``, ``derog*``, or an equivalent "queda sin efecto" /
  "deja de" turn of phrase). The population is exhaustive and currently one
  source: ``boe-modelo-037-historical-suppression``, which points at Orden
  HAC/1526/2024's ``disposicion final unica`` (its entry-into-force clause,
  "se aplica ... a los modelos 030 y 036 ...") rather than the order's
  article 1 (the amendment that actually retires modelo 037's active
  surfaces) -- a source about WHEN the order took effect, cited as though it
  were the source that says WHAT was suppressed.

* :func:`deadline_window_content_failures` -- a ``deadline_window`` asserts
  official guidance for WHEN a filing is due. Unlike the other three sites,
  this claim is narrow and near-universal across the corpus: a genuine AEAT
  procedure page, instruction manual, or calendar almost always states a
  "plazo de presentacion" somewhere. Scoped to windows only (never
  ``applicability_conditions``, whose claim is about WHO must file, a
  heterogeneous population of profile predicates this module does not
  attempt to content-probe), calibrated against every deadline window in the
  bundled registry: 449 of 453 pass on the strength of their own cited text,
  and the 4 that do not are the same real gap under one modelo -- 115's four
  quarterly windows cite only two sources that establish who must withhold
  on rental income, never when the resulting declaration is due.

Both checks accept broadly and refuse narrowly, on the same principle
``_validate_layout_authority_content.py`` documents: refuse on CONTENT, never
on size, and scope tightly enough that the accepting vocabulary cannot be
satisfied by boilerplate every document in the corpus already carries.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from .schema_base import RegistrySourceKind
from ._source_file_text import read_source_file_text
from ._validate_evidence import EvidenceValidator
from .schema_deadlines import DeadlineWindowDefinition
from .schema_references import SourceReference

#: A suppression notice must itself say something was suppressed or repealed.
#: Deliberately stem-based (not "suprimido"/"derogado" as exact forms) so it
#: survives verb conjugation and gender/number agreement without becoming so
#: broad it matches unrelated vocabulary -- there is no third stem sharing
#: this prefix in Spanish legal prose.
_SUPPRESSION_VOCABULARY: Final = re.compile(r"suprim\w*|derog\w*|queda\s+sin\s+efecto")

#: A deadline claim must itself say something about a filing window: the noun
#: "plazo" (deadline/window), a form of "presentar"/"presentacion", a specific
#: "vencimiento" (expiry), or the "dias naturales" idiom AEAT deadlines are
#: near-universally phrased in. Matched against normalised text (accent-folded,
#: casefolded by :func:`~cadrumo.core.corpus_text.normalise_corpus_text`), so
#: no accent variants are needed here.
_DEADLINE_VOCABULARY: Final = re.compile(r"plazo|presentaci\w*|vencimient\w*|dias?\s+natural")


def _carries_suppression_content(text: str) -> bool:
    return bool(_SUPPRESSION_VOCABULARY.search(text))


def _carries_deadline_content(text: str) -> bool:
    return bool(_DEADLINE_VOCABULARY.search(text))


def validate_suppression_notice_content(
    sources: Mapping[str, SourceReference],
    *,
    source_root: Path | None,
) -> list[str]:
    """Return one failure per ``suppression_notice`` claim its own file cannot support.

    Scoped to ``kind = "suppression_notice"`` sources declaring
    ``evidence_tier = "official_source_guidance"`` -- the only combination
    this kind currently ships under. A file that cannot be read from this
    root is skipped rather than reported, matching
    :func:`~cadrumo.domain.calculations.registry.validate_layout_authority_content.validate_layout_authority_content`.

    Args:
        sources: The registry source catalogue, keyed by source ID.
        source_root: Repository root for resolving ``corpus_path``; when
            ``None``, no file is reachable and the check yields nothing.

    Returns:
        Accumulated diagnostics; empty when every suppression-notice claim is
        backed by suppression-establishing text.
    """
    if source_root is None:
        return []
    failures: list[str] = []
    for source_id, source in sorted(sources.items()):
        if source.kind is not RegistrySourceKind.SUPPRESSION_NOTICE or source.evidence_tier != "official_source_guidance":
            continue
        raw = read_source_file_text(source_root, source)
        if raw is None or _carries_suppression_content(raw):
            continue
        failures.append(
            f"source {source_id!r} declares kind='suppression_notice' but its bundled file "
            f"{source.corpus_path!r} carries no suppression-establishing text (no 'suprim*', "
            "'derog*', or 'queda sin efecto' turn of phrase) -- it cannot be where a modelo's "
            "suppression is recorded. Cite the amending article that actually performs the "
            "suppression, not an adjacent entry-into-force or scope clause of the same order",
        )
    return failures


def deadline_window_content_failures(
    prefix: str,
    window: DeadlineWindowDefinition,
    *,
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return a failure when none of a deadline window's own sources say WHEN.

    ``require_source_tier`` already proved the window cites at least one
    ``official_source_guidance`` source; this asks the stronger question of
    whether ANY of them carries deadline vocabulary of its own. Scoped to
    :class:`DeadlineWindowDefinition` only, never its
    ``applicability_conditions`` -- a condition's claim is about WHO must
    file (an open, profile-predicate-shaped population no single vocabulary
    check can honestly cover), while a window's claim is narrowly WHEN, which
    a genuine AEAT procedure page, instruction manual, or calendar almost
    always states.

    Args:
        prefix: Validation-message scope prefix (matches the sibling checks
            in ``_validate_surfaces.py``).
        window: The deadline window being checked.
        source_refs: The registry source catalogue, keyed by source ID.
        evidence: The revision's :class:`EvidenceValidator`, reused for its
            cached, PDF-sidecar-aware text resolution rather than
            duplicating it here.

    Returns:
        A single-element list naming the window when none of its
        ``official_source_guidance`` sources carry deadline vocabulary;
        empty otherwise, including when no such source is reachable (an
        unreachable corpus is a different, already-reported failure).
    """
    osg_refs = [
        ref
        for ref in window.source_refs
        if (source := source_refs.get(ref)) is not None and source.evidence_tier == "official_source_guidance"
    ]
    if not osg_refs:
        return []
    any_reachable = False
    for ref in osg_refs:
        text = evidence.source_text(source_refs[ref])
        if text is None:
            continue
        any_reachable = True
        if _carries_deadline_content(text):
            return []
    if not any_reachable:
        # No cited source could be read from this root -- an unreachable
        # corpus is a different, already-reported failure (verify_source_catalogue
        # / EvidenceValidator.validate_source_citations own that message), and
        # this check must not invent a content claim about a file it never saw.
        return []
    return [
        f"{prefix}: deadline window {window.id!r} cites official_source_guidance source(s) "
        f"{sorted(osg_refs)!r} but none of their bundled text states a filing deadline (no "
        "'plazo', 'presentacion', 'vencimiento', or 'dias naturales' turn of phrase) -- they "
        "may ground WHO must file without ever grounding WHEN. Cite a source that states this "
        "window's actual filing deadline",
    ]


__all__ = ["deadline_window_content_failures", "validate_suppression_notice_content"]
