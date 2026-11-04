# Cadrumo Wry patch

This directory vendors Wry 0.57.1 from its published crates.io crate, copied from the local Cargo registry cache. Cargo's local registry metadata files `.cargo-ok` and `.cargo_vcs_info.json` are excluded.

The published crate checksum is `759c50ddad0ef9913bb5496cb9d509a50433a3b78cb0238d61105526589cf0e9`.

The local change in `src/wkwebview/navigation.rs` applies the navigation callback to main-frame and missing-target-frame requests, while allowing iframe requests to proceed under the embedding document's Content Security Policy. Wry 0.57.1 otherwise invokes Tauri's top-level navigation callback for iframe loads too, cancelling the isolated documentation frame on macOS. Download handling is unchanged.

Cadrumo retains its strict top-level shell-origin allowlist and its exact documentation-origin `frame-src` policy. Remove this override when the pinned upstream dependency implements the same frame boundary, after native macOS documentation navigation is verified.

The standalone crate lock updates `time` from 0.3.45 to 0.3.55, with its required
companion packages, to clear RUSTSEC-2026-0009. The desktop dependency graph
already pins 0.3.55 in its own lock; this change covers the vendored crate's
independent lock without changing Wry's dependency declarations or source.

The development/example dependency graph migrates from wgpu 23 to 29.0.4,
with an API port of `examples/wgpu.rs` that retains its surface rendering and
transparent child-WebView overlay. Winit remains on 0.30 with explicit `rwh_06`,
X11, Wayland and Wayland dlopen features; its Adwaita CSD title renderer uses
crossfont instead of ab_glyph. Title text, all examples and all GPU backends
remain enabled. This removes the standalone lock's `paste` and `ttf-parser`
dependency paths without changing Wry's library API or navigation patch.

wgpu 29 development checks require Rust 1.87 or newer. The retained standalone
`time` 0.3.55 graph already requires Rust 1.88, including through the normal
library dependency on cookie; Cadrumo's declared Rust 1.96.0 toolchain meets both
floors. Wry's upstream `rust-version = "1.85"` metadata is retained, but Rust 1.85
compatibility of this lock is not claimed or verified. Linux/BSD crossfont title
rendering requires pkg-config and fontconfig development metadata/libraries;
provide FreeType development headers/libraries too, or validate freetype-sys's
bundled FreeType fallback. Native non-Windows compilation and graphical title
and overlay behavior require separate platform verification.
