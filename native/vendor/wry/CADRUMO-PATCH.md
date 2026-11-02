# Cadrumo Wry patch

This directory vendors Wry 0.57.1 from its published crates.io crate, copied from the local Cargo registry cache. Cargo's local registry metadata files `.cargo-ok` and `.cargo_vcs_info.json` are excluded.

The published crate checksum is `759c50ddad0ef9913bb5496cb9d509a50433a3b78cb0238d61105526589cf0e9`.

The local change in `src/wkwebview/navigation.rs` applies the navigation callback to main-frame and missing-target-frame requests, while allowing iframe requests to proceed under the embedding document's Content Security Policy. Wry 0.57.1 otherwise invokes Tauri's top-level navigation callback for iframe loads too, cancelling the isolated documentation frame on macOS. Download handling is unchanged.

Cadrumo retains its strict top-level shell-origin allowlist and its exact documentation-origin `frame-src` policy. Remove this override when the pinned upstream dependency implements the same frame boundary, after native macOS documentation navigation is verified.
