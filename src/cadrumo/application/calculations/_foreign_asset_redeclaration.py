"""Foreign-asset re-declaration advisory helpers for Modelo 720 and 721.

Every projection here reads a persisted :class:`CalculationRevision` against the
registry's :class:`ModeloRevision` for the same filing context, and emits its
result as :class:`CasillaObservation` rows so the advisory carries the same
per-casilla grounding the rest of the calculation chain does.

See Also:
    :mod:`~application._foreign_asset_thresholds`
        Resolves the per-bloque declaration floors and re-declaration deltas
        from the effective registry revision.
    :class:`~domain.calculations.registry.RegistryModeloObservation`
        Registry-grounded observation envelope accepted as prior, current, and
        current-declaration evidence.
    :mod:`~application.calculations.tests.test_modelo_720_prior_year_baseline_fidelity`
        Exercises the Modelo 720 prior-year baseline advisory path with real
        observations and enrollment evidence.
    :mod:`~application.calculations.tests.test_modelo_721_cripto_extranjero_fidelity`
        Exercises the Modelo 721 token baseline sibling through the same
        advisory mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from ...core.foreign_asset_obligation import (
    ForeignAssetObligationGroup,
    MODELO_720_FOREIGN_ASSET_CLASS_CODES,
    foreign_asset_obligation_group,
)
from ...core.modelo import Modelo
from ...core.casilla_id import CasillaId
from ...core.aggregation import BindingSourceKind
from ...core.aggregation import ForeignAssetClass
from ...domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_binding_source_casilla_ids
from ...domain.calculations.registry.detail_record_bindings import foreign_asset_binding_row_field
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ...domain.modelos.calculation_revision import CalculationRevision
from .._foreign_asset_thresholds import foreign_asset_declaration_thresholds

_M720_VALUATION_CASILLA_GROUPS: Mapping[CasillaId, ForeignAssetObligationGroup] = {
    "cuentas.valoracion": ForeignAssetObligationGroup.CUENTAS,
    "valores.valoracion": ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS,
    "inmuebles.valoracion": ForeignAssetObligationGroup.INMUEBLES,
}
_M720_GROUP_VALUATION_CASILLAS: Mapping[ForeignAssetObligationGroup, CasillaId] = {
    group: casilla_id for casilla_id, group in _M720_VALUATION_CASILLA_GROUPS.items()
}
_M720_ASSET_CLASS_BY_CODE: Mapping[str, ForeignAssetClass] = {
    code: asset_class for asset_class, code in MODELO_720_FOREIGN_ASSET_CLASS_CODES.items()
}
#: ``row_field`` selectors of the two foreign-asset row bindings the evidence
#: projection joins. Named rather than inlined so the join is greppable; the
#: binding IDs themselves are never hardcoded — they are discovered from the
#: revision by these row fields.
_ASSET_CLASS_ROW_FIELD = "asset_class_code"
_VALUATION_ROW_FIELD = "valuation_amount"

_M721_CUSTODIAN_NAME_CASILLA: CasillaId = "custodio.nombre-razon-social"
_M721_CUSTODIAN_COUNTRY_CASILLA: CasillaId = "custodio.codigo-pais"
_M721_CRYPTO_ASSET_CASILLA: CasillaId = "moneda.clave-token"
_M721_BALANCE_CASILLA: CasillaId = "moneda.saldo-31-diciembre"


@dataclass(frozen=True, slots=True)
class _RedeclarationPosition:
    key: tuple[str, ...]
    group: ForeignAssetObligationGroup
    value_eur: Decimal


def modelo_720_redeclaration_advisory_findings(
    *,
    prior_observation: RegistryModeloObservation,
    current_observation: RegistryModeloObservation,
    current_declaration_observation: RegistryModeloObservation | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return non-blocking M720 re-declaration advisories for omitted grown groups.

    ``current_observation`` is the operator's current-year valuation evidence;
    ``current_declaration_observation`` is the current filed/declarable row set.
    When omitted, the current evidence is also treated as the current declaration,
    so a correctly present row produces no advisory.

    See Also:
        :func:`~application._foreign_asset_thresholds.foreign_asset_declaration_thresholds`
            Supplies the strict per-obligation-block re-declaration delta.
    """
    return _redeclaration_advisory_findings(
        modelo=Modelo.M720.value,
        prior_positions=_modelo_720_positions(prior_observation),
        current_positions=_modelo_720_positions(current_observation),
        declared_positions=_modelo_720_positions(current_declaration_observation or current_observation),
        filing_year=current_observation.filing_year,
    )


