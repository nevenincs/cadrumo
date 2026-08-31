"""Canonical label-head records and their crash-recovery witness."""

from __future__ import annotations

from typing import Any, ClassVar, Literal, TypeVar, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .....core import STRICT_FROZEN_CONFIG
from .....core.hashing import bounded_canonical_json_bytes, canonical_json_digest
from .....core.identity import PrefixedContentDigest
from .capsule_records import ProfileCustodyCapsuleLabel
from .errors import ProfileCustodyRecordError

LABEL_HEAD_MAX_BYTES = 4 * 1024
"""Bounded durable head and pending-advance records share one strict budget."""

_ModelT = TypeVar("_ModelT", bound="_CustodyDigestModel")


def _payload_without_self_digest(model: BaseModel) -> dict[str, object]:
    payload = cast(dict[str, object], model.model_dump(mode="json"))
    payload.pop("self_digest", None)
    return payload


class _CustodyDigestModel(BaseModel):
    """Shared canonical digest and JSON behavior for custody head records."""

    model_config = STRICT_FROZEN_CONFIG
    _digest_maximum_bytes: ClassVar[int]
    _digest_subject: ClassVar[str]

    @property
    def computed_self_digest(self) -> str:
        return canonical_json_digest(
            _payload_without_self_digest(self),
            maximum_bytes=self._digest_maximum_bytes,
            subject=self._digest_subject,
        )

    def canonical_json_bytes(self) -> bytes:
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


class ProfileLabelHead(_CustodyDigestModel):
    """Trusted current label witness, separate from the immutable commit marker."""

    _digest_maximum_bytes = LABEL_HEAD_MAX_BYTES
    _digest_subject = "profile label head"

    schema_version: Literal[1] = 1
    profile_id: UUID
    label_revision: int = Field(ge=1)
    label_content_digest: PrefixedContentDigest
    label_self_digest: str
    source_witness: str
    previous_head_digest: str | None = None
    self_digest: str = Field(min_length=71, max_length=71)

    @field_validator(
        "label_content_digest",
        "label_self_digest",
        "source_witness",
        "previous_head_digest",
    )
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if (
            len(value) != 71
            or not value.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value[7:])
        ):
            raise ValueError("profile label head digest must be a lowercase sha256 digest")
        return value

    @model_validator(mode="after")
    def _validate_head(self) -> ProfileLabelHead:
        if self.label_revision == 1 and self.previous_head_digest is not None:
            raise ValueError("first label head must not carry a predecessor")
        if self.label_revision > 1 and self.previous_head_digest is None:
            raise ValueError("later label head must carry its predecessor")
        if self.self_digest != self.computed_self_digest:
            raise ValueError("profile label head self digest does not match")
        return self

    @classmethod
    def create_initial(
        cls,
        *,
        label: ProfileCustodyCapsuleLabel,
        source_witness: str,
    ) -> ProfileLabelHead:
        """Start a label-head chain from the label's own first revision.

        Refuses any label that is not itself revision 1 with no predecessor —
        the chain's root must anchor to a label the label-record layer already
        proved is first, never to an arbitrary starting point a caller
        supplies.
        """
        if label.label_revision != 1 or label.previous_label_digest is not None:
            raise ProfileCustodyRecordError("initial label head requires the first label record")
        return cls._create_with_self_digest(
            {
                "profile_id": label.profile_id,
                "label_revision": label.label_revision,
                "label_content_digest": label.content_digest,
                "label_self_digest": label.self_digest,
                "source_witness": source_witness,
                "previous_head_digest": None,
            },
            "cannot construct initial profile label head",
        )

    @classmethod
    def advance(cls, *, current: ProfileLabelHead, label: ProfileCustodyCapsuleLabel) -> ProfileLabelHead:
        """Extend the trusted chain by exactly one label revision.

        Refuses a label that does not continue ``current`` by revision number
        AND content lineage (``previous_label_digest`` must equal the
        current head's content digest) — a caller cannot skip a revision or
        splice in a label from a different chain, only ever advance one step
        from the head it already trusts.
        """
        if (
            label.profile_id != current.profile_id
            or label.label_revision != current.label_revision + 1
            or label.previous_label_digest != current.label_content_digest
        ):
            raise ProfileCustodyRecordError("next label record does not continue the trusted label head")
        return cls._create_with_self_digest(
            {
                "profile_id": label.profile_id,
                "label_revision": label.label_revision,
                "label_content_digest": label.content_digest,
                "label_self_digest": label.self_digest,
                "source_witness": current.self_digest,
                "previous_head_digest": current.self_digest,
            },
            "cannot construct next profile label head",
        )

    def verifies(self, label: ProfileCustodyCapsuleLabel) -> bool:
        """Return whether this head is the trusted head for exactly ``label``.

        The check every reader uses before trusting a label as current: a
        label is only "the" current one if a head record independently
        vouches for its identity AND digest, not merely because it happens
        to be the most recently written one on disk.
        """
        return (
            label.profile_id == self.profile_id
            and label.label_revision == self.label_revision
            and label.content_digest == self.label_content_digest
            and label.self_digest == self.label_self_digest
        )


