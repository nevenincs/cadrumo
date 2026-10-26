// Build-script support shared by the Windows images built from Cargo: the build identity of
// the image's component and `.res` serialization of numbered resources, including a
// `VS_VERSIONINFO` block. Build scripts `include!` this file; it is not a module of any crate.

const RT_VERSION: u16 = 16;
const VS_VERSION_INFO: u16 = 1;
// MOVEABLE | PURE and en-US, as the resource compiler writes them by default.
const RESOURCE_MEMORY_FLAGS: u16 = 0x0030;
const RESOURCE_LANGUAGE: u16 = 0x0409;
const RESOURCE_HEADER_SIZE: u32 = 32;
// VS_FIXEDFILEINFO fields of a Windows application or DLL.
const VS_FFI_SIGNATURE: u32 = 0xFEEF_04BD;
const VS_FFI_STRUCVERSION: u32 = 0x0001_0000;
const VS_FFI_FILEFLAGSMASK: u32 = 0x0000_003F;
const VOS_NT_WINDOWS32: u32 = 0x0004_0004;
const VFT_APP: u32 = 0x0000_0001;
#[allow(dead_code, reason = "only images that build a DLL name this file type")]
const VFT_DLL: u32 = 0x0000_0002;
// en-US strings in UTF-16 (code page 1200); the Translation entry declares the same pair.
const STRING_TABLE: &str = "040904b0";
const CODE_PAGE_UTF16: u16 = 1200;

/// The build identity of one component: the build resolves its id and sequence from the
/// component's input fingerprint (`CADRUMO_<COMPONENT>_BUILD_ID`, `..._BUILD_SEQUENCE`), and
/// Cargo's profile is the build type. Only the build of the component's own images reads it
/// (`CADRUMO_IMAGE_COMPONENT` names that component); linked as a library into another image
/// the crate reads no identity, so a moving identity never rebuilds the images that link it.
struct BuildIdentity {
    version: String,
    build_id: String,
    build_sequence: u16,
    build_type: &'static str,
}

impl BuildIdentity {
    /// The identity of `component` when this build produces its images, otherwise `None`.
    fn for_image(component: &str) -> Option<Self> {
        println!("cargo:rerun-if-env-changed=CADRUMO_IMAGE_COMPONENT");
        (std::env::var("CADRUMO_IMAGE_COMPONENT").as_deref() == Ok(component))
            .then(|| Self::from_projection(&component.to_uppercase()))
    }

    fn from_projection(component: &str) -> Self {
        let sequence_name = format!("CADRUMO_{component}_BUILD_SEQUENCE");
        let sequence = projected(&sequence_name);
        Self {
            version: projected("CADRUMO_ID_VERSION"),
            build_id: projected(&format!("CADRUMO_{component}_BUILD_ID")),
            build_sequence: sequence
                .parse()
                .ok()
                .filter(|&value| value > 0)
                .unwrap_or_else(|| panic!("{sequence_name} must be 1 to 65535: {sequence}")),
            build_type: match std::env::var("PROFILE").as_deref() {
                Ok("debug") => "debug",
                _ => "release",
            },
        }
    }

    /// `{version}+{build_id}`, with a `.debug` suffix for a debug build.
    fn display_version(&self) -> String {
        let suffix = if self.build_type == "debug" {
            ".debug"
        } else {
            ""
        };
        format!("{}+{}{suffix}", self.version, self.build_id)
    }
}

/// Version-resource strings of one image.
struct VersionNames {
    product_name: String,
    file_description: String,
    original_filename: String,
    file_type: u32,
}

fn projected(name: &str) -> String {
    println!("cargo:rerun-if-env-changed={name}");
    let value = std::env::var(name)
        .unwrap_or_else(|_| panic!("{name} must come from the build's identity projection"));
    assert!(
        !value.is_empty() && !value.contains('\0'),
        "{name} must be a non-empty string without NUL"
    );
    value
}

/// Serialize a `VS_VERSIONINFO` block with the fixed version and the named strings.
fn version_info(names: &VersionNames, build: &BuildIdentity) -> Vec<u8> {
    let (most, least) = fixed_version(&build.version, build.build_sequence);
    let display = build.display_version();
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
        names.file_type,
        0, // dwFileSubtype
        0, // dwFileDateMS
        0, // dwFileDateLS
    ] {
        fixed.extend_from_slice(&field.to_le_bytes());
    }
    let strings = [
        ("FileDescription", names.file_description.as_str()),
        ("FileVersion", display.as_str()),
        ("OriginalFilename", names.original_filename.as_str()),
        ("ProductName", names.product_name.as_str()),
        ("ProductVersion", build.version.as_str()),
        ("BuildId", build.build_id.as_str()),
        ("BuildType", build.build_type),
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

/// Pack `major.minor.patch.sequence` into the `VS_FIXEDFILEINFO` most and least significant words.
fn fixed_version(version: &str, sequence: u16) -> (u32, u32) {
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
        (u32::from(patch) << 16) | u32::from(sequence),
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
