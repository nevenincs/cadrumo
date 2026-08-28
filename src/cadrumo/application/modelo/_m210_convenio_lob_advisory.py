"""Convenio doble imposición limitation-of-benefits advisory for M210 verification.

A bilateral double-taxation treaty (CDI) rate override is only available to a
filer who actually satisfies the treaty's residence and beneficial-ownership
conditions; several CDIs bundled in this project's corpus (see e.g. the
Spain-Germany art. 11 exemption, ``convenio-es-de-2011:art-11``, which
conditions source-state exemption on the recipient being the "beneficiario
efectivo" of the interest) restrict the benefit to a genuine beneficial owner,
and the wider OECD Model Convention limitation-of-benefits (LOB) concept
further restricts treaty relief for entities lacking economic substance in
their state of residence. The engine has no way to verify beneficial ownership
or substance from a filer-supplied ``country_of_fiscal_residence`` alone, so
whenever a Convenio override is actually applied to a Modelo 210 rate this
module surfaces a non-blocking :class:`ModeloVerificationFinding` telling the
operator to confirm LOB eligibility against the specific treaty text — never
silently trusting the residence declaration (``no-silent-under-declaration``).

The advisory is derived from the :class:`~domain.calculations.registry.RegistrySnapshot`
carrying the cross-cutting :class:`~domain.calculations.registry.ConvenioAuthority`
projection and the filer's :class:`~domain.deadlines.TaxpayerProfile`
``country_of_fiscal_residence``.

See Also:
    :func:`~application.modelo._m210_rate.resolve_m210_rate`
        Application-layer replay of the same tipo-de-gravamen resolution path;
        this advisory reads the same :class:`~domain.calculations.registry.ConvenioAuthority`
        projection to detect whether an override actually matched.
    :func:`~application.modelo._verification_actions._collect_revision_verification_findings`
        Verification collector that appends this advisory beside the DT 12ª /
        art. 20 / art. 52 advisories using the same non-blocking mechanism.
    :class:`~domain.calculations.registry.ConvenioAuthority`
        Cross-cutting treaty-override authority whose ``resolve`` lookup this
        advisory consults to detect a matched treaty row.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core import CasillaId, TipoRentaIrnr
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.errors import ModeloError
from ._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_semantic_role,
)

_IRNR_TIPO_RENTA_ROLE = "irnr_tipo_renta"


def _m210_convenio_lob_advisory_finding(
    snapshot: RegistrySnapshot,
    profile: TaxpayerProfile,
    input_values_by_casilla_id: Mapping[CasillaId, str],
) -> ModeloVerificationFinding | None:
    """Warn to confirm treaty LOB eligibility when a Convenio override applies.

    Fires only when the profile declares a ``country_of_fiscal_residence`` AND
    the cross-cutting :class:`~domain.calculations.registry.ConvenioAuthority`
    actually resolves a treaty override row for ``(country, tipo_renta)`` — i.e.
    only when treaty-based relief is genuinely being claimed, never for a filer
    on the plain TRLIRNR domestic baseline. The finding is ADVISORY because
    beneficial-ownership and limitation-of-benefits eligibility depend on facts
    (economic substance, ownership chain) this engine cannot verify from the
    profile alone; a legitimately-eligible treaty claim must remain permissible
    (``no-silent-under-declaration``). Grounded generically in the OECD Model
    Convention limitation-of-benefits framework plus the matched treaty's own
    beneficial-ownership article when the row carries one.
    """
    country = profile.country_of_fiscal_residence
    if not country:
        return None

    try:
        tipo_renta_id = casilla_id_for_unique_semantic_role(snapshot, _IRNR_TIPO_RENTA_ROLE)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if tipo_renta_id is None:
        return None

    tipo_renta_raw = input_values_by_casilla_id.get(tipo_renta_id, "")
    try:
        tipo_renta = TipoRentaIrnr(tipo_renta_raw)
    except ValueError:
        return None

    override = snapshot.convenio.resolve(country.upper(), tipo_renta, snapshot.filing_year)
    if override is None:
        return None

    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=tipo_renta_id,
        message_locale_key="application.modelo.findings.m210_convenio_lob_advisory",
        message_facts={
            "country_code": override.country_code,
            "document_id": override.document_id,
            "tipo_renta_code": tipo_renta.value,
        },
        legal_refs=override.legal_refs,
    )


__all__ = ["_m210_convenio_lob_advisory_finding"]
