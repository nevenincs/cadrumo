"""Locate the components the native engine installed, from the records it writes.

The native component engine owns every component: it downloads, installs, checks
and removes the browser and the local AI. Once an item verifies it writes one
record for it, ``<item>.json`` in the ``DEPENDENCY_RECEIPTS`` storage member.
Beside the manifest of installed files, the record says where the item is: the
folder its files are relative to, the paths a consumer uses inside that folder,
and identity facts a consumer compares with its own, such as the driver version a
browser build belongs to.

Python only consumes components. This reader reads that record and confirms that
the paths it names exist. It never hashes, launches, installs or removes anything,
and it never decides an item's state: a located component is one whose record
says where it is and whose named paths are there, not a verdict that it works.

The local AI record also names the fixed loopback address of the one server the
runtime manager runs from that program. :func:`local_ai_chat_url` is the one
place the readers learn where to send a request: the operator's own endpoint
when one is configured, otherwise the address the record names.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import BaseModel, NonNegativeInt, StringConstraints, ValidationError, field_validator

from .config_runtime_fields import LOCAL_AI_CHAT_URL
from .errors.hierarchy import pydantic_validation_boundary
from .models import STRICT_FROZEN_CONFIG
from .storage_taxonomy import StorageCategory
from .storage_taxonomy_locations import storage_path

if TYPE_CHECKING:
    from .config import Settings

__all__ = [
    "ComponentItem",
    "ComponentLocateOutcome",
    "ComponentLocation",
    "ComponentRecord",
    "ComponentRecordFile",
    "ComponentRecordReading",
    "ComponentRecordState",
    "LocatedComponent",
    "LocatedLocalAi",
    "component_records_root",
    "local_ai_chat_url",
    "locate_component",
    "locate_local_ai",
    "read_component_record",
    "uses_managed_local_ai",
]

#: The record shape the engine writes.
COMPONENT_RECORD_VERSION: Final = 1
#: The local AI record's path naming the program's executable.
LOCAL_AI_PROGRAM_PATH: Final = "program"
#: The local AI record's path naming the models folder.
LOCAL_AI_MODELS_PATH: Final = "models"
#: The local AI record's fact naming the fixed loopback ``host:port`` its server answers on.
LOCAL_AI_ADDRESS_FACT: Final = "address"
_RECORD_BYTES_LIMIT: Final = 4 * 1024 * 1024

type _Name = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,128}$")]
type _Fact = Annotated[str, StringConstraints(min_length=1, max_length=128)]
type _RelativePath = Annotated[str, StringConstraints(min_length=1, max_length=1024)]


class ComponentItem(StrEnum):
    """The components the engine installs; each value is its record's file stem."""

    BROWSER = "browser"
    LOCAL_AI = "local_ai"


def _contained(relative: str) -> str:
    path = PurePosixPath(relative)
    if path.is_absolute() or "\\" in relative or ":" in relative or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("a component path is a plain relative path inside its folder")
    if path.as_posix() != relative:
        raise ValueError("a component path is written in its canonical form")
    return relative


class ComponentRecordFile(BaseModel):
    """One installed file the record lists, relative to the component's folder."""

    model_config = STRICT_FROZEN_CONFIG

    path: _RelativePath
    size_bytes: NonNegativeInt
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @field_validator("path")
    @classmethod
    @pydantic_validation_boundary
    def _validate_path(cls, value: str) -> str:
        return _contained(value)


