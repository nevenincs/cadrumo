"""One desktop-only Linux runtime envelope and native package requirement projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from dev._paths import REPO_ROOT

from .build_directory import require_enrolled_output
from .hashing import digest
from .layout import application_images, load_layout

POLICY = "gtk3-webkit41-v1"
MANIFEST = "data/linux-desktop-runtime.json"


# Semantic TOML identities for the reviewed locked graph and its owned feature
# declarations. This conservative drift fence is not compiled-symbol evidence.
# Comments/line endings do not change dependency semantics. Refresh only together
# with resolved feature/provider evidence; imported APIs still require artifact proof.
DEPENDENCY_INPUTS = {
    # The desktop now depends directly on the local platform crate for Linux. That
    # crate has no default features or Linux-target native dependencies; WebView2
    # remains enabled only by the Windows-target dependency. Direct ureq use also
    # adds no features, preserving the reviewed GTK/WebKit provider envelope. The linked
    # interpreter host and launch guard are Windows-target dependencies only.
    # tauri-plugin-dialog 2.8.3 selects rfd 0.16's GTK3 backend with its defaults
    # disabled: gtk-sys 0.18/v3_24 stays inside GTK 3.24; no portal backend is
    # enabled. All 13 locked native sys-crates retain their versions, checksums
    # and dependency edges. Direct sha2 was already enabled by the application.
    # The application crate's provisioning dependencies (rustls with ring, webpki-roots,
    # flate2 with zlib-rs, ruzstd, tar, toml, zeroize, sha2 0.11) are pure Rust or
    # statically linked: the Linux-target graph gains no sys-crate, and the platform crate
    # reaches only libc there. The locked GTK/WebKit sys-crates and rfd's GTK3-only backend
    # are unchanged (rfd 0.16.1; no ashpd). A direct `log` dependency was added
    # to the desktop crate; it is pure Rust and does not alter native providers.
    # The diagnostics test-support feature is empty and is selected only by tests;
    # the distributed desktop still selects only application/platform. Desktop `log`
    # is pure Rust. The refreshed lock and manifest digests bind both changes; neither
    # adds a native dependency or distributed feature, so provider evidence remains valid.
    # This is source/feature evidence, not new artifact or minimum-host proof.
    # The desktop now links the interpreter host on every unix target, Linux included. That
    # crate adds only the locked launch-guard and platform path dependencies and a C
    # build-dependency that compiles the posix host into the binary; the lock is unchanged
    # and no sys-crate, provider feature or Linux native library is added. The host's
    # dlopen use needs only the C library, which the packaged image already requires.
    # A Linux build of the linked binary remains unproven by this fence.
    # The manager dependency added under cfg(target_os = "macos") is absent from
    # Linux's production/build graph. Native Linux `cargo tree --locked --offline
    # --target <triple> -e normal,build,features` is unchanged for both enrolled
    # Linux architectures from the previously bound desktop manifest, including
    # native provider features.
    # Reviewed against manifest 3b7aac40d8 and lock 32fd3a4072 with cargo tree
    # --locked --offline --target <triple> -e normal,build,features for both
    # x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu. The only added
    # resolved Linux feature is tokio/signal: tokio 1.54.1 already enables all
    # its Unix dependency features through process (libc, mio/net, mio/os-ext,
    # mio/os-poll, signal-hook-registry). No package or native provider feature
    # changes. Non-root lock records are identical; the root only adds macOS
    # objc2 dependencies. This refresh admits source drift, not new imported
    # symbol or minimum-host proof; the native artifact restrictions still apply.
    "native/desktop/src-tauri/Cargo.lock": "224974233ee997aac6a3fef5aa635569fb1f35b4d2ef5bfa46e8329895fb40b6",
    "native/desktop/src-tauri/Cargo.toml": "ff6c01cda3117130e4a563fc71d30d59b34e128d7090793aa1964952b0e85126",
    "native/application/Cargo.toml": "45b431600a5da6caa057865bdb39afc3aae4f9512d51d598f9d04e380cc03499",
    "native/platform/Cargo.toml": "45e633cefce86ce0a233670b94839e23bca14aba65b8d1c3b870718f50d01c37",
}


def validate_dependency_inputs(root: Path = REPO_ROOT) -> None:
    """Refuse dependency or owned feature drift until runtime policy is re-evidenced."""
    for name, expected in DEPENDENCY_INPUTS.items():
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Linux desktop dependency evidence input is missing or linked: {name}")
        value = tomllib.loads(path.read_text(encoding="utf-8"))
        content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"Linux desktop dependency evidence requires refresh: {name}")


@dataclass(frozen=True)
class Requirement:
    """An API family, exact imported library names and native runtime providers."""

    api: str
    minimum: str | None
    sonames: tuple[str, ...]
    deb: tuple[str, ...]
    rpm: str


# Bounds conservatively combine locked sys-crate features and Debian provider symbol
# metadata for the built image. WebKit uses the first stable API release (2.42),
# not Debian's prerelease provider floor (2.41.90). Provider floors do not prove
# upstream API history or graphical operation on a minimum supported host.
REQUIREMENTS = (
    Requirement("gtk3", "3.24", ("libgtk-3.so.0", "libgdk-3.so.0"), ("libgtk-3-0", "libgtk-3-0t64"), "gtk3"),
    Requirement(
        "glib",
        "2.70",
        ("libglib-2.0.so.0", "libgobject-2.0.so.0", "libgio-2.0.so.0"),
        ("libglib2.0-0", "libglib2.0-0t64"),
        "glib2",
    ),
    Requirement("webkitgtk4.1", "2.42", ("libwebkit2gtk-4.1.so.0",), ("libwebkit2gtk-4.1-0",), "webkit2gtk4.1"),
    Requirement(
        "javascriptcoregtk4.1",
        "2.38",
        ("libjavascriptcoregtk-4.1.so.0",),
        ("libjavascriptcoregtk-4.1-0",),
        "javascriptcoregtk4.1",
    ),
    Requirement("soup3", "3.0.3", ("libsoup-3.0.so.0",), ("libsoup-3.0-0",), "libsoup3"),
    Requirement("cairo", "1.14", ("libcairo.so.2",), ("libcairo2",), "cairo"),
    Requirement("cairo-gobject", "1.14", ("libcairo-gobject.so.2",), ("libcairo-gobject2",), "cairo-gobject"),
    Requirement("pango", "1.40", ("libpango-1.0.so.0",), ("libpango-1.0-0",), "pango"),
    Requirement("gdk-pixbuf", "2.36.9", ("libgdk_pixbuf-2.0.so.0",), ("libgdk-pixbuf-2.0-0",), "gdk-pixbuf2"),
    Requirement("dbus", "1.9.14", ("libdbus-1.so.3",), ("libdbus-1-3",), "dbus-libs"),
)


def desktop_path(layout: dict[str, Any]) -> str | None:
    """Admit the exact canonical desktop image, never another image with its flag copied."""
    policy = layout.get("linux_desktop_runtime")
    if policy is None:
        return None
    if policy != POLICY or layout.get("platform") not in {"linux-x86-64", "linux-aarch64"}:
        raise ValueError("Unknown Linux desktop runtime policy or target")
    images = [image for image in application_images(layout) if image.desktop]
    if len(images) != 1:
        raise ValueError("Linux desktop runtime policy requires one enrolled desktop image")
    image = images[0]
    canonical = next(item for item in application_images(load_layout(layout["platform"])) if item.desktop)
    if (image.package_path, image.target, image.artifact) != (
        canonical.package_path,
        canonical.target,
        canonical.artifact,
    ):
        raise ValueError("Linux desktop runtime policy is not bound to the canonical desktop image")
    return image.package_path


def external_sonames(layout: dict[str, Any], root: Path) -> frozenset[str]:
    """Return external libraries only when this payload actually includes the enrolled image."""
    image = desktop_path(layout)
    if image is None or not (root / image).is_file():
        return frozenset[str]()
    return frozenset(name for requirement in REQUIREMENTS for name in requirement.sonames)


def declaration(layout: dict[str, Any]) -> dict[str, Any]:
    """Describe prerequisites separately from unproven minimum-host compatibility."""
    image = desktop_path(layout)
    if image is None:
        raise ValueError("Linux desktop runtime policy is not enrolled")
    validate_dependency_inputs()
    return {
        "schema": 1,
        "policy": POLICY,
        "platform": layout["platform"],
        "image": image,
        "delivery": "distribution-managed",
        "minimum_host_verified": False,
        "requirements": [asdict(requirement) for requirement in REQUIREMENTS],
        "dependency_inputs": DEPENDENCY_INPUTS,
        "pending_evidence": ["dbus-api-history", "minimum-provider-symbols", "native-graphical-acceptance"],
    }


def stage(root: Path, layout: dict[str, Any]) -> None:
    """Write ordinary inventory-bound metadata before the package inventory is sealed."""
    if external_sonames(layout, root):
        path = root / MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(declaration(layout), indent=2) + "\n", encoding="utf-8")


def _validate_desktop_manifest(path: Path, layout: dict[str, object], target: str, files: dict[str, str]) -> None:
    if layout["platform"] != target:
        raise ValueError("Linux desktop prerequisite target differs from payload")
    if not path.is_file() or path.is_symlink() or digest(path) != files.get(MANIFEST):
        raise ValueError("Linux desktop prerequisite manifest is missing or modified")
    if json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(declaration(layout))):
        raise ValueError("Linux desktop prerequisite manifest differs from canonical policy")


def _declares_desktop(layout: dict[str, object], target: str, files: dict[str, str]) -> bool:
    canonical = next(item for item in application_images(load_layout(target)) if item.desktop)
    desktop = canonical.package_path in files or any(
        item.desktop and item.package_path in files for item in application_images(layout)
    )
    return desktop


def validate_payload(root: Path, manifest: dict[str, Any]) -> bool:
    """Check the metadata bytes and exact image association against the canonical policy."""
    layout = manifest["layout"]
    if not manifest["build"]["target"].startswith("linux-"):
        return False
    image = desktop_path(layout)
    desktop = _declares_desktop(layout, manifest["build"]["target"], manifest["files"])
    if desktop and image is None:
        raise ValueError("Linux desktop payload lacks its canonical runtime policy")
    path = root / MANIFEST
    if not desktop:
        if path.exists() or MANIFEST in manifest["files"]:
            raise ValueError("Runtime-only payload contains desktop prerequisite metadata")
        return False
    _validate_desktop_manifest(path, layout, manifest["build"]["target"], manifest["files"])
    return True


def package_requirements(package_format: Literal["deb", "rpm"]) -> tuple[str, ...]:
    """Project explicit provider alternatives with the same bound on every branch."""
    if package_format not in {"deb", "rpm"}:
        raise ValueError("Unsupported Linux dependency format")
    clauses: list[str] = []
    for requirement in REQUIREMENTS:
        if package_format == "deb":
            suffix = f" (>= {requirement.minimum})" if (requirement.minimum is not None and requirement.minimum) else ""
            clauses.append(" | ".join(name + suffix for name in requirement.deb))
        else:
            clauses.append(
                requirement.rpm
                + (f" >= {requirement.minimum}" if (requirement.minimum is not None and requirement.minimum) else "")
            )
    return tuple(clauses)


def verify_requirements(observed: str, package_format: Literal["deb", "rpm"]) -> None:
    """Require the explicit policy clauses; automatic extra dependencies are permitted.

    Exact clauses deliberately avoid implementing Debian/RPM version comparison.
    Even a stronger generated replacement requires an explicit policy update.
    """
    separator = "," if package_format == "deb" else "\n"
    clauses = {" ".join(clause.split()) for clause in observed.split(separator)}
    if not set(package_requirements(package_format)) <= clauses:
        raise ValueError("Native package lacks canonical Linux desktop runtime dependencies")


def main() -> None:
    """Generate CPack dependency inputs from the exact assembled payload."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=require_enrolled_output, required=True)
    arguments = parser.parse_args()
    manifest = json.loads((arguments.payload / "data/package-manifest.json").read_text(encoding="utf-8"))
    included = validate_payload(arguments.payload, manifest)
    lines: list[str] = []
    for package_format in ("deb", "rpm"):
        value = ", ".join(package_requirements(package_format)) if included else ""
        lines.append(f"set(CADRUMO_LINUX_{package_format.upper()}_DESKTOP_DEPENDS [=[{value}]=])")
    arguments.output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
