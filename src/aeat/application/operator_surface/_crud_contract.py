"""Standardized CRUD verb contract for mutating noun-groups.

Locks the canonical five-verb mutating-noun-group shape
(``add``/``remove``/``update``/``view``/``list``). Every operator-facing
CLI domain that exposes an edit work surface over persisted records
(ledger transactions, purchase invoice evidence, payable and
collectible invoices, profile values, auth providers, apoderado
configuration, inventory rows, bucket records, usage ratios) must
satisfy this contract or declare an explicit exception.

The reference shape is the ``aeat app ledger evidence`` verb group:
five CRUD verbs with strict semantics. Orthogonal-axis verbs and
lifecycle-state verbs remain at the noun-group level but are
explicitly demoted to sub-verbs, not CRUD substitutes. Key-value-as-
record noun-groups adopt a documented ``set``/``get``/``unset``
exception where records are conceptually keyed scalars rather than
entities.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CrudVerb(StrEnum):
    """Canonical five-verb spine for mutating noun-groups."""

    ADD = "add"
    REMOVE = "remove"
    UPDATE = "update"
    VIEW = "view"
    LIST = "list"


CANONICAL_CRUD_VERBS: frozenset[CrudVerb] = frozenset(CrudVerb)
"""The five-verb canonical CRUD set every strict noun-group must register.

