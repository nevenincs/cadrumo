"""Row models admitted by the modelo CLI detail-row ingress."""

from pydantic import BaseModel

from ...domain.modelos.row_models import (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
)

# Routing only: each model owns its row_type and validation contract.
SUPPORTED_DETAIL_ROW_MODELS: tuple[type[BaseModel], ...] = (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
)
