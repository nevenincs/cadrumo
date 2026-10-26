"""Screen: a revision's directory name against the temporal window it actually declares.

The revision directory name is also the revision identifier. It appears in
prose, in tooling output, in review stamps and in every plan and audit that
cites the revision, and readers take its year tokens as fact. Nothing compares
those tokens with the window the revision declares, so a name can say one thing
while ``valid_from``, ``valid_to`` and the period selector say another, and the
registry validates.

The name is read, never trusted, and never used to derive a window. Only these
shapes carry a temporal claim:

- a leading four-digit year is the claimed opening year;
- a second bare four-digit year later in the name closes the claim at that year
  (``2019-2023``, ``2011-julio-2015``);
- the ``y-siguientes`` suffix claims the window is open-ended;
- otherwise a single leading year claims that year alone.

Eight conditions are reported, and every row names one of them:

- ``open_ended_window_not_selectable`` - the revision declares no ``valid_to``,
  which reads as an open-ended window, while its period selector declares
  neither an opening nor a closing year. Selection does not in fact extend
  beyond the named year in this shape: all five instances admit their own year
  and refuse the next. A revision that genuinely runs open-ended carries a
  selector ``year_from``, which is how modelo 194 and modelo 721 serve years
  after the one their name states.
- ``name_opens_after_window`` - the name's leading year is later than the year
  the window opens, so the revision serves years its name does not claim. A
  reader selecting by name understates the revision's reach.
- ``name_opens_before_window`` - the name's leading year is earlier than the
  year the window opens, so the name claims years the revision does not serve.
- ``name_misstates_closing`` - the name closes at a year the window does not.
- ``name_claims_single_year`` - the name gives one year while the window runs
  open-ended AND selection honours that, so the revision really does serve years
  its name omits. A revision whose open-endedness is not selectable is excluded:
  its single-year name describes what it does, and reporting it here would call
  an accurate name misleading. This understates reach rather than overstating it, which is why
  it attracts no attention and is the most common of these.
- ``name_claims_open_ended`` - the name carries the open-ended suffix while the
  window closes. This one reports nothing today and is kept deliberately: the
  shipped registry refuses that exact shape at build time, so no loaded
  authority can carry one, and the condition is a canary rather than dead code.
  A finding here means the refusal upstream stopped happening, which is a
  larger fact than the finding itself. The other direction - a name closing a
  window the declarations leave open - is not refused upstream and is why the
  remaining conditions below exist.
- ``no_temporal_claim`` - the name carries no year at all. Reported rather than
  skipped: a revision slot holding a non-temporal axis is itself worth seeing,
  and dropping those rows would hide it.
- ``window_sources_disagree`` - the window's own opening date and the period
  selector's opening year differ, which is a disagreement between two
  declarations rather than between a name and a declaration.

``valid_from`` is mandatory on a revision and is the declared opening year.
The closing year comes from ``valid_to`` when the revision carries one and from
the period selector's ``year_to`` otherwise. The selector also carries its own
``year_from``, and when that disagrees with ``valid_from`` the disagreement is
reported in its own right: neither is preferred, because a reader cannot tell
which one the law meant.

The screen exits 0 whatever it finds. It reports findings; it does not gate.
A gate belongs here once the names it would refuse have been corrected.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from .corpus import bundled_modelo_ids

__all__ = [
    "KINDS",
    "RevisionNameFinding",
    "name_window_findings",
    "screen_authority",
]

#: Every condition this screen can report, declared once and used at each
#: emission site below. The set was previously recovered by matching the source
#: with four regexes, one added each time a new assignment shape appeared - a
#: keyword argument, a conditional expression, an else-branch - which is the
#: static extraction the sibling gates warn against: it under-reads silently,
#: and an under-read set still compares equal to a docstring that lost the same
#: entry. Declared, it cannot be misread.
KINDS: tuple[str, ...] = (
    "open_ended_window_not_selectable",
    "name_opens_after_window",
    "name_opens_before_window",
    "name_misstates_closing",
    "name_claims_single_year",
    "name_claims_open_ended",
    "no_temporal_claim",
    "window_sources_disagree",
)

_YEAR = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_OPEN_ENDED = "y-siguientes"


@dataclass(frozen=True, slots=True)
class RevisionNameFinding:
    """One disagreement between a revision's name and the window it declares."""

    modelo: str
    revision: str
    kind: str
    detail: str


def _declared_window(revision: ModeloRevision) -> tuple[int | None, int | None, str]:
    """Return the declared opening year, closing year, and the source that carried them."""
    selector = revision.period_selector
    valid_to = None if revision.valid_to is None else revision.valid_to.year
    closing = valid_to if valid_to is not None else selector.year_to
    return revision.valid_from.year, closing, "valid_from"


def _selection_window_findings(
    revision: ModeloRevision,
    *,
    modelo_id: str,
) -> tuple[list[RevisionNameFinding], bool]:
    """Report selector/window disagreement and whether the open window is unselectable."""
    selector = revision.period_selector
    findings: list[RevisionNameFinding] = []
    if selector.year_from is not None and revision.valid_from.year != selector.year_from:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=str(revision.id),
                kind="window_sources_disagree",
                detail=f"valid_from={revision.valid_from.year} period_selector.year_from={selector.year_from}",
            )
        )
    unselectable = revision.valid_to is None and selector.year_from is None and selector.year_to is None
    if unselectable:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=str(revision.id),
                kind="open_ended_window_not_selectable",
                detail=(
                    "valid_to is unset, which reads as open-ended, while the period selector "
                    "declares neither year_from nor year_to"
                ),
            )
        )
    return findings, unselectable


