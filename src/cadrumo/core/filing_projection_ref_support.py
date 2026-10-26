"""Private compiler helpers for core filing projection references."""

STRING_WIRE_FIELDS = frozenset(
    {
        "casilla_id",
        "cohort",
        "fact",
        "field",
        "projection_kind",
        "representative_kind",
        "value",
    },
)


def validated_type_members(union_args: tuple[object, ...]) -> tuple[type, ...]:
    """Return ``union_args`` re-typed as ``type``, refusing a non-class member."""
    validated: list[type] = []
    for member in union_args:
        if not isinstance(member, type):
            raise TypeError(f"expected a FilingProjectionRef union member to be a type, got {member!r}")
        validated.append(member)
    return tuple(validated)
