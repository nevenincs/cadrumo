"""Registry-resolved LIVA art-103.Dos.2 mandatory-especial margin.

Art. 103.Dos.2 makes the prorrata especial regime compulsory once the deduction
computed under the general regime exceeds the one under the especial regime by a
statutory margin. Both halves of that test are law: the margin ITSELF, and
whether landing exactly on it is enough.

The provision has had two redactions and they differ on both. The original (in
force to 31-12-2014) required the excess to be "en un 20 por 100", with no
"o más" and so exclusive. Ley 28/2014 art. 1.26 (in force from 01-01-2015)
replaced it with "en un 10 por ciento o más" -- lowering the margin AND making
it inclusive. A margin without its comparison direction is therefore only half
the rule, which is why both travel together here.

Only the current redaction is declared in the registry. No modelo 303 revision
covers a pre-2015 filing year, and the bundled consolidated corpus carries only
the text in force, so the repealed redaction has no citable authority in this
tree. :func:`resolve_prorrata_especial_mandatory_parameters` therefore refuses a
pre-2015 ejercicio by name rather than resolving it from an ungrounded figure.

See Also:
    :mod:`domain.iva.prorrata`
        The predicate and advisory that consume the resolved margin.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError as _CadrumoError
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ..calculations.registry.formula_runtime_ops import resolve_dated_value
from ..calculations.registry.schema import ModeloRevision
from ..calculations.registry.schema_base import ThresholdComparison

#: The registry parameter carrying the art-103.Dos.2 margin.
PRORRATA_ESPECIAL_MANDATORY_PARAMETER_ID = "m303-prorrata-especial-obligatoria-margen-porcentaje"

#: First filing year the declared redaction governs (Ley 28/2014 art. 1.26).
PRORRATA_ESPECIAL_MANDATORY_DECLARED_FIRST_YEAR = 2015


class ProrrataEspecialMandatoryParameterError(_CadrumoError):
    """Raised when the art-103.Dos.2 margin cannot be grounded for an ejercicio."""


class ProrrataEspecialMandatoryParameters(BaseModel):
    """The art-103.Dos.2 margin and its comparison direction, resolved.

    Attributes:
        margin_percentage: The percentage the provision names.
        comparison: Whether the margin must be exceeded strictly or merely
            reached. Registry data, because the two redactions differ on it.
        modelo_id: Modelo whose revision hosts the parameter.
        revision_id: The hosting revision's canonical id.
        resolved_on: The filing-period date the value was selected for.
    """

    model_config = _STRICT_FROZEN_CONFIG

    margin_percentage: Decimal = Field(gt=Decimal("0"))
    comparison: ThresholdComparison
    modelo_id: str = Field(min_length=1, max_length=16)
    revision_id: str = Field(min_length=1, max_length=64)
    resolved_on: date

    @property
    def multiple(self) -> Decimal:
        """The factor the especial-regime deduction is scaled by for the threshold."""
        return Decimal("1") + self.margin_percentage / Decimal("100")

    @property
    def inclusive(self) -> bool:
        """Whether a deduction landing exactly on the threshold already qualifies."""
        return self.comparison is ThresholdComparison.INCLUSIVE


def resolve_prorrata_especial_mandatory_parameters(
    revision: ModeloRevision,
    *,
    modelo_id: str,
    ejercicio: int,
) -> ProrrataEspecialMandatoryParameters:
    """Resolve the art-103.Dos.2 margin for one ejercicio from a compiled revision.

    Args:
        revision: The compiled revision the application layer selected.
        modelo_id: Modelo the revision belongs to.
        ejercicio: The filing year whose margin is wanted.

    Returns:
        The resolved :class:`ProrrataEspecialMandatoryParameters`.

    Raises:
        ProrrataEspecialMandatoryParameterError: For an ejercicio before the
            declared redaction, or when the revision does not declare the
            parameter or cannot resolve it for that ejercicio.
    """
    if ejercicio < PRORRATA_ESPECIAL_MANDATORY_DECLARED_FIRST_YEAR:
        raise ProrrataEspecialMandatoryParameterError(
            f"ejercicio {ejercicio} predates the only redaction of LIVA art. 103.Dos.2 this "
            f"registry declares (in force from {PRORRATA_ESPECIAL_MANDATORY_DECLARED_FIRST_YEAR}). "
            f"No revision covers a pre-{PRORRATA_ESPECIAL_MANDATORY_DECLARED_FIRST_YEAR} filing "
            "year and the repealed redaction has no citable authority here, so the mandatory "
            "prorrata especial margin cannot be grounded for it.",
        )

    declared = next(
        (p for p in revision.parameters if p.id == PRORRATA_ESPECIAL_MANDATORY_PARAMETER_ID),
        None,
    )
    if declared is None:
        raise ProrrataEspecialMandatoryParameterError(
            f"modelo {modelo_id} revision {revision.id} declares no "
            f"{PRORRATA_ESPECIAL_MANDATORY_PARAMETER_ID}; the LIVA art. 103.Dos.2 margin has no "
            "grounded source for this filing context",
        )

    date_context: Mapping[str, date] = {"filing_period": date(ejercicio, 12, 31)}
    try:
        value = resolve_dated_value(declared, date_context)
    except Exception as exc:
        raise ProrrataEspecialMandatoryParameterError(
            f"modelo {modelo_id} revision {revision.id} parameter "
            f"{PRORRATA_ESPECIAL_MANDATORY_PARAMETER_ID} does not resolve for ejercicio "
            f"{ejercicio}: {exc}",
        ) from exc

    return ProrrataEspecialMandatoryParameters(
        margin_percentage=Decimal(value.value),
        comparison=value.comparison,
        modelo_id=modelo_id,
        revision_id=revision.id,
        resolved_on=date_context["filing_period"],
    )
