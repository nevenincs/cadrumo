"""Generate the desktop's pre-auth provider marks from the admitted agent wheel."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import tempfile
import zipfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from urllib.parse import quote_from_bytes
from uuid import uuid4

from dev.packaging.native.build_directory import require_enrolled_build

from .agent import agent_wheel
from .build_paths import build_paths
from .stable_output import write_text

_PACKAGE = "cadrumo_agent/providers/"
_METADATA = f"{_PACKAGE}provider_metadata.json"
_ICON_MODULE = f"{_PACKAGE}provider_icons.py"
_ICON_DIRECTORY = f"{_PACKAGE}icons/"
_ICON_FILENAME = re.compile(r"[a-z0-9][a-z0-9._-]*\.svg\Z")
_PROVIDER_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")


class ProviderIconGenerationError(ValueError):
    """The admitted agent wheel has no complete, safe provider artwork set."""


def _read_once(archive: zipfile.ZipFile, name: str) -> bytes:
    """Read one unique wheel member, refusing duplicate archive names."""
    if archive.namelist().count(name) != 1:
        raise ProviderIconGenerationError(f"The agent wheel must contain one {name} member")
    try:
        return archive.read(name)
    except (KeyError, zipfile.BadZipFile) as error:
        raise ProviderIconGenerationError(f"The agent wheel cannot read {name}") from error


@contextmanager
def _provider_icons_module(archive: zipfile.ZipFile) -> Generator[ModuleType]:
    """Load the wheel's stdlib-only validator without importing the agent runtime."""
    source = _read_once(archive, _ICON_MODULE)
    members = archive.namelist()
    assets: dict[str, bytes] = {}
    for member in members:
        if not member.startswith(_ICON_DIRECTORY) or member.endswith("/"):
            continue
        filename = member.removeprefix(_ICON_DIRECTORY)
        if "/" in filename or _ICON_FILENAME.fullmatch(filename) is None:
            raise ProviderIconGenerationError("The provider icon directory has an invalid member")
        if filename in assets:
            raise ProviderIconGenerationError("The provider icon directory has duplicate artwork")
        assets[filename] = _read_once(archive, member)

    with tempfile.TemporaryDirectory(prefix="cadrumo-provider-icons-") as temporary:
        package_name = f"_cadrumo_provider_icons_{uuid4().hex}"
        package = Path(temporary) / package_name
        icon_directory = package / "icons"
        icon_directory.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "provider_icons.py").write_bytes(source)
        for filename, contents in assets.items():
            (icon_directory / filename).write_bytes(contents)

        search_root = str(Path(temporary))
        sys.path.insert(0, search_root)
        try:
            yield importlib.import_module(f"{package_name}.provider_icons")
        finally:
            sys.path.remove(search_root)
            for name in tuple(sys.modules):
                if name == package_name or name.startswith(f"{package_name}."):
                    del sys.modules[name]


def _provider_rows(document: object) -> list[tuple[str, str | None]]:
    """Read provider IDs and icon keys from the wheel's packaged metadata."""
    if not isinstance(document, dict) or not isinstance(document.get("providers"), list):
        raise ProviderIconGenerationError("The agent provider metadata has no providers list")
    rows: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for row in document["providers"]:
        if not isinstance(row, dict):
            raise ProviderIconGenerationError("The agent provider metadata has an invalid provider")
        provider = row.get("id")
        if "icon" not in row:
            raise ProviderIconGenerationError("The agent provider metadata omits an icon declaration")
        icon = row["icon"]
        if not isinstance(provider, str) or _PROVIDER_ID.fullmatch(provider) is None:
            raise ProviderIconGenerationError("The agent provider metadata has an invalid provider ID")
        if provider in seen:
            raise ProviderIconGenerationError("The agent provider metadata has duplicate provider IDs")
        if icon is not None and (not isinstance(icon, str) or not icon or icon != icon.strip()):
            raise ProviderIconGenerationError(f"Provider {provider} has no declared icon key")
        seen.add(provider)
        rows.append((provider, icon))
    return rows


def _data_url(artwork: bytes) -> str:
    """Keep the validated SVG self-contained in a data URL for the frontend."""
    return f"data:image/svg+xml,{quote_from_bytes(artwork, safe='')}"


def provider_icon_document(wheel: Path) -> dict[str, object]:
    """Project provider IDs, validated SVGs and license terms from *wheel*."""
    try:
        archive = zipfile.ZipFile(wheel)
    except (OSError, zipfile.BadZipFile) as error:
        raise ProviderIconGenerationError("The admitted agent wheel is not a readable ZIP archive") from error

    with archive:
        try:
            metadata = json.loads(_read_once(archive, _METADATA))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderIconGenerationError("The agent provider metadata is not valid JSON") from error
        providers = _provider_rows(metadata)
        with _provider_icons_module(archive) as icons:
            output: dict[str, dict[str, str]] = {}
            expected_assets: set[str] = set()
            for provider_id, icon_key in providers:
                if icon_key is None:
                    continue
                try:
                    variants = icons.icon_variants(icon_key)
                except (LookupError, ValueError) as error:
                    raise ProviderIconGenerationError(
                        f"Provider {provider_id} names artwork absent from the agent wheel"
                    ) from error
                if (
                    not variants
                    or variants[0] is not icons.IconVariant.MONO
                    or any(variant not in (icons.IconVariant.MONO, icons.IconVariant.COLOR) for variant in variants)
                    or len(set(variants)) != len(variants)
                ):
                    raise ProviderIconGenerationError(f"Provider {provider_id} has no preferred mono artwork")

                rendered: dict[str, str] = {}
                for variant in variants:
                    filename = (
                        f"{icon_key}.svg" if variant is icons.IconVariant.MONO else f"{icon_key}-{variant.value}.svg"
                    )
                    expected_assets.add(filename)
                    try:
                        rendered[variant.value] = _data_url(icons.read_icon(icon_key, variant))
                    except (LookupError, OSError, ValueError) as error:
                        raise ProviderIconGenerationError(
                            f"The agent wheel refused artwork for provider {provider_id}"
                        ) from error
                output[provider_id] = rendered

            actual_assets = {
                name.removeprefix(_ICON_DIRECTORY)
                for name in archive.namelist()
                if name.startswith(_ICON_DIRECTORY) and not name.endswith("/")
            }
            if expected_assets != actual_assets:
                raise ProviderIconGenerationError("The provider catalog and bundled icon files differ")

            attribution = icons.ICON_ATTRIBUTION
            credit = {
                field: getattr(attribution, field)
                for field in ("title", "url", "pin", "licence", "notice", "trademarks")
            }
            if any(not isinstance(value, str) or not value for value in credit.values()):
                raise ProviderIconGenerationError("The agent icon attribution is incomplete")
            return {"providers": dict(sorted(output.items())), "attribution": credit}


def generate(wheel: Path, output: Path) -> None:
    """Write deterministic JSON to the CMake-owned generated frontend directory."""
    document = provider_icon_document(wheel)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_text(output, json.dumps(document, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    """Generate provider artwork from the wheel admitted by this build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    paths = build_paths(arguments.build)
    expected = paths["desktop_frontend_generated"] / "provider-icons.json"
    if arguments.output.resolve() != expected.resolve():
        parser.error("--output must be the enrolled build's desktop frontend generated output")
    generate(agent_wheel(paths["agent"]), expected)


if __name__ == "__main__":
    main()
