"""Localized, passive guidance for unavailable runtime consumers."""

from ...core.i18n.render import tr
from ...core.product_identity import PRODUCT_IDENTITY
from ..runtime.contracts import RuntimeRefusalCode


def runtime_unavailable_remedy(code: str | None) -> str | None:
    """Name the manager without requesting lifecycle work or changing refusal codes."""
    if code != RuntimeRefusalCode.UNAVAILABLE.value:
        return None
    return tr("common.runtime.manager_unavailable_remedy", product=PRODUCT_IDENTITY.prose_name)