A :class:`MutatingNounGroupContract` with
``exception=STRICT_CRUD`` must declare exactly these five verbs. Tests
assert against this constant so any future :class:`CrudVerb` addition
surfaces immediately as a contract drift.
"""


class BucketEventSuffix(StrEnum):
    """Canonical bucket event suffixes emitted by mutating CRUD verbs.

    Every mutating verb in a noun-group must emit a bucket event whose name
    ends with one of these suffixes (e.g. ``payable_invoice.created``,
    ``profile.updated``). Read verbs (``view``, ``list``) emit no event.
    Lifecycle-state verbs use state-specific suffixes documented per
    noun-group rather than these CRUD suffixes.
    """

    CREATED = "created"
    REMOVED = "removed"
    UPDATED = "updated"


_CRUD_VERB_TO_EVENT_SUFFIX: dict[CrudVerb, BucketEventSuffix] = {
    CrudVerb.ADD: BucketEventSuffix.CREATED,
    CrudVerb.REMOVE: BucketEventSuffix.REMOVED,
    CrudVerb.UPDATE: BucketEventSuffix.UPDATED,
}


def event_suffix_for(verb: CrudVerb) -> BucketEventSuffix | None:
    """Return the :class:`BucketEventSuffix` for ``verb``, or None for read verbs."""
    return _CRUD_VERB_TO_EVENT_SUFFIX.get(verb)


class OrthogonalAxis(StrEnum):
    """Axes that operate on existing noun-group records without lifecycle change.

    Orthogonal-axis verbs are NOT CRUD substitutes. They stay at the
    noun-group level alongside the canonical CRUD spine and operate on
    records the spine materialised.
    """

    CLASSIFY = "classify"
    ALLOCATE = "allocate"
    ATTACH = "attach"
    LINK = "link"
    CHECK = "check"
    PREFLIGHT = "preflight"
    RECONCILE = "reconcile"


class LifecycleStateVerb(StrEnum):
    """State-transition verbs distinct from CRUD lifecycle.

    Lifecycle-state verbs move a record between named states with distinct
    semantics. They emit state-specific bucket events (e.g.
    ``modelo.work_unit.discarded``) rather than the CRUD suffixes and do
    not collapse into ``remove`` or ``update``.
    """

    ARCHIVE = "archive"
    STASH = "stash"
    RESET = "reset"
    DISCARD = "discard"


class KeyValueVerb(StrEnum):
    """Documented exception for key-value-as-record noun-groups.

    Where records are conceptually keyed scalars rather than entities
    (profile values, usage ratios, configuration keys), the canonical CRUD
    shape adapts: ``add``→``set KEY VALUE``, ``remove``→``unset KEY``,
    ``update``→``set KEY VALUE`` (idempotent), ``view``→``get KEY``,
    ``list``→``list [--prefix PREFIX]``.
    """

    SET = "set"
    GET = "get"
    UNSET = "unset"
    LIST = "list"


class NounGroupExceptionKind(StrEnum):
    """Categories of documented deviation from the strict CRUD spine."""

    STRICT_CRUD = "strict_crud"
    KEY_VALUE_AS_RECORD = "key_value_as_record"
    LIFECYCLE_OPERATIONS_ONLY = "lifecycle_operations_only"


class MutatingNounGroupContract(BaseModel):
    """Contract describing a single mutating noun-group's canonical shape.

    Every noun-group that exposes an edit work surface registers a
    contract instance. CLI Typer-graph conformance tests and runtime
    invariant tests consume the registered contract to assert the
    noun-group's verb set is canonical or carries a documented exception.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    noun: str = Field(min_length=1, description="canonical noun (e.g. 'payable_invoice')")
    cli_path: str = Field(
        min_length=1,
        description="Typer mount path (e.g. 'aeat app ledger invoice')",
    )
    exception: NounGroupExceptionKind = Field(
        default=NounGroupExceptionKind.STRICT_CRUD,
        description="documented exception class; STRICT_CRUD is the default",
    )
    crud_verbs: frozenset[CrudVerb] = Field(
        default_factory=lambda: frozenset(CrudVerb),
        description="canonical CRUD verbs registered on this noun-group",
    )
    key_value_verbs: frozenset[KeyValueVerb] = Field(
        default_factory=lambda: frozenset[KeyValueVerb](),
        description="key-value verbs (set/get/unset/list) when exception is KEY_VALUE_AS_RECORD",
    )
    orthogonal_axes: frozenset[OrthogonalAxis] = Field(
        default_factory=lambda: frozenset[OrthogonalAxis](),
        description="orthogonal axes registered alongside the canonical spine",
    )
    lifecycle_state_verbs: frozenset[LifecycleStateVerb] = Field(
        default_factory=lambda: frozenset[LifecycleStateVerb](),
        description="lifecycle-state verbs registered alongside the canonical spine",
    )

    @field_validator("noun")
    @classmethod
    def _noun_is_canonical(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("noun must not carry leading or trailing whitespace")
        if value != value.lower():
            raise ValueError("noun must be lowercase canonical form")
        return value

    @model_validator(mode="after")
    def _verb_axes_consistent(self) -> MutatingNounGroupContract:
        if self.exception is NounGroupExceptionKind.STRICT_CRUD:
            if self.crud_verbs != CANONICAL_CRUD_VERBS:
                raise ValueError(
                    f"strict-CRUD noun-group {self.noun!r} must register exactly the canonical "
                    f"five verbs; got {sorted(v.value for v in self.crud_verbs)!r}",
                )
            if self.key_value_verbs:
                raise ValueError(
                    f"strict-CRUD noun-group {self.noun!r} must not register key-value verbs",
                )
        elif self.exception is NounGroupExceptionKind.KEY_VALUE_AS_RECORD:
            if not self.key_value_verbs:
                raise ValueError(
                    f"key-value-exception noun-group {self.noun!r} must register at least one "
                    f"key-value verb (set/get/unset/list)",
                )
            if self.crud_verbs and self.crud_verbs != CANONICAL_CRUD_VERBS:
                raise ValueError(
                    f"key-value-exception noun-group {self.noun!r} may register the canonical CRUD "
                    f"spine alongside its key-value verbs, but partial CRUD registration is rejected",
                )
        elif self.exception is NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY:
            if self.crud_verbs:
                raise ValueError(
                    f"lifecycle-only noun-group {self.noun!r} must not register CRUD verbs",
                )
            if not self.lifecycle_state_verbs:
                raise ValueError(
                    f"lifecycle-only noun-group {self.noun!r} must register at least one lifecycle-state verb",
                )
        return self

    def declares_crud(self) -> bool:
        """Return True iff this noun-group exposes the strict CRUD spine."""
        return self.crud_verbs == CANONICAL_CRUD_VERBS

    def all_verb_names(self) -> frozenset[str]:
        """Return every registered verb name across CRUD, key-value, orthogonal, lifecycle axes."""
        names: set[str] = set()
        names.update(v.value for v in self.crud_verbs)
        names.update(v.value for v in self.key_value_verbs)
        names.update(v.value for v in self.orthogonal_axes)
        names.update(v.value for v in self.lifecycle_state_verbs)
        return frozenset(names)


class CrudContractCatalogue(BaseModel):
    """Catalogue of every mutating noun-group's registered contract.

    The catalogue is the source of truth for cross-cutting CLI conformance
    checks. Tests assert every Typer noun-group app present in the CLI
    layer has a matching catalogue entry, and that its registered verb set
    matches the contract.
    """

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    entries: tuple[MutatingNounGroupContract, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _unique_per_cli_path(self) -> CrudContractCatalogue:
        seen: set[str] = set()
        for entry in self.entries:
            if entry.cli_path in seen:
                raise ValueError(f"duplicate noun-group contract for CLI path {entry.cli_path!r}")
            seen.add(entry.cli_path)
        return self

    def find(self, cli_path: str) -> MutatingNounGroupContract | None:
        """Return the :class:`MutatingNounGroupContract` for ``cli_path``, or ``None`` if not registered.

        Args:
            cli_path: The Typer mount path to look up (e.g.
                ``"aeat app ledger invoice"``).
        """
        for entry in self.entries:
            if entry.cli_path == cli_path:
                return entry
        return None


__all__ = [
    "CANONICAL_CRUD_VERBS",
    "BucketEventSuffix",
    "CrudContractCatalogue",
    "CrudVerb",
    "KeyValueVerb",
    "LifecycleStateVerb",
    "MutatingNounGroupContract",
    "NounGroupExceptionKind",
    "OrthogonalAxis",
    "event_suffix_for",
]
