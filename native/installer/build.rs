fn main() {
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
        let output = std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap())
            .join("installer-manifest.res");
        std::fs::write(&output, resource).expect("write installer process manifest");
        println!("cargo:rustc-link-arg-bins=/MANIFEST:NO");
        println!("cargo:rustc-link-arg-bins={}", output.display());
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
