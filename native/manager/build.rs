//! Windows linkage for the manager image.
//!
//! The image embeds the canonical native-host process manifest unchanged as resource 1,
//! because linker manifest merging rewrites the document and can discard compatibility
//! entries. The manager binary also carries a version resource named from the identity
//! projection, which the shell shows for the image, for example in Task Manager's
//! startup list. Both are serialized here as `.res` files, so the build needs no
//! resource compiler. Load-time imports resolve from System32 only, like the C hosts.

use std::{env, fs, path::PathBuf};

const RT_MANIFEST: u16 = 24;
const RT_VERSION: u16 = 16;
const CREATEPROCESS_MANIFEST_RESOURCE_ID: u16 = 1;
const VS_VERSION_INFO: u16 = 1;
// MOVEABLE | PURE and en-US, as the resource compiler writes them by default.
const RESOURCE_MEMORY_FLAGS: u16 = 0x0030;
const RESOURCE_LANGUAGE: u16 = 0x0409;
const RESOURCE_HEADER_SIZE: u32 = 32;

/// The Cargo binary that is the packaged manager image; other binaries keep no version resource.
const MANAGER_BINARY: &str = "cadrumo-manager";
// VS_FIXEDFILEINFO fields of a released Windows application.
const VS_FFI_SIGNATURE: u32 = 0xFEEF_04BD;
const VS_FFI_STRUCVERSION: u32 = 0x0001_0000;
const VS_FFI_FILEFLAGSMASK: u32 = 0x0000_003F;
const VOS_NT_WINDOWS32: u32 = 0x0004_0004;
const VFT_APP: u32 = 0x0000_0001;
// en-US strings in UTF-16 (code page 1200); the Translation entry declares the same pair.
const STRING_TABLE: &str = "040904b0";
const CODE_PAGE_UTF16: u16 = 1200;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let target_env = env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
    if target_os != "windows" || target_env != "msvc" {
        return;
    }
    let crate_root =
        PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").expect("Cargo sets CARGO_MANIFEST_DIR"));
    let out_dir = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo sets OUT_DIR"));
    let manifest = crate_root.join("../interpreter/windows/host.manifest");
    println!("cargo:rerun-if-changed={}", manifest.display());
    let document = fs::read(&manifest).expect("read the canonical native-host process manifest");
    let manifest_resource = out_dir.join("manager-manifest.res");
    fs::write(
        &manifest_resource,
        resource_file(&[(RT_MANIFEST, CREATEPROCESS_MANIFEST_RESOURCE_ID, &document)]),
    )
    .expect("write the manifest resource");
    let version_resource = out_dir.join("manager-version.res");
    let version_info = version_info(&VersionNames::from_projection());
    fs::write(
        &version_resource,
        resource_file(&[(RT_VERSION, VS_VERSION_INFO, &version_info)]),
    )
    .expect("write the version resource");
    // The resource is the only manifest; a linker-generated one would duplicate resource 1.
    println!("cargo:rustc-link-arg-bins=/MANIFEST:NO");
    // LOAD_LIBRARY_SEARCH_SYSTEM32: the image sits at the package root beside other DLLs.
    println!("cargo:rustc-link-arg-bins=/DEPENDENTLOADFLAG:0x800");
    println!("cargo:rustc-link-arg-bins={}", manifest_resource.display());
    println!(
        "cargo:rustc-link-arg-bin={MANAGER_BINARY}={}",
        version_resource.display()
    );
}

/// Version-resource strings, each taken from the distribution identity projection.
struct VersionNames {
    version: String,
    product_name: String,
    file_description: String,
    original_filename: String,
}

impl VersionNames {
    fn from_projection() -> Self {
        Self {
            version: projected("CADRUMO_ID_VERSION"),
            product_name: projected("CADRUMO_ID_NAME"),
            file_description: projected("CADRUMO_ID_MANAGER_NAME"),
            original_filename: format!("{MANAGER_BINARY}.exe"),
        }
    }
}

fn projected(name: &str) -> String {
    println!("cargo:rerun-if-env-changed={name}");
    let value = env::var(name)
        .unwrap_or_else(|_| panic!("{name} must come from the distribution identity projection"));
    assert!(
        !value.is_empty() && !value.contains('\0'),
        "{name} must be a non-empty string without NUL"
    );
    value
}

