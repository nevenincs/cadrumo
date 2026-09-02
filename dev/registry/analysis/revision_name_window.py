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

Six conditions are reported, and every row names one of them:

- ``selector_declares_no_window`` - the period selector carries neither an
  opening nor a closing year, so the name is the only place the revision's
  span is stated. Reported ahead of any name comparison, because the remedy is
  to author the declaration rather than to correct the name.
- ``name_opens_after_window`` - the name's leading year is later than the year
  the window opens, so the revision serves years its name does not claim. A
  reader selecting by name understates the revision's reach.
- ``name_opens_before_window`` - the name's leading year is earlier than the
  year the window opens, so the name claims years the revision does not serve.
- ``name_misstates_closing`` - the name closes at a year the window does not.
- ``name_claims_single_year`` - the name gives one year while the window runs
  open-ended. This understates reach rather than overstating it, which is why
  it attracts no attention and is the most common of these.
- ``name_claims_open_ended`` - the name carries the open-ended suffix while the
  window closes.
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

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision

__all__ = [
    "RevisionNameFinding",
    "name_window_findings",
    "screen_authority",
]

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


def name_window_findings(revision: ModeloRevision, *, modelo_id: str) -> tuple[RevisionNameFinding, ...]:
    """Compare one revision's name tokens with the window it declares."""
    name = str(revision.id)
    findings: list[RevisionNameFinding] = []
    opening, closing, source = _declared_window(revision)

    selector_from = revision.period_selector.year_from
    if selector_from is not None and revision.valid_from.year != selector_from:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=name,
                kind="window_sources_disagree",
                detail=f"valid_from={revision.valid_from.year} period_selector.year_from={selector_from}",
            )
        )

    selector = revision.period_selector
    if selector.year_from is None and selector.year_to is None:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=name,
                kind="selector_declares_no_window",
                detail=f"period selector declares neither year_from nor year_to; valid_from is {opening}",
            )
        )

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

    claimed_open = years[0]
    if opening is not None and claimed_open != opening:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=name,
                kind=("name_opens_after_window" if claimed_open > opening else "name_opens_before_window"),
                detail=f"name claims {claimed_open}; {source} declares {opening}",
            )
        )

    open_ended = name.endswith(_OPEN_ENDED)
    claimed_close = years[1] if len(years) > 1 and not open_ended else None
    if open_ended and closing is not None:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=name,
                kind="name_claims_open_ended",
                detail=f"name claims open-ended; declared window closes {closing}",
            )
        )
    elif not open_ended and claimed_close is None and closing is None and len(years) == 1:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=name,
                kind="name_claims_single_year",
                detail=f"name claims {claimed_open} alone; declared window is open-ended",
            )
        )
    elif claimed_close is not None and closing is not None and claimed_close != closing:
        findings.append(
            RevisionNameFinding(
                modelo=modelo_id,
                revision=name,
                kind="name_misstates_closing",
                detail=f"name claims through {claimed_close}; declared window closes {closing}",
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


def _bundled_modelo_ids() -> tuple[str, ...]:
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = bundled_authority()
    findings = screen_authority(authority, _bundled_modelo_ids())
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
