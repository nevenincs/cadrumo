"""Typed ``--json`` payload schemas for censo config CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every censo command surface this module covers.

Field sets match the production payload dicts constructed in
``_profile_censo.py`` at their emit sites.

The backing service is :class:`~aeat.application.user_profile.CensoSyncService`;
this module documents only the CLI transport shapes for censo snapshot capture,
review, comparison, and apply.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._schemas import OutputSchema, register_schema

if TYPE_CHECKING:
    from ....application.user_profile import CensoApplyResult as _AppCensoApplyResult


@register_schema("config.profile.censo.pull")
class CensoRefreshResult(OutputSchema):
    """JSON envelope for ``aeat config profile censo pull``.

    Mirrors the active :class:`~aeat.application.live._censo.CensoSnapshot`
    captured from AEAT G313 by the censo service. ``facts`` is the flat
    dotted-path censo map used later by compare/apply; the encrypted snapshot
    payload itself remains in secure storage.
    """

    snapshot_id: str
    profile_id: str
    captured_at: str
    facts: dict[str, object] = {}


@register_schema("config.profile.censo.show")
class CensoShowResult(OutputSchema):
    """JSON envelope for ``aeat config profile censo show``.

    Projects the selected :class:`~aeat.application.live._censo.CensoSnapshot`,
    including lifecycle ``state`` and ``source_url``, so an operator can inspect
    the AEAT-side facts before comparing or applying them to the local profile.
    """

    snapshot_id: str
    profile_id: str
    captured_at: str
    source_url: str
    state: str
    facts: dict[str, object] = {}


@register_schema("config.profile.censo.compare")
class CensoCompareResult(OutputSchema):
    """JSON envelope for ``aeat config profile censo compare``.

    Wraps :class:`~aeat.application.user_profile.CensoProfileComparison`.
    ``rows`` contains every :class:`~aeat.application.user_profile.CensoFieldComparison`
    row, while ``diverging``, ``censo_only``, and ``profile_only`` are grouped
    projections populated by the CLI from the application comparison
    properties.
    """

    snapshot_id: str | None = None
    diverging: list[dict[str, object]] = []
    censo_only: list[dict[str, object]] = []
    profile_only: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor; mypy
    # assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("config.profile.censo.apply")
class CensoApplyPayload(OutputSchema):
    """JSON envelope for ``aeat config profile censo apply``.

    Distinct from the application
    :class:`~aeat.application.user_profile.CensoApplyResult` (DB-26 S52): this
    envelope projects that result's JSON-coerced fields and (via
    ``extra=allow``) forwards any provider-specific extras without
    re-declaring them. The calendar fields are a CLI-side summary of the
    resulting :class:`~aeat.application.overview.OverviewCalendar` after censo
    facts have updated the profile, so operators can see which obligations are
    now computable. Derive instances via :meth:`from_result`.
    """

    snapshot_id: str
    written_paths: list[str] = []
    unchanged_paths: list[str] = []
    derived_paths: list[str] = []
    taxpayer_model_declared: bool | None = None
    calendar_range_from: str | None = None
    calendar_range_to: str | None = None
    calendar_obligation_count: int = 0
    calendar_obligation_modelos: list[str] = []
    calendar_enrolment_source_paths: list[str] = []
    calendar_warning_codes: list[str] = []
    calendar_defaulted_modelos: list[str] = []
    calendar_obligation_rows: list[dict[str, object]] = []
    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor; mypy
    # assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]

    @classmethod
    def from_result(cls, result: _AppCensoApplyResult) -> CensoApplyPayload:
        """Project the application :class:`~aeat.application.user_profile.CensoApplyResult`.

        ``model_dump(mode="json")`` performs the typed-field coercion; ``extra=allow``
        forwards any additional fields the application result carries.

        Returns:
            The projected :class:`CensoApplyPayload` instance.
        """
        return cls.model_validate(result.model_dump(mode="json"))
