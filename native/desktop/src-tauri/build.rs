fn main() {
    let contract = std::env::var("CADRUMO_NATIVE_CONTRACT")
        .expect("CADRUMO_NATIVE_CONTRACT must select the generated package contract");
    println!("cargo:rerun-if-env-changed=CADRUMO_NATIVE_CONTRACT");
    println!("cargo:rerun-if-changed={contract}");
    std::fs::copy(
        contract,
        std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap()).join("contract.json"),
    )
    .expect("copy generated package contract");
    tauri_build::build();
}
