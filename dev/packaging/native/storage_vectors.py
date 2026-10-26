"""Independent conformance vectors for Python and native storage resolvers."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from .application_environment import load


class StorageRootVector(NamedTuple):
    """One conformance case every storage root resolver must reproduce.

    ``environment`` is the full variable map; ``known_folder`` is the value a
    Windows resolver reads from ``FOLDERID_LocalAppData`` instead of the
    environment (``None`` when that lookup fails). Exactly one of
    ``expected_root`` and ``refusal`` is set. Platforms, modes and refusals
    carry the package declaration's tokens.
    """

    name: str
    platform: str
    mode: str
    environment: tuple[tuple[str, str], ...]
    checkout: str | None
    known_folder: str | None
    channel: str
    expected_root: str | None
    refusal: str | None
    invalid_environment: tuple[str, ...] = ()
    invalid_checkout: bool = False
    invalid_known_folder: bool = False

    def as_contract(self) -> dict[str, object]:
        """Project the vector onto the JSON shape the native contract carries."""
        return {
            "name": self.name,
            "platform": self.platform,
            "mode": self.mode,
            "environment": dict(self.environment),
            "checkout": self.checkout,
            "known_folder": self.known_folder,
            "channel": self.channel,
            "expected_root": self.expected_root,
            "refusal": self.refusal,
            "invalid_environment": list(self.invalid_environment),
            "invalid_checkout": self.invalid_checkout,
            "invalid_known_folder": self.invalid_known_folder,
        }


def storage_root_vectors(root: Path) -> tuple[StorageRootVector, ...]:
    """Return the conformance vectors the package declaration authors for every storage root resolver.

    Expected roots and refusals are written out by hand in
    ``native/application-environment.toml``, independently of any resolver, so
    replaying them tests the resolver rather than echoing it.
    """
    return tuple(
        StorageRootVector(
            name=vector["name"],
            platform=vector["platform"],
            mode=vector["mode"],
            environment=tuple(vector["environment"].items()),
            checkout=vector["checkout"],
            known_folder=vector["known_folder"],
            channel=vector["channel"],
            expected_root=vector["expected_root"],
            refusal=vector["refusal"],
            invalid_environment=tuple(vector["invalid_environment"]),
            invalid_checkout=vector["invalid_checkout"],
            invalid_known_folder=vector["invalid_known_folder"],
        )
        for vector in load(root).vectors
    )


INVALID_NATIVE_PATH_BYTES = (0xFF,)
INVALID_NATIVE_PATH_UTF16 = (0xD800,)
FILESYSTEM_PATH_REFUSED = "filesystem_path_refused"


def invalid_native_path_value(platform: str) -> str:
    """Independent native-input fixture encoding; never replacement decoding."""
    if platform == "windows":
        return b"".join(value.to_bytes(2, "little") for value in INVALID_NATIVE_PATH_UTF16).decode(
            "utf-16-le", "surrogatepass"
        )
    return bytes(INVALID_NATIVE_PATH_BYTES).decode("utf-8", "surrogateescape")


class StoragePathVector(NamedTuple):
    """Host filesystem fixture rooted at a fresh absolute test directory."""

    name: str
    components: tuple[str, ...]
    directories: tuple[str, ...]
    files: tuple[str, ...]
    links: tuple[tuple[str, str], ...]
    expected_components: tuple[str, ...] | None
    refusal: str | None

    def as_contract(self) -> dict[str, object]:
        """Project fixture operations and independently authored outcomes."""
        return {
            "name": self.name,
            "components": list(self.components),
            "directories": list(self.directories),
            "files": list(self.files),
            "links": [list(link) for link in self.links],
            "expected_components": None if self.expected_components is None else list(self.expected_components),
            "refusal": self.refusal,
        }


def storage_path_vectors() -> tuple[StoragePathVector, ...]:
    """Link evidence is checked on the original and normalized paths, without creation."""
    refused = FILESYSTEM_PATH_REFUSED
    return (
        StoragePathVector("missing-parent-normalized", ("missing", "..", "selected"), (), (), (), ("selected",), None),
        StoragePathVector(
            "original-link-parent-refused",
            ("link", "..", "selected"),
            ("target",),
            (),
            (("link", "target"),),
            None,
            refused,
        ),
        StoragePathVector(
            "normalized-link-refused",
            ("missing", "..", "link", "child"),
            ("target",),
            (),
            (("link", "target"),),
            None,
            refused,
        ),
        StoragePathVector("dangling-link-refused", ("link", "child"), (), (), (("link", "absent"),), None, refused),
        StoragePathVector("regular-file-component-refused", ("file", "child"), (), ("file",), (), None, refused),
    )


NON_ABSOLUTE_PIN = "non_absolute_pin"


class StorageMemberVector(NamedTuple):
    """One override of a storage member below a fresh absolute root.

    ``platform`` is ``windows`` or ``posix``: both resolvers read a member with
    their host's path grammar, so a drive-relative spelling is a refusal on
    Windows and an ordinary relative name elsewhere. ``value`` is the override
    exactly as an operator writes it. Exactly one of ``expected_components``
    (the result, relative to the root) and ``refusal`` is set.
    """

    name: str
    platform: str
    variable: str
    value: str
    expected_components: tuple[str, ...] | None
    refusal: str | None

    def as_contract(self) -> dict[str, object]:
        """Project the override and its independently authored outcome."""
        return {
            "name": self.name,
            "platform": self.platform,
            "variable": self.variable,
            "value": self.value,
            "expected_components": None if self.expected_components is None else list(self.expected_components),
            "refusal": self.refusal,
        }


def storage_member_vectors() -> tuple[StorageMemberVector, ...]:
    """A relative member lands below its root; a drive- or root-relative one is never re-anchored."""
    variable = "CADRUMO_LOG_DIR"
    refused = NON_ABSOLUTE_PIN
    return (
        StorageMemberVector("windows-relative-member-below-root", "windows", variable, "logs", ("logs",), None),
        StorageMemberVector(
            "windows-relative-member-normalized", "windows", variable, r"unused\..\logs\run", ("logs", "run"), None
        ),
        StorageMemberVector("windows-drive-relative-member-refused", "windows", variable, "C:rooted", None, refused),
        StorageMemberVector(
            "windows-rooted-member-without-drive-refused", "windows", variable, r"\rooted", None, refused
        ),
        StorageMemberVector("windows-slash-rooted-member-refused", "windows", variable, "/rooted", None, refused),
        StorageMemberVector("posix-relative-member-below-root", "posix", variable, "logs", ("logs",), None),
        StorageMemberVector(
            "posix-relative-member-normalized", "posix", variable, "unused/../logs/run", ("logs", "run"), None
        ),
        StorageMemberVector("posix-drive-like-name-is-relative", "posix", variable, "C:rooted", ("C:rooted",), None),
    )