def modelo_721_redeclaration_advisory_findings(
    *,
    prior_observation: RegistryModeloObservation,
    current_observation: RegistryModeloObservation,
    current_declaration_observation: RegistryModeloObservation | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return non-blocking M721 re-declaration advisories for omitted grown tokens.

    See Also:
        :class:`~core.foreign_asset_obligation.ForeignAssetObligationGroup`
            Provides the ``MONEDAS_VIRTUALES`` group used for the Modelo 721
            re-declaration threshold.
    """
    return _redeclaration_advisory_findings(
        modelo=Modelo.M721.value,
        prior_positions=_modelo_721_positions(prior_observation),
        current_positions=_modelo_721_positions(current_observation),
        declared_positions=_modelo_721_positions(current_declaration_observation or current_observation),
        filing_year=current_observation.filing_year,
    )


def _redeclaration_advisory_findings(
    *,
    modelo: str,
    prior_positions: Mapping[tuple[str, ...], _RedeclarationPosition],
    current_positions: Mapping[tuple[str, ...], _RedeclarationPosition],
    declared_positions: Mapping[tuple[str, ...], _RedeclarationPosition],
    filing_year: int,
) -> tuple[ModeloVerificationFinding, ...]:
    thresholds = foreign_asset_declaration_thresholds(modelo=modelo, filing_year=filing_year)
    findings: list[ModeloVerificationFinding] = []
    for key in sorted(prior_positions):
        prior = prior_positions[key]
        current = current_positions.get(key)
        if current is None or key in declared_positions:
            continue

        threshold = thresholds[prior.group]
        delta_eur = current.value_eur - prior.value_eur
        if delta_eur <= threshold.redeclaration_increase_delta_eur:
            continue

        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message_locale_key="application.modelo.findings.foreign_asset_redeclaration",
                message_facts={
                    "modelo_code": modelo,
                    "filing_year": filing_year,
                    "position_key": _position_key_code(current.key),
                    "group_code": current.group.value,
                    "prior_value_eur": prior.value_eur,
                    "current_value_eur": current.value_eur,
                    "delta_value_eur": delta_eur,
                    "redeclaration_increase_threshold_eur": threshold.redeclaration_increase_delta_eur,
                },
                legal_refs=threshold.legal_refs,
                source_refs=threshold.source_refs,
            )
        )
    return tuple(findings)


def _modelo_720_positions(observation: RegistryModeloObservation) -> Mapping[tuple[str, ...], _RedeclarationPosition]:
    totals: dict[ForeignAssetObligationGroup, Decimal] = {}
    for item in observation.observations:
        group = _M720_VALUATION_CASILLA_GROUPS.get(item.casilla_id)
        if group is None:
            continue
        if not isinstance(item.value, Decimal):
            continue
        totals[group] = totals.get(group, Decimal("0")) + item.value

    return {
        (group.value,): _RedeclarationPosition(
            key=(group.value,),
            group=group,
            value_eur=value,
        )
        for group, value in totals.items()
    }


def _modelo_721_positions(observation: RegistryModeloObservation) -> Mapping[tuple[str, ...], _RedeclarationPosition]:
    positions: dict[tuple[str, ...], _RedeclarationPosition] = {}
    custodian_name = ""
    custodian_country = ""
    token = ""
    for item in observation.observations:
        if item.casilla_id == _M721_CUSTODIAN_NAME_CASILLA:
            custodian_name = _decimal_text(item.value) if isinstance(item.value, Decimal) else item.value
        elif item.casilla_id == _M721_CUSTODIAN_COUNTRY_CASILLA:
            custodian_country = _decimal_text(item.value) if isinstance(item.value, Decimal) else item.value
        elif item.casilla_id == _M721_CRYPTO_ASSET_CASILLA:
            token = _decimal_text(item.value) if isinstance(item.value, Decimal) else item.value
        elif item.casilla_id == _M721_BALANCE_CASILLA and token:
            if not isinstance(item.value, Decimal):
                continue
            key = (
                ForeignAssetObligationGroup.MONEDAS_VIRTUALES.value,
                custodian_name,
                custodian_country,
                token,
            )
            existing = positions.get(key)
            value_eur = item.value if existing is None else existing.value_eur + item.value
            positions[key] = _RedeclarationPosition(
                key=key,
                group=ForeignAssetObligationGroup.MONEDAS_VIRTUALES,
                value_eur=value_eur,
            )
            token = ""
    return positions


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _position_key_code(key: tuple[str, ...]) -> str:
    """Encode the complete source-position identity as a locale-neutral token."""
    return "|".join(quote(part, safe="") for part in key)


def modelo_720_declared_observation(
    *,
    revision: CalculationRevision,
    modelo_revision: ModeloRevision,
    filing_year: int,
    period: str,
) -> RegistryModeloObservation:
    """Project what the operator actually DECLARED on a Modelo 720 draft.

    The declared set is read from
    :attr:`~CalculationRevision.input_values_by_casilla_id` —
    the operator-supplied inputs — and deliberately NOT from
    ``casilla_values``. The engine materialises every declared casilla in
    ``casilla_values``, emitting ``0`` for a valuation the operator never
    supplied; a declared set derived from that mapping would therefore always
    contain all three obligation blocks, and the omitted-position test in
    :func:`modelo_720_redeclaration_advisory_findings` could never be
    satisfied. An operator-entered zero remains a genuine declaration and is
    kept.

    Returns a :class:`RegistryModeloObservation` carrying only the valuation
    casillas present in the operator's input set.

    Args:
        revision: The persisted :class:`CalculationRevision` whose operator
            inputs are read as the declaration.
        modelo_revision: The :class:`ModeloRevision` supplying each valuation
            casilla's legal and source grounding.
        filing_year: Devengo year the observation is stamped with.
        period: Registry period token the observation is stamped with.

    See Also:
        :func:`modelo_720_evidence_observation`
            The independent valuation counterpart this declaration is tested
            against.
    """
    refs_by_casilla = {casilla.id: (casilla.legal_refs, casilla.source_refs) for casilla in modelo_revision.casillas}
    observations: list[CasillaObservation] = []
    for casilla_id in _M720_VALUATION_CASILLA_GROUPS:
        raw = revision.input_values_by_casilla_id.get(casilla_id)
        refs = refs_by_casilla.get(casilla_id)
        if raw is None or refs is None:
            continue
        value = _decimal_or_none(raw)
        if value is None:
            continue
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=refs[0],
                source_refs=refs[1],
            ),
        )
    return RegistryModeloObservation(
        modelo=Modelo.M720.value,
        filing_year=filing_year,
        period=period,
        observations=tuple(observations),
    )


def modelo_720_evidence_observation(
    *,
    revision: CalculationRevision,
    modelo_revision: ModeloRevision,
    filing_year: int,
    period: str,
) -> RegistryModeloObservation:
    """Project the per-asset-row valuation EVIDENCE on a Modelo 720 draft.

    Joins the revision's persisted ``row_binding_values`` for the two
    ``foreign_asset`` row bindings that carry the asset class clave and the
    row valuation, resolves each clave to its RGAT obligation bloque, and sums
    the rows per bloque onto that bloque's valuation casilla.

    This is independent of what the operator typed into the declaration: the
    rows come from the foreign-asset source mesh, the declaration comes from
    the operator's manual inputs. That independence is what makes the omitted
    position detectable at all.

    The two binding ids are discovered from ``modelo_revision`` by their
    selector ``row_field`` rather than hardcoded, so a registry rename does not
    silently empty the evidence side.

    Returns an empty observation when the revision carries no asset rows.

    Args:
        revision: The persisted :class:`CalculationRevision` whose
            ``row_binding_values`` carry the per-asset rows.
        modelo_revision: The :class:`ModeloRevision` the two ``foreign_asset``
            row bindings are discovered from by selector.
        filing_year: Devengo year the observation is stamped with.
        period: Registry period token the observation is stamped with.
    """
    class_binding = _foreign_asset_row_binding_id(modelo_revision, row_field=_ASSET_CLASS_ROW_FIELD)
    valuation_binding = _foreign_asset_row_binding_id(modelo_revision, row_field=_VALUATION_ROW_FIELD)
    totals: dict[ForeignAssetObligationGroup, Decimal] = {}
    if class_binding is not None and valuation_binding is not None:
        class_rows = revision.row_binding_values.get(class_binding, {})
        valuation_rows = revision.row_binding_values.get(valuation_binding, {})
        for row_index, raw_code in class_rows.items():
            asset_class = _M720_ASSET_CLASS_BY_CODE.get(raw_code.strip().upper())
            raw_valuation = valuation_rows.get(row_index)
            if asset_class is None or raw_valuation is None:
                continue
            value = _decimal_or_none(raw_valuation)
            if value is None:
                continue
            group = foreign_asset_obligation_group(asset_class)
            totals[group] = totals.get(group, Decimal("0")) + value

    refs_by_casilla = {casilla.id: (casilla.legal_refs, casilla.source_refs) for casilla in modelo_revision.casillas}
    observations: list[CasillaObservation] = []
    for group, total in totals.items():
        casilla_id = _M720_GROUP_VALUATION_CASILLAS.get(group)
        refs = refs_by_casilla.get(casilla_id) if casilla_id is not None else None
        if casilla_id is None or refs is None:
            continue
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=total,
                legal_refs=refs[0],
                source_refs=refs[1],
            ),
        )
    return RegistryModeloObservation(
        modelo=Modelo.M720.value,
        filing_year=filing_year,
        period=period,
        observations=tuple(observations),
    )


def modelo_720_prior_baseline_observation(
    *,
    binding_values: Mapping[str, Decimal],
    modelo_revision: ModeloRevision,
    filing_year: int,
    period: str,
) -> RegistryModeloObservation:
    """Project the prior-year declared baseline resolved by the previous-filing carry.

    ``binding_values`` is the resolved mapping produced by
    :func:`~._binding_prefill.resolve_bindings_from_local_store`, which has
    already re-confirmed each carried observation's stamped revision against
    the law-determined revision for its source context. Only the
    ``previous_filing`` bindings whose selector names a Modelo 720 valuation
    casilla are projected; every other resolved binding is ignored.

    Returns an empty observation when no prior baseline resolved, which leaves
    the re-declaration advisory silent rather than comparing against a
    fabricated zero baseline.

    Args:
        binding_values: Resolved ``previous_filing`` binding values, already
            revision-confirmed against their source context.
        modelo_revision: The :class:`ModeloRevision` supplying each projected
            casilla's legal and source grounding.
        filing_year: Devengo year the observation is stamped with.
        period: Registry period token the observation is stamped with.
    """
    refs_by_casilla = {casilla.id: (casilla.legal_refs, casilla.source_refs) for casilla in modelo_revision.casillas}
    observations: list[CasillaObservation] = []
    for binding in modelo_revision.bindings:
        if binding.source != BindingSourceKind.PREVIOUS_FILING:
            continue
        value = binding_values.get(binding.id)
        if value is None:
            continue
        source_casilla_ids = previous_filing_binding_source_casilla_ids(binding)
        # binding_values resolves ONE value per binding id, so this observation
        # only applies when the binding targets exactly one casilla -- a
        # multi-casilla (plural source_casilla_ids) binding has no single value
        # to attribute to which of its several targets, and is out of scope
        # here, same as before this typed read replaced the raw singular-key
        # lookup (which only ever matched the singular shape in the first
        # place).
        if len(source_casilla_ids) != 1:
            continue
        (source_casilla_id,) = source_casilla_ids
        if source_casilla_id not in _M720_VALUATION_CASILLA_GROUPS:
            continue
        refs = refs_by_casilla.get(source_casilla_id)
        if refs is None:
            continue
        observations.append(
            CasillaObservation(
                casilla_id=source_casilla_id,
                value=value,
                legal_refs=refs[0],
                source_refs=refs[1],
            ),
        )
    return RegistryModeloObservation(
        modelo=Modelo.M720.value,
        filing_year=filing_year,
        period=period,
        observations=tuple(observations),
    )


def _foreign_asset_row_binding_id(revision: ModeloRevision, *, row_field: str) -> str | None:
    for binding in revision.bindings:
        if foreign_asset_binding_row_field(binding) == row_field:
            return binding.id
    return None


def _decimal_or_none(raw: object) -> Decimal | None:
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None


__all__ = [
    "modelo_720_declared_observation",
    "modelo_720_evidence_observation",
    "modelo_720_prior_baseline_observation",
    "modelo_720_redeclaration_advisory_findings",
    "modelo_721_redeclaration_advisory_findings",
]
