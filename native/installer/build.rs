// The version resources share the manager's serializer and carry the installer component's identity.
include!("../manager/version_resource.rs");

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=../manager/version_resource.rs");
    // Only the installer image's own build reads its identity; linked into the manager or the
    // desktop as a library, the crate reads none and writes no version resources.
    let build = BuildIdentity::for_image("installer");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        // The installer extracts this DLL to its private temporary directory. Its
        // operating-system imports must still resolve exclusively from System32.
        println!("cargo:rustc-link-arg-cdylib=/DEPENDENTLOADFLAG:0x800");
        println!("cargo:rustc-link-arg-bins=/DEPENDENTLOADFLAG:0x800");
        let root = std::path::PathBuf::from(std::env::var_os("CARGO_MANIFEST_DIR").unwrap());
        let manifest = root.join("../interpreter/windows/host.manifest");
        println!("cargo:rerun-if-changed={}", manifest.display());
        let document = std::fs::read(manifest).expect("canonical asInvoker manifest");
        let mut resource = Vec::new();
        entry(&mut resource, 0, 0, &[]);
        entry(&mut resource, 24, 1, &document);
        let out_dir = std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap());
        let output = out_dir.join("installer-manifest.res");
        std::fs::write(&output, resource).expect("write installer process manifest");
        println!("cargo:rustc-link-arg-bins=/MANIFEST:NO");
        println!("cargo:rustc-link-arg-bins={}", output.display());
        if let Some(build) = &build {
            let product_name = projected("CADRUMO_ID_NAME");
            for (file_name, description, file_type, link) in [
                (
                    "cadrumo_installer.dll",
                    "installer adapter",
                    VFT_DLL,
                    "cargo:rustc-link-arg-cdylib",
                ),
                (
                    "cadrumo-msi-maintenance.exe",
                    "installer maintenance runner",
                    VFT_APP,
                    "cargo:rustc-link-arg-bin=cadrumo-msi-maintenance",
                ),
            ] {
                let names = VersionNames {
                    file_description: format!("{product_name} {description}"),
                    product_name: product_name.clone(),
                    original_filename: file_name.into(),
                    file_type,
                };
                let output = out_dir.join(format!("{file_name}.res"));
                std::fs::write(
                    &output,
                    resource_file(&[(RT_VERSION, VS_VERSION_INFO, &version_info(&names, build))]),
                )
                .expect("write installer version resource");
                println!("{link}={}", output.display());
            }
        }
    }
}

// Numbered Win32 resource records preserve the canonical manifest bytes instead
// of relying on linker XML merging. A leading empty record denotes a 32-bit RES.
fn entry(bytes: &mut Vec<u8>, kind: u16, name: u16, data: &[u8]) {
    bytes.extend_from_slice(
        &u32::try_from(data.len())
            .expect("bounded resource")
            .to_le_bytes(),
    );
    bytes.extend_from_slice(&32_u32.to_le_bytes());
    for ordinal in [kind, name] {
        bytes.extend_from_slice(&0xffff_u16.to_le_bytes());
        bytes.extend_from_slice(&ordinal.to_le_bytes());
    }
    bytes.extend_from_slice(&0_u32.to_le_bytes());
    bytes.extend_from_slice(&(if kind == 0 { 0_u16 } else { 0x30 }).to_le_bytes());
    bytes.extend_from_slice(&(if kind == 0 { 0_u16 } else { 0x409 }).to_le_bytes());
    bytes.extend_from_slice(&0_u32.to_le_bytes());
    bytes.extend_from_slice(&0_u32.to_le_bytes());
    bytes.extend_from_slice(data);
    bytes.resize(bytes.len().next_multiple_of(4), 0);
}
