"""The package manifest claims exactly the identity every Cadrumo image embeds."""

from __future__ import annotations

from dataclasses import replace

import pytest
from defusedxml import ElementTree

from dev.packaging.native.identity import identity
from dev.packaging.native.package_identity import package_manifest, same_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

FOUNDATION = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"
UAP = "{http://schemas.microsoft.com/appx/manifest/uap/windows10}"
UAP10 = "{http://schemas.microsoft.com/appx/manifest/uap/windows10/10}"
RESCAP = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities}"


@pytest.mark.parametrize("channel", ["stable", "preview"])
def test_package_manifest_declares_the_channel_identity_with_external_content(channel: str) -> None:
    product = identity("windows-x86-64", channel)
    document = ElementTree.fromstring(
        package_manifest(product, publisher=product.windows_package_development_publisher, executable="cadrumo.exe")
    )
    assert document.find(f"{FOUNDATION}Identity").attrib == {
        "Name": product.windows_package_name,
        "Publisher": "CN=Cadrumo Development",
        "Version": product.windows_package_version,
        "ProcessorArchitecture": "neutral",
    }
    properties = document.find(f"{FOUNDATION}Properties")
    assert properties.findtext(f"{FOUNDATION}DisplayName") == product.name
    assert properties.findtext(f"{UAP10}AllowExternalContent") == "true"
    assert {item.get("Name") for item in document.iter(f"{RESCAP}Capability")} == {
        "runFullTrust",
        "unvirtualizedResources",
    }
    (application,) = document.iter(f"{FOUNDATION}Application")
    assert application.attrib == {
        "Id": "Cadrumo",
        "Executable": "cadrumo.exe",
        f"{UAP10}TrustLevel": "mediumIL",
        f"{UAP10}RuntimeBehavior": "win32App",
    }
    assert application.find(f"{UAP}VisualElements").get("AppListEntry") == "none"


def test_package_manifest_escapes_projected_text() -> None:
    product = replace(identity("windows-x86-64"), name="A & <B>", description='Say "hi"')
    document = ElementTree.fromstring(package_manifest(product, publisher="CN=X", executable="dir/a&b.exe"))
    assert document.find(f"{FOUNDATION}Properties").findtext(f"{FOUNDATION}DisplayName") == "A & <B>"
    (application,) = document.iter(f"{FOUNDATION}Application")
    assert application.get("Executable") == "dir/a&b.exe"
    assert application.find(f"{UAP}VisualElements").get("Description") == 'Say "hi"'


RENDERED = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0"
        processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*" />
    </dependentAssembly>
  </dependency>
  <msix xmlns="urn:schemas-microsoft-com:msix.v1" publisher="CN=Cadrumo Development"
    packageName="md.neve.cadrumo" applicationId="Cadrumo" />
</assembly>
"""
# Tauri's resource step embeds the manifest with each line break and indentation run as one space.
EMBEDDED = (
    b' <?xml version="1.0" encoding="UTF-8" standalone="yes"?>  <assembly xmlns="urn:schemas-microsoft-com:asm.v1"'
    b' manifestVersion="1.0">  <dependency>  <dependentAssembly>  <assemblyIdentity type="win32"'
    b' name="Microsoft.Windows.Common-Controls" version="6.0.0.0"  processorArchitecture="*"'
    b' publicKeyToken="6595b64144ccf1df" language="*" />  </dependentAssembly>  </dependency>'
    b'  <msix xmlns="urn:schemas-microsoft-com:msix.v1" publisher="CN=Cadrumo Development"'
    b' packageName="md.neve.cadrumo" applicationId="Cadrumo" />  </assembly> '
)


def test_same_manifest_ignores_the_layout_tauri_rewrites() -> None:
    assert same_manifest(EMBEDDED, RENDERED)


@pytest.mark.parametrize(
    ("original", "changed"),
    [
        (b'publisher="CN=Cadrumo Development"', b'publisher="CN=Neve Nincs"'),
        (b'packageName="md.neve.cadrumo"', b'packageName="md.neve.cadrumo.preview"'),
        (
            b'  <msix xmlns="urn:schemas-microsoft-com:msix.v1" publisher="CN=Cadrumo Development"'
            b' packageName="md.neve.cadrumo" applicationId="Cadrumo" />',
            b"",
        ),
    ],
)
def test_same_manifest_refuses_a_different_identity_claim(original: bytes, changed: bytes) -> None:
    assert original in EMBEDDED
    assert not same_manifest(EMBEDDED.replace(original, changed), RENDERED)
