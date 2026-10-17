fn main() {
    let contract = std::env::var("CADRUMO_NATIVE_CONTRACT")
        .expect("CADRUMO_NATIVE_CONTRACT must select the generated package contract");
    println!("cargo:rerun-if-env-changed=CADRUMO_NATIVE_CONTRACT");
    println!("cargo:rerun-if-changed={contract}");
    std::fs::copy(
        &contract,
        std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap()).join("contract.json"),
    )
    .expect("copy generated package contract");
    let mut windows = tauri_build::WindowsAttributes::new();
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        // The window claims the package identity of its build kind, rendered beside the contract
        // from windows/desktop.manifest: Tauri's Common Controls dependency plus that claim.
        let kind = match std::env::var("PROFILE").as_deref() {
            Ok("debug") => "development",
            _ => "release",
        };
        let manifest =
            std::path::Path::new(&contract).with_file_name(format!("desktop-{kind}.manifest"));
        println!("cargo:rerun-if-changed={}", manifest.display());
        windows = windows.app_manifest(
            std::fs::read_to_string(&manifest).expect("read the rendered desktop manifest"),
        );
    }
    tauri_build::try_build(tauri_build::Attributes::new().windows_attributes(windows))
        .expect("tauri build");
}
