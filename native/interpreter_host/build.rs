//! Compile the Windows interpreter host into this crate, so the Cadrumo binary runs a
//! console entrypoint role in its own process instead of starting a separate host image.
//!
//! The source and compile policy are the ones the standalone hosts use; the generated
//! contract and build metadata headers sit beside the generated package contract.

use std::{env, path::PathBuf};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return;
    }
    let contract = PathBuf::from(
        env::var_os("CADRUMO_NATIVE_CONTRACT")
            .expect("CADRUMO_NATIVE_CONTRACT must select the generated package contract"),
    );
    println!("cargo:rerun-if-env-changed=CADRUMO_NATIVE_CONTRACT");
    let generated = contract
        .parent()
        .expect("the generated contract has a directory")
        .to_path_buf();
    let native = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").expect("Cargo sets it"))
        .parent()
        .expect("the crate sits in the native directory")
        .to_path_buf();
    let interpreter = native.join("interpreter");
    let source = interpreter.join("windows").join("host.c");
    for input in [
        source.clone(),
        interpreter.join("launch_guard.h"),
        interpreter.join("launch_profile.h"),
        generated.join("contract.h"),
        generated.join("build_metadata.h"),
    ] {
        println!("cargo:rerun-if-changed={}", input.display());
    }
    cc::Build::new()
        .file(&source)
        .include(&generated)
        .include(native.join("platform").join("include"))
        .include(native.join("launch_guard").join("include"))
        .include(&interpreter)
        .include(interpreter.join("windows"))
        .define("CADRUMO_LINKED_HOST", None)
        // Cargo's profile directory is the build type, as the CMake configuration is for the C hosts.
        .define(
            "CADRUMO_BUILD_DEBUG",
            if env::var("PROFILE").as_deref() == Ok("debug") {
                "1"
            } else {
                "0"
            },
        )
        .define("WINVER", "0x0A00")
        .define("_WIN32_WINNT", "0x0A00")
        .std("c17")
        .flag("/W4")
        .flag("/sdl")
        .flag("/guard:cf")
        .warnings_into_errors(true)
        .compile("cadrumo_interpreter_host");
}