def _opening_name_findings(
    *,
    name: str,
    years: list[int],
    opening: int | None,
    source: str,
    modelo_id: str,
) -> list[RevisionNameFinding]:
    """Report a named opening-year disagreement, if the name carries a year."""
    if not years or opening is None or years[0] == opening:
        return []
    claimed_open = years[0]
    return [
        RevisionNameFinding(
            modelo=modelo_id,
            revision=name,
            kind="name_opens_after_window" if claimed_open > opening else "name_opens_before_window",
            detail=f"name claims {claimed_open}; {source} declares {opening}",
        )
    ]


def _closing_name_findings(
    *,
    name: str,
    years: list[int],
    closing: int | None,
    window_unselectable: bool,
    modelo_id: str,
) -> list[RevisionNameFinding]:
    """Report disagreement between the name's closing claim and declared window."""
    findings: list[RevisionNameFinding] = []
    for finding in (
        _open_ended_name_finding(name=name, closing=closing, modelo_id=modelo_id),
        _single_year_name_finding(
            name=name,
            years=years,
            closing=closing,
            window_unselectable=window_unselectable,
            modelo_id=modelo_id,
        ),
        _misstated_closing_name_finding(
            name=name,
            years=years,
            closing=closing,
            modelo_id=modelo_id,
        ),
    ):
        if finding is not None:
            findings.append(finding)
    return findings


def _open_ended_name_finding(
    *,
    name: str,
    closing: int | None,
    modelo_id: str,
) -> RevisionNameFinding | None:
    """Build the refusal to reconcile an open-ended name with a closed window."""
    if not name.endswith(_OPEN_ENDED) or closing is None:
        return None
    return RevisionNameFinding(
        modelo=modelo_id,
        revision=name,
        kind="name_claims_open_ended",
        detail=f"name claims open-ended; declared window closes {closing}",
    )


def _single_year_name_finding(
    *,
    name: str,
    years: list[int],
    closing: int | None,
    window_unselectable: bool,
    modelo_id: str,
) -> RevisionNameFinding | None:
    """Build the finding for a single-year name on a selectable open window."""
    if name.endswith(_OPEN_ENDED) or len(years) != 1 or closing is not None or window_unselectable:
        return None
    return RevisionNameFinding(
        modelo=modelo_id,
        revision=name,
        kind="name_claims_single_year",
        detail=f"name claims {years[0]} alone; declared window is open-ended",
    )


def _misstated_closing_name_finding(
    *,
    name: str,
    years: list[int],
    closing: int | None,
    modelo_id: str,
) -> RevisionNameFinding | None:
    """Build the finding for a named closing year that differs from the window."""
    if name.endswith(_OPEN_ENDED) or len(years) < 2 or closing is None:
        return None
    claimed_close = years[1]
    if claimed_close == closing:
        return None
    return RevisionNameFinding(
        modelo=modelo_id,
        revision=name,
        kind="name_misstates_closing",
        detail=f"name claims through {claimed_close}; declared window closes {closing}",
    )


def name_window_findings(revision: ModeloRevision, *, modelo_id: str) -> tuple[RevisionNameFinding, ...]:
    """Compare one revision's name tokens with the window it declares."""
    name = str(revision.id)
    findings: list[RevisionNameFinding] = []
    opening, closing, source = _declared_window(revision)
    # An open-ended `valid_to` beside a selector carrying neither bound does not
    # select beyond the named year, so such a revision's single-year name is
    # ACCURATE and must not also be reported as understating its reach.
    selection_findings, window_unselectable = _selection_window_findings(
        revision,
        modelo_id=modelo_id,
    )
    findings.extend(selection_findings)

    years = [int(match) for match in _YEAR.findall(name)]
    if not years:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=name,
                kind="no_temporal_claim",
                detail=f"name carries no year token; declared window opens {opening}",
            )
        )
        return tuple(findings)

    findings.extend(
        _opening_name_findings(
            name=name,
            years=years,
            opening=opening,
            source=source,
            modelo_id=modelo_id,
        )
    )
    findings.extend(
        _closing_name_findings(
            name=name,
            years=years,
            closing=closing,
            window_unselectable=window_unselectable,
            modelo_id=modelo_id,
        )
    )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[RevisionNameFinding, ...]:
    """Screen every revision of the named modelos through the validated authority."""
    findings: list[RevisionNameFinding] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            findings.extend(name_window_findings(revision, modelo_id=modelo_id))
    return tuple(findings)


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = compiled_bundled_authority()
    findings = screen_authority(authority, bundled_modelo_ids())
    census: dict[str, int] = {}
    for finding in findings:
        census[finding.kind] = census.get(finding.kind, 0) + 1
        sys.stdout.write(
            f"revision_name modelo={finding.modelo} revision={finding.revision} "
            f"kind={finding.kind} detail={finding.detail!r}\n"
        )
    tally = " ".join(f"{kind}={count}" for kind, count in sorted(census.items()))
    sys.stdout.write(f"summary findings={len(findings)} {tally}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
