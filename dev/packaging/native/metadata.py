"""Generate native build identity and Windows resources from canonical inputs."""

from __future__ import annotations

import argparse
import importlib
import io
import json
import sys
from pathlib import Path

from PIL import Image

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT


def generate(destination: Path, number: int, date: str, tools: Path) -> None:
    """Project identity, the existing favicon, and package filenames into resources."""
    sys.path.insert(0, str(tools))
    renderer = importlib.import_module("resvg_py")
    version = parse_toml((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    python = (REPO_ROOT / "dev/packaging/release-python-version").read_text().strip()
    layout = json.loads((REPO_ROOT / "native/package-layout.json").read_text(encoding="utf-8"))
    if not 0 <= number <= 65535:
        raise ValueError("Windows resource build number must be between 0 and 65535")
    destination.mkdir(parents=True, exist_ok=True)
    metadata = {
        "product": PRODUCT_IDENTITY.display_name,
        "version": version,
        "build_number": number,
        "build_date": date,
        "python": python,
        "layout_abi": layout["abi"],
    }
    (destination / "build.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    values = {
        "VERSION": version,
        "BUILD_NUMBER": str(number),
        "BUILD_DATE": date,
        **{name.upper(): value for name, value in layout["files"].items()},
    }
    header = "\n".join(f"#define CADRUMO_{name} {json.dumps(value)}" for name, value in values.items())
    (destination / "build_metadata.h").write_text(header + "\n", encoding="utf-8")
    png = renderer.svg_to_bytes(
        svg_path=str(REPO_ROOT / "docs/_static/cadrumo-favicon.svg"), width=256, height=256, skip_system_fonts=True
    )
    with Image.open(io.BytesIO(png)) as icon:
        icon.save(destination / "cadrumo.ico", format="ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    numeric = ",".join([*version.split(".")[:3], str(number)])
    resource = f'''#include <winver.h>
1 ICON "{(destination / "cadrumo.ico").as_posix()}"
1 VERSIONINFO
FILEVERSION {numeric}
PRODUCTVERSION {numeric}
FILEFLAGSMASK VS_FFI_FILEFLAGSMASK
#if CADRUMO_DEVELOPMENT
FILEFLAGS VS_FF_DEBUG
#else
FILEFLAGS 0
#endif
FILEOS VOS_NT_WINDOWS32
FILETYPE VFT_APP
BEGIN
 BLOCK "StringFileInfo"
 BEGIN
  BLOCK "040904b0"
  BEGIN
   VALUE "CompanyName", "CADRUMO\\0"
   VALUE "ProductName", "CADRUMO\\0"
   VALUE "FileDescription", "CADRUMO controlled Python interpreter\\0"
   VALUE "FileVersion", "{version}.{number}\\0"
   VALUE "ProductVersion", "{version}\\0"
   VALUE "BuildDate", "{date}\\0"
  END
 END
 BLOCK "VarFileInfo"
 BEGIN
  VALUE "Translation", 0x0409, 1200
 END
END
'''
    (destination / "interpreter.rc").write_text(resource, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--tools", type=Path, required=True)
    args = parser.parse_args()
    generate(args.destination, args.number, args.date, args.tools)
