"""The self-verifying custody record: one digest over its own payload.

Several custody records carry a ``self_digest`` field holding the canonical
digest of everything else in the record, so loading one re-derives the digest
and refuses a payload that has been altered underneath it. The shape is always
the same and differs only in a size budget and a subject string used in
refusals.

That shape was written out by hand in five classes across four modules. A base
factoring it already existed, but it lived in ``label_head_models``, which
imports from ``capsule_records`` -- so the two capsule records could not have
subclassed it without closing an import cycle. It lives here instead, in a
module that imports nothing from its siblings, which is what lets every custody
record reach it.

The chained-digest variant is deliberately NOT covered. A record that digests
a content digest and then digests a payload INCLUDING that digest is a wider
shape than one digest over one payload, and collapsing the two would mean this
base silently accepting a record whose inner digest nobody checked.
"""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar, cast

from pydantic import BaseModel, ValidationError

from .....core.hashing import bounded_canonical_json_bytes, canonical_json_digest
from .....core.models import STRICT_FROZEN_CONFIG
from .errors import ProfileCustodyRecordError

_ModelT = TypeVar("_ModelT", bound="CustodyDigestModel")


def payload_without_self_digest(model: BaseModel) -> dict[str, object]:
    """The digest payload: everything the record carries except the digest itself."""
    payload = cast(dict[str, object], model.model_dump(mode="json"))
    payload.pop("self_digest", None)
    return payload


class CustodyDigestModel(BaseModel):
    """Shared canonical digest and JSON behavior for self-verifying custody records."""

    model_config = STRICT_FROZEN_CONFIG
    _digest_maximum_bytes: ClassVar[int]
    _digest_subject: ClassVar[str]

    @property
    def canonical_payload(self) -> dict[str, object]:
        """Return the exact digest payload, excluding only ``self_digest``."""
        return payload_without_self_digest(self)

    @property
    def computed_self_digest(self) -> str:
        """Re-derive the digest this record claims, from what it actually holds."""
        return canonical_json_digest(
            self.canonical_payload,
            maximum_bytes=self._digest_maximum_bytes,
            subject=self._digest_subject,
        )

    def canonical_json_bytes(self) -> bytes:
        """Serialise the complete record in its unique canonical JSON form."""
        return bounded_canonical_json_bytes(
            cast(dict[str, object], self.model_dump(mode="json")),
            maximum_bytes=self._digest_maximum_bytes,
            subject=self._digest_subject,
        )

    @classmethod
    # values is splatted into pydantic's model_construct(**values: Any),
    # whose own signature has a same-named parameter (_fields_set): a
    # KWARGS-ANY-RATIONALE-MODEL-CONSTRUCT-SPLAT: narrower value type makes
    # every checker treat the splat as a possible match against it.
    def _create_with_self_digest(cls: type[_ModelT], values: dict[str, Any], error_message: str) -> _ModelT:
        try:
            payload = cls.model_construct(**values, self_digest="").model_dump(mode="json")
            payload["self_digest"] = canonical_json_digest(
                cast(dict[str, object], {key: value for key, value in payload.items() if key != "self_digest"}),
                maximum_bytes=cls._digest_maximum_bytes,
                subject=cls._digest_subject,
            )
            return cls.model_validate_json(
                bounded_canonical_json_bytes(
                    cast(dict[str, object], payload),
                    maximum_bytes=cls._digest_maximum_bytes,
                    subject=cls._digest_subject,
                )
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError(error_message) from exc


__all__ = ["CustodyDigestModel", "payload_without_self_digest"]
