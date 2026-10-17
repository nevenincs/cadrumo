"""Render Cadrumo's Windows package manifest and register a built Debug stage tree for development.

Every Cadrumo application image embeds a claim on the channel's package identity; the claim is
inert until a package with that identity is registered with an external location holding the
images. Installers register the signed package. This command registers a Debug stage tree loosely,
in developer mode, under the development publisher the Debug images claim, so a developer build
never shares a package family with a distributed one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from xml.etree.ElementTree import Element
from xml.sax.saxutils import escape, quoteattr

from defusedxml import ElementTree
from PIL import Image

from ..command_execution import run_command
from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .identity import DistributionIdentity
from .layout import desktop_image, load_layout
from .platforms.windows import application_manifest_name
from .platforms.windows_manifest import embedded_manifest
from .stable_output import write_bytes

LOGOS = {"Square150x150Logo": 150, "Square44x44Logo": 44, "StoreLogo": 50}
"""Package logo assets, rendered from the generated application icon."""
DEVELOPMENT_CONFIG = "Debug"
"""Only Debug images claim the development publisher that loose registration may use."""


def package_manifest(product: DistributionIdentity, *, publisher: str, executable: str) -> bytes:
    """Render the manifest of a package with external location for the channel's identity."""
    attribute = quoteattr
    text = f"""<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:uap10="http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap uap10 rescap">
  <Identity Name={attribute(product.windows_package_name)} Publisher={attribute(publisher)}
    Version={attribute(product.windows_package_version)} ProcessorArchitecture="neutral" />
  <Properties>
    <DisplayName>{escape(product.name)}</DisplayName>
    <PublisherDisplayName>{escape(product.publisher)}</PublisherDisplayName>
    <Logo>StoreLogo.png</Logo>
    <uap10:AllowExternalContent>true</uap10:AllowExternalContent>
  </Properties>
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
    <rescap:Capability Name="unvirtualizedResources" />
  </Capabilities>
  <Applications>
    <Application Id={attribute(product.windows_package_application)} Executable={attribute(executable)}
      uap10:TrustLevel="mediumIL" uap10:RuntimeBehavior="win32App">
      <uap:VisualElements AppListEntry="none" DisplayName={attribute(product.name)}
        Description={attribute(product.description)} BackgroundColor="transparent"
        Square150x150Logo="Square150x150Logo.png" Square44x44Logo="Square44x44Logo.png" />
    </Application>
  </Applications>
</Package>
"""
    return text.encode("utf-8")


def same_manifest(embedded: bytes, rendered: bytes) -> bool:
    """Whether two manifests hold the same elements, attributes and text, ignoring layout whitespace.

    Tauri's resource step rewrites the manifest's line breaks and indentation as spaces.
    """

    def shape(element: Element) -> tuple[object, ...]:
        return (
            element.tag,
            sorted(element.attrib.items()),
            (element.text or "").strip(),
            (element.tail or "").strip(),
            [shape(child) for child in element],
        )

    return shape(ElementTree.fromstring(embedded.strip())) == shape(ElementTree.fromstring(rendered.strip()))


def _powershell(script: str, **values: str) -> str:
    import winreg

    system = Path(winreg.ExpandEnvironmentStrings("%SystemRoot%"))
    executable = system / "System32/WindowsPowerShell/v1.0/powershell.exe"
    # Values travel as CADRUMO_PACKAGE_* environment variables, never interpolated into the script.
    environment = os.environ | {f"CADRUMO_PACKAGE_{name.upper()}": value for name, value in values.items()}
    result = run_command(
        [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=system,
        environment=environment,
        timeout_seconds=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"PowerShell exited {result.returncode}")
    return result.stdout


def _developer_mode() -> bool:
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AllowDevelopmentWithoutDevLicense")
    except OSError:
        return False
    return value == 1


def _registration(build: Path) -> tuple[DistributionIdentity, Path, Path, Path, str]:
    paths = build_paths(require_enrolled_build(build))
    product = DistributionIdentity(**json.loads((paths["generated"] / "identity.json").read_text(encoding="utf-8")))
    layout = load_layout(None)
    image = desktop_image(layout)
    if image is None:
        raise ValueError("The Windows layout declares no desktop image")
    stage = paths["stage"] / DEVELOPMENT_CONFIG / "app"
    directory = paths["generated"] / "package-identity" / DEVELOPMENT_CONFIG
    return product, paths["generated"], stage, directory, image.package_path


def _remove(product: DistributionIdentity) -> list[str]:
    script = (
        "$ErrorActionPreference = 'Stop'; Get-AppxPackage -Name $env:CADRUMO_PACKAGE_NAME |"
        " Where-Object { $_.Publisher -eq $env:CADRUMO_PACKAGE_PUBLISHER } |"
        " ForEach-Object { Remove-AppxPackage -Package $_.PackageFullName; $_.PackageFullName }"
    )
    output = _powershell(
        script, name=product.windows_package_name, publisher=product.windows_package_development_publisher
    )
    return [line for line in output.splitlines() if line.strip()]


def register(build: Path) -> str:
    """Loosely register the Debug stage tree as the channel's development package."""
    if not _developer_mode():
        raise RuntimeError("Developer mode is off; enable it in Windows Settings to register a development build")
    product, generated, stage, directory, executable = _registration(build)
    desktop = stage / executable
    if not desktop.is_file():
        raise FileNotFoundError(f"Build the Debug stage first; missing {desktop}")
    expected = generated / application_manifest_name("desktop", "development")
    if not same_manifest(embedded_manifest(desktop), expected.read_bytes()):
        raise ValueError(f"{desktop} does not embed {expected}; rebuild the Debug stage")
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "AppxManifest.xml"
    write_bytes(
        manifest,
        package_manifest(product, publisher=product.windows_package_development_publisher, executable=executable),
    )
    with Image.open(generated / "cadrumo.ico") as icon:
        source = icon.copy()
    for name, size in LOGOS.items():
        logo = source.resize((size, size), Image.Resampling.LANCZOS)
        logo.save(directory / f"{name}.png", format="PNG")
    _remove(product)
    script = (
        "$ErrorActionPreference = 'Stop';"
        " Add-AppxPackage -Register $env:CADRUMO_PACKAGE_MANIFEST -ExternalLocation $env:CADRUMO_PACKAGE_LOCATION;"
        " (Get-AppxPackage -Name $env:CADRUMO_PACKAGE_NAME).PackageFullName"
    )
    return _powershell(script, manifest=str(manifest), location=str(stage), name=product.windows_package_name).strip()


def remove(build: Path) -> list[str]:
    """Remove the channel's development package registration, if any."""
    product, *_ = _registration(build)
    return _remove(product)


def main() -> None:
    """Register or remove the development package for an enrolled build's Debug stage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "remove"))
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Windows package identity registration requires Windows")
    if args.action == "register":
        print(f"Registered {register(args.build)}")
    else:
        removed = remove(args.build)
        print("\n".join(f"Removed {name}" for name in removed) or "No development package was registered")


if __name__ == "__main__":
    main()
