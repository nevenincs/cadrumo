//! Windows linkage for the manager image.
//!
//! The image embeds the canonical native-host process manifest unchanged as resource 1,
//! because linker manifest merging rewrites the document and can discard compatibility
//! entries. It also resolves load-time imports from System32 only, like the C hosts.

use std::{env, fs, path::PathBuf};

const RT_MANIFEST: u16 = 24;
const CREATEPROCESS_MANIFEST_RESOURCE_ID: u16 = 1;
// MOVEABLE | PURE and en-US, as the resource compiler writes them by default.
const MANIFEST_MEMORY_FLAGS: u16 = 0x0030;
const MANIFEST_LANGUAGE: u16 = 0x0409;
const RESOURCE_HEADER_SIZE: u32 = 32;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let target_env = env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
    if target_os != "windows" || target_env != "msvc" {
        return;
    }
    let crate_root =
        PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").expect("Cargo sets CARGO_MANIFEST_DIR"));
    let manifest = crate_root.join("../interpreter/windows/host.manifest");
    println!("cargo:rerun-if-changed={}", manifest.display());
    let document = fs::read(&manifest).expect("read the canonical native-host process manifest");
    let resource = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo sets OUT_DIR"))
        .join("manager-manifest.res");
    fs::write(&resource, resource_file(&document)).expect("write the manifest resource");
    // The resource is the only manifest; a linker-generated one would duplicate resource 1.
    println!("cargo:rustc-link-arg-bins=/MANIFEST:NO");
    // LOAD_LIBRARY_SEARCH_SYSTEM32: the image sits at the package root beside other DLLs.
    println!("cargo:rustc-link-arg-bins=/DEPENDENTLOADFLAG:0x800");
    println!("cargo:rustc-link-arg-bins={}", resource.display());
}

/// Serialize a 32-bit `.res` file holding one process manifest, which the linker converts.
fn resource_file(manifest: &[u8]) -> Vec<u8> {
    let mut file = Vec::new();
    // An empty leading entry marks the file as a 32-bit resource file.
    resource_entry(&mut file, 0, 0, 0, 0, &[]);
    resource_entry(
        &mut file,
        RT_MANIFEST,
        CREATEPROCESS_MANIFEST_RESOURCE_ID,
        MANIFEST_MEMORY_FLAGS,
        MANIFEST_LANGUAGE,
        manifest,
    );
    file
}

fn resource_entry(
    file: &mut Vec<u8>,
    kind: u16,
    name: u16,
    flags: u16,
    language: u16,
    data: &[u8],
) {
    let size = u32::try_from(data.len()).expect("the process manifest fits a resource");
    file.extend_from_slice(&size.to_le_bytes());
    file.extend_from_slice(&RESOURCE_HEADER_SIZE.to_le_bytes());
    // Numeric type and name ordinals, each introduced by 0xFFFF.
    for ordinal in [kind, name] {
        file.extend_from_slice(&0xFFFF_u16.to_le_bytes());
        file.extend_from_slice(&ordinal.to_le_bytes());
    }
    file.extend_from_slice(&0_u32.to_le_bytes()); // DataVersion
    file.extend_from_slice(&flags.to_le_bytes());
    file.extend_from_slice(&language.to_le_bytes());
    file.extend_from_slice(&0_u32.to_le_bytes()); // Version
    file.extend_from_slice(&0_u32.to_le_bytes()); // Characteristics
    file.extend_from_slice(data);
    file.resize(file.len().next_multiple_of(4), 0);
}
