"""Object-only protocol record assertions shared by actual integration callers."""

from typing import cast


def _record(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)