class ComponentLocation(BaseModel):
    """Where a verified component is: its folder, the paths a consumer uses, and identity facts."""

    model_config = STRICT_FROZEN_CONFIG

    root: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    paths: dict[_Name, _RelativePath]
    facts: dict[_Name, _Fact]

    @field_validator("root")
    @classmethod
    @pydantic_validation_boundary
    def _validate_root(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("a component folder is an absolute path")
        return value

    @field_validator("paths")
    @classmethod
    @pydantic_validation_boundary
    def _validate_paths(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("a component location names at least one path")
        for relative in value.values():
            _contained(relative)
        return value

    @property
    def folder(self) -> Path:
        """The component's folder."""
        return Path(self.root)

    def path(self, name: str) -> Path | None:
        """Return the named path inside the folder, or ``None`` when the record names none."""
        relative = self.paths.get(name)
        return None if relative is None else self.folder.joinpath(*PurePosixPath(relative).parts)


class ComponentRecord(BaseModel):
    """One component's record, as the engine wrote it after the component verified."""

    model_config = STRICT_FROZEN_CONFIG

    receipt_version: Literal[1]
    item_id: ComponentItem
    version: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None
    files: tuple[ComponentRecordFile, ...]
    verified_at: datetime
    hosts: tuple[Annotated[str, StringConstraints(min_length=1, max_length=253)], ...]
    location: ComponentLocation | None = None


class ComponentRecordState(StrEnum):
    """Whether a component's record could be read: present, never written, or unreadable."""

    PRESENT = "present"
    ABSENT = "absent"
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class ComponentRecordReading:
    """A read of one component's record; ``record`` is set exactly when it is present."""

    state: ComponentRecordState
    record: ComponentRecord | None = None


class ComponentLocateOutcome(StrEnum):
    """Why a component was, or was not, located from its record."""

    LOCATED = "located"
    NO_RECORD = "no_record"
    RECORD_UNREADABLE = "record_unreadable"
    NO_LOCATION = "no_location"
    OTHER_FOLDER = "other_folder"
    OTHER_IDENTITY = "other_identity"
    PATH_MISSING = "path_missing"


@dataclass(frozen=True, slots=True)
class LocatedComponent:
    """Where a component is, as its record says, and whether every named path is there.

    ``paths`` holds every path the record names, resolved under ``folder``;
    ``missing`` names those that are not there.
    """

    item: ComponentItem
    outcome: ComponentLocateOutcome
    version: str | None = None
    folder: Path | None = None
    paths: Mapping[str, Path] = field(default_factory=dict)
    missing: tuple[str, ...] = ()

    @property
    def located(self) -> bool:
        """Whether the record says where the component is and every path it names exists."""
        return self.outcome is ComponentLocateOutcome.LOCATED


def component_records_root(settings: Settings | None = None) -> Path:
    """Return the folder the engine writes component records into."""
    return storage_path(StorageCategory.DEPENDENCY_RECEIPTS, settings=settings)


def read_component_record(item: ComponentItem, *, records_root: Path) -> ComponentRecordReading:
    """Read ``item``'s record from ``records_root``; a damaged or foreign file is unreadable, never absent."""
    path = records_root / f"{item.value}.json"
    try:
        with path.open("rb") as handle:
            content = handle.read(_RECORD_BYTES_LIMIT + 1)
    except FileNotFoundError:
        return ComponentRecordReading(state=ComponentRecordState.ABSENT)
    except OSError:
        return ComponentRecordReading(state=ComponentRecordState.UNREADABLE)
    if len(content) > _RECORD_BYTES_LIMIT:
        return ComponentRecordReading(state=ComponentRecordState.UNREADABLE)
    try:
        record = ComponentRecord.model_validate_json(content)
    except ValidationError:
        return ComponentRecordReading(state=ComponentRecordState.UNREADABLE)
    if record.item_id is not item:
        return ComponentRecordReading(state=ComponentRecordState.UNREADABLE)
    return ComponentRecordReading(state=ComponentRecordState.PRESENT, record=record)


def _same_folder(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def locate_component(
    item: ComponentItem,
    *,
    records_root: Path,
    expected_folder: Path | None = None,
    expected_facts: Mapping[str, str] | None = None,
) -> LocatedComponent:
    """Locate ``item`` from its record alone.

    ``expected_folder`` is where the consumer will look, so a record for another
    folder does not locate the component there. ``expected_facts`` are identity
    facts the record must carry with the same values, such as the driver version
    a browser build belongs to. Every path the record names must exist.
    """
    reading = read_component_record(item, records_root=records_root)
    if reading.record is None:
        outcome = (
            ComponentLocateOutcome.NO_RECORD
            if reading.state is ComponentRecordState.ABSENT
            else ComponentLocateOutcome.RECORD_UNREADABLE
        )
        return LocatedComponent(item=item, outcome=outcome)
    record = reading.record
    location = record.location
    if location is None:
        return LocatedComponent(item=item, outcome=ComponentLocateOutcome.NO_LOCATION, version=record.version)
    paths = {name: path for name in location.paths if (path := location.path(name)) is not None}
    located = LocatedComponent(
        item=item,
        outcome=ComponentLocateOutcome.LOCATED,
        version=record.version,
        folder=location.folder,
        paths=paths,
    )
    if expected_folder is not None and not _same_folder(location.folder, expected_folder):
        return _with(located, ComponentLocateOutcome.OTHER_FOLDER)
    if any(location.facts.get(name) != value for name, value in (expected_facts or {}).items()):
        return _with(located, ComponentLocateOutcome.OTHER_IDENTITY)
    missing = tuple(name for name, path in paths.items() if not path.exists())
    if missing:
        return LocatedComponent(
            item=item,
            outcome=ComponentLocateOutcome.PATH_MISSING,
            version=record.version,
            folder=location.folder,
            paths=paths,
            missing=missing,
        )
    return located


def _with(located: LocatedComponent, outcome: ComponentLocateOutcome) -> LocatedComponent:
    return LocatedComponent(
        item=located.item,
        outcome=outcome,
        version=located.version,
        folder=located.folder,
        paths=located.paths,
    )


@dataclass(frozen=True, slots=True)
class LocatedLocalAi:
    """The local AI as its record locates it: the program, the models folder and the server's address.

    ``address`` is the loopback ``host:port`` the record names, or ``None`` when
    the record names none this reader accepts.
    """

    component: LocatedComponent
    address: str | None = None

    @property
    def located(self) -> bool:
        """Whether the record locates the program and the models and names the server's address."""
        return self.component.located and self.address is not None

    @property
    def program(self) -> Path | None:
        """The program's executable, as the record names it."""
        return self.component.paths.get(LOCAL_AI_PROGRAM_PATH)

    @property
    def models(self) -> Path | None:
        """The models folder, as the record names it."""
        return self.component.paths.get(LOCAL_AI_MODELS_PATH)

    @property
    def chat_url(self) -> str | None:
        """The server's chat endpoint at the recorded address."""
        return None if self.address is None else f"http://{self.address}/api/chat"


def _loopback_address(value: str | None) -> str | None:
    host, separator, port = (value or "").rpartition(":")
    if not separator or not port.isdigit() or not 0 < int(port) < 65536:
        return None
    try:
        loopback = ipaddress.IPv4Address(host).is_loopback
    except ValueError:
        return None
    return f"{host}:{int(port)}" if loopback else None


def locate_local_ai(*, records_root: Path) -> LocatedLocalAi:
    """Locate the local AI from its record alone: the program, the models folder and the server's address."""
    located = locate_component(ComponentItem.LOCAL_AI, records_root=records_root)
    if not located.located:
        return LocatedLocalAi(component=located)
    if not {LOCAL_AI_PROGRAM_PATH, LOCAL_AI_MODELS_PATH} <= located.paths.keys():
        return LocatedLocalAi(component=_with(located, ComponentLocateOutcome.NO_LOCATION))
    record = read_component_record(ComponentItem.LOCAL_AI, records_root=records_root).record
    facts = {} if record is None or record.location is None else record.location.facts
    address = _loopback_address(facts.get(LOCAL_AI_ADDRESS_FACT))
    if address is None:
        return LocatedLocalAi(component=_with(located, ComponentLocateOutcome.OTHER_IDENTITY))
    return LocatedLocalAi(component=located, address=address)


def uses_managed_local_ai(settings: Settings) -> bool:
    """Whether the readers use the server the runtime manager runs, rather than an operator's own endpoint."""
    return settings.cadrumo_llm_ollama_chat_url == LOCAL_AI_CHAT_URL


def local_ai_chat_url(settings: Settings) -> str:
    """Return the chat endpoint the local readers send to.

    An operator who configured another endpoint runs that server themselves, so
    it is used as written. Otherwise the endpoint is the server the local AI
    record names; without a record that locates it, the configured default is
    returned, where nothing Cadrumo runs answers.
    """
    if not uses_managed_local_ai(settings):
        return settings.cadrumo_llm_ollama_chat_url
    located = locate_local_ai(records_root=component_records_root(settings))
    return located.chat_url if located.located and located.chat_url is not None else LOCAL_AI_CHAT_URL