class ProfileLabelHeadPendingAdvance(_CustodyDigestModel):
    """Crash-recovery witness for one label-record then head advance."""

    _digest_maximum_bytes = LABEL_HEAD_MAX_BYTES
    _digest_subject = "pending profile label head advance"

    schema_version: Literal[1] = 1
    operation_id: UUID
    profile_id: UUID
    expected_head_digest: str
    expected_label: ProfileCustodyCapsuleLabel
    replacement_label: ProfileCustodyCapsuleLabel
    replacement_head: ProfileLabelHead
    self_digest: str = Field(min_length=71, max_length=71)

    @field_validator("expected_head_digest")
    @classmethod
    def _validate_expected_head_digest(cls, value: str) -> str:
        if (
            len(value) != 71
            or not value.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value[7:])
        ):
            raise ValueError("pending profile label head digest must be a lowercase sha256 digest")
        return value

    @model_validator(mode="after")
    def _validate_pending(self) -> ProfileLabelHeadPendingAdvance:
        if (
            self.expected_label.profile_id != self.profile_id
            or self.replacement_label.profile_id != self.profile_id
            or self.replacement_head.profile_id != self.profile_id
            or self.replacement_head.previous_head_digest != self.expected_head_digest
            or not self.replacement_head.verifies(self.replacement_label)
        ):
            raise ValueError("pending profile label head advance has inconsistent lineage")
        if self.self_digest != self.computed_self_digest:
            raise ValueError("pending profile label head advance self digest does not match")
        return self

    @classmethod
    def create(
        cls,
        *,
        expected_head: ProfileLabelHead,
        expected_label: ProfileCustodyCapsuleLabel,
        replacement_label: ProfileCustodyCapsuleLabel,
        replacement_head: ProfileLabelHead,
    ) -> ProfileLabelHeadPendingAdvance:
        """Record intent to advance the label head, durably, before the advance is committed.

        This is the crash-recovery witness the class docstring names: written
        BEFORE the actual label-then-head write lands, so a process that dies
        mid-advance leaves a record recovery can resume from, rather than an
        untraceable partial write. Refuses to start unless ``expected_head``
        already verifies ``expected_label`` — recovery can only resume from a
        state that was itself trustworthy.
        """
        if not expected_head.verifies(expected_label):
            raise ProfileCustodyRecordError("pending label advance does not start at its trusted head")
        return cls._create_with_self_digest(
            {
                "operation_id": uuid4(),
                "profile_id": expected_head.profile_id,
                "expected_head_digest": expected_head.self_digest,
                "expected_label": expected_label,
                "replacement_label": replacement_label,
                "replacement_head": replacement_head,
            },
            "cannot construct pending profile label head advance",
        )


__all__ = ["LABEL_HEAD_MAX_BYTES", "ProfileLabelHead", "ProfileLabelHeadPendingAdvance"]
