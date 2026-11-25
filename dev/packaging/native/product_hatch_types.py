"""Typed view of the Hatch wheel selection API used for product fingerprints."""

from collections.abc import Iterable, Mapping
from contextlib import AbstractContextManager
from typing import Protocol


class HatchIncludedFile(Protocol):
    """One selected wheel member and its source path."""

    distribution_path: str
    path: str


class HatchMetadataCore(Protocol):
    """Metadata files that contribute to a wheel."""

    readme_path: str | None
    license_files: list[str]


class HatchMetadata(Protocol):
    """The wheel builder's metadata view."""

    core: HatchMetadataCore


class HatchConfig(Protocol):
    """The active wheel build-data context."""

    def set_build_data(self, data: dict[str, object]) -> AbstractContextManager[object]:
        """Bind the active wheel build data."""
        ...


class HatchHook(Protocol):
    """Lifecycle and source configuration of a build hook."""

    config: Mapping[str, str]

    def initialize(self, version: str, data: dict[str, object]) -> None:
        """Prepare hook-owned build data."""
        ...

    def finalize(self, version: str, data: dict[str, object], artifact: str) -> None:
        """Complete the hook lifecycle."""
        ...


class HatchWheelBuilder(Protocol):
    """The wheel builder operations needed for fingerprinting."""

    config: HatchConfig
    metadata: HatchMetadata

    def get_default_build_data(self) -> dict[str, object]:
        """Return the initial build-data mapping."""
        ...

    def set_build_data_defaults(self, data: dict[str, object]) -> None:
        """Populate defaults for the wheel build."""
        ...

    def get_build_hooks(self, directory: str) -> Mapping[str, HatchHook]:
        """Return configured wheel build hooks."""
        ...

    def recurse_included_files(self) -> Iterable[HatchIncludedFile]:
        """Yield the selected wheel members."""
        ...