/// Serialize a `VS_VERSIONINFO` block with the fixed version and the named strings.
fn version_info(names: &VersionNames) -> Vec<u8> {
    let (most, least) = fixed_version(&names.version);
    let mut fixed = Vec::with_capacity(52);
    for field in [
        VS_FFI_SIGNATURE,
        VS_FFI_STRUCVERSION,
        most, // dwFileVersionMS
        least,
        most, // dwProductVersionMS
        least,
        VS_FFI_FILEFLAGSMASK,
        0, // dwFileFlags: a release image
        VOS_NT_WINDOWS32,
        VFT_APP,
        0, // dwFileSubtype
        0, // dwFileDateMS
        0, // dwFileDateLS
    ] {
        fixed.extend_from_slice(&field.to_le_bytes());
    }
    let strings = [
        ("FileDescription", names.file_description.as_str()),
        ("FileVersion", names.version.as_str()),
        ("OriginalFilename", names.original_filename.as_str()),
        ("ProductName", names.product_name.as_str()),
        ("ProductVersion", names.version.as_str()),
    ]
    .map(|(key, text)| {
        let value = utf16z(text);
        let units = u16::try_from(value.len() / 2).expect("a version string fits a block");
        version_block(key, &value, units, true, &[])
    });
    let string_table = version_block(STRING_TABLE, &[], 0, true, &strings);
    let string_file_info = version_block("StringFileInfo", &[], 0, true, &[string_table]);
    let mut translation = Vec::with_capacity(4);
    translation.extend_from_slice(&RESOURCE_LANGUAGE.to_le_bytes());
    translation.extend_from_slice(&CODE_PAGE_UTF16.to_le_bytes());
    let var = version_block("Translation", &translation, 4, false, &[]);
    let var_file_info = version_block("VarFileInfo", &[], 0, true, &[var]);
    version_block(
        "VS_VERSION_INFO",
        &fixed,
        52,
        false,
        &[string_file_info, var_file_info],
    )
}

/// Pack `major.minor.patch` into the `VS_FIXEDFILEINFO` most and least significant words.
fn fixed_version(version: &str) -> (u32, u32) {
    let parts: Vec<u16> = version
        .split('.')
        .map(|part| {
            part.parse()
                .unwrap_or_else(|_| panic!("{version} is not a numeric major.minor.patch version"))
        })
        .collect();
    let [major, minor, patch] = parts[..] else {
        panic!("{version} is not a numeric major.minor.patch version");
    };
    (
        (u32::from(major) << 16) | u32::from(minor),
        u32::from(patch) << 16,
    )
}

/// One version block: length, value length, type, key, then the value and each child,
/// each starting on a 32-bit boundary. The length covers the block up to its last byte.
fn version_block(
    key: &str,
    value: &[u8],
    value_length: u16,
    text: bool,
    children: &[Vec<u8>],
) -> Vec<u8> {
    let mut block = vec![0; 6];
    block.extend_from_slice(&utf16z(key));
    align(&mut block);
    block.extend_from_slice(value);
    for child in children {
        align(&mut block);
        block.extend_from_slice(child);
    }
    let length = u16::try_from(block.len()).expect("a version block fits 64 KiB");
    block[0..2].copy_from_slice(&length.to_le_bytes());
    block[2..4].copy_from_slice(&value_length.to_le_bytes());
    block[4..6].copy_from_slice(&u16::from(text).to_le_bytes());
    block
}

fn utf16z(text: &str) -> Vec<u8> {
    text.encode_utf16()
        .chain([0])
        .flat_map(u16::to_le_bytes)
        .collect()
}

fn align(bytes: &mut Vec<u8>) {
    bytes.resize(bytes.len().next_multiple_of(4), 0);
}

/// Serialize a 32-bit `.res` file holding numbered resources, which the linker converts.
fn resource_file(resources: &[(u16, u16, &[u8])]) -> Vec<u8> {
    let mut file = Vec::new();
    // An empty leading entry marks the file as a 32-bit resource file.
    resource_entry(&mut file, 0, 0, 0, 0, &[]);
    for &(kind, name, data) in resources {
        resource_entry(
            &mut file,
            kind,
            name,
            RESOURCE_MEMORY_FLAGS,
            RESOURCE_LANGUAGE,
            data,
        );
    }
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
    let size = u32::try_from(data.len()).expect("the resource data fits a resource");
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
    align(file);
}
