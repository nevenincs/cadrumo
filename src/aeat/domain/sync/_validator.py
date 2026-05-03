"""Wire payload validator wrapping pydantic JSON validation.

Wraps :meth:`pydantic.BaseModel.model_validate_json` so every validation
failure at the AEAT boundary becomes a :class:`WireValidationError`
(a subclass of :class:`aeat.core.errors.AeatError`).
"""

from __future__ import annotations

from pydantic import ValidationError

from ...core.logging import get_logger
from ._errors import WireValidationError
from ._wire import WirePayloadBase

_logger = get_logger(__name__)


class WireValidator:
    """Strict JSON-to-pydantic validator for AEAT wire payloads."""

    def validate[T: WirePayloadBase](
        self,
        raw: bytes | str,
        schema: type[T],
    ) -> T:
        """Parse ``raw`` into ``schema`` or raise :class:`WireValidationError`.

        Args:
            raw: The raw JSON payload bytes or str as received from the
                browser session.
            schema: The concrete :class:`WirePayloadBase` subclass the
                payload must conform to.

        Returns:
            A validated, frozen instance of ``schema``.

        Raises:
            WireValidationError: If the payload cannot be coerced.
        """
        try:
            return schema.model_validate_json(raw)
        except ValidationError as exc:
            _logger.warning(
                "wire payload failed validation against %s",
                schema.__name__,
                exc_info=True,
            )
            raise WireValidationError(
                f"Wire payload failed strict validation against {schema.__name__}: {exc}"
            ) from exc
