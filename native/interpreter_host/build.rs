//! Compile the platform's interpreter host into this crate, so the Cadrumo binary runs a
//! console entrypoint role in its own process instead of starting a separate host image.
//!
//! The source and compile policy are the ones the standalone hosts use; the generated
//! contract and layout headers sit beside the generated package contract. The build identity
//! header is written here from the identity of the image that links this crate
//! (`CADRUMO_IMAGE_COMPONENT`, normally the desktop), so a change to the interpreter hosts'
//! identity alone rebuilds nothing that links this host. The interpreter's own identity
//! still reaches every Python start through the CPython bridge, which the bootstrap checks.

use std::{env, path::PathBuf};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    let windows = env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows");
    if !windows && env::var("CARGO_CFG_TARGET_FAMILY").as_deref() != Ok("unix") {
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
    let host = interpreter.join(if windows { "windows" } else { "posix" });
    let source = host.join("host.c");
    for input in [
        source.clone(),
        interpreter.join("launch_guard.h"),
        interpreter.join("launch_profile.h"),
        generated.join("contract.h"),
        generated.join("build_layout.h"),
    ] {
        println!("cargo:rerun-if-changed={}", input.display());
    }
    let out_dir = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo sets OUT_DIR"));
    std::fs::write(out_dir.join("build_metadata.h"), identity_header())
        .expect("write the linking image's build identity header");
    let mut build = cc::Build::new();
    build
        .file(&source)
        .include(&out_dir)
        .include(&generated)
        .include(native.join("platform").join("include"))
        .include(native.join("launch_guard").join("include"))
        .include(&interpreter)
        .include(&host)
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
        .std("c17")
        .warnings_into_errors(true);
    // The compile policy the standalone hosts take from CompilePolicy.cmake.
    if windows {
        build
            .define("WINVER", "0x0A00")
            .define("_WIN32_WINNT", "0x0A00")
            .flag("/W4")
            .flag("/sdl")
            .flag("/guard:cf");
    } else {
        build
            .flag("-Wall")
            .flag("-Wextra")
            .flag("-Wformat=2")
            .flag("-fstack-protector-strong");
    }
    build.compile("cadrumo_interpreter_host");
}

fn projected(name: &str) -> String {
    println!("cargo:rerun-if-env-changed={name}");
    let value = env::var(name)
        .unwrap_or_else(|_| panic!("{name} must come from the build's identity projection"));
    assert!(
        !value.is_empty() && !value.contains(['"', '\\', '\0']),
        "{name} must be a non-empty string a C literal can hold"
    );
    value
}

/// The `build_metadata.h` the C host compiles: the linking image's identity over the shared
/// layout header, selecting the display version of the compiler's build type.
fn identity_header() -> String {
    let component = projected("CADRUMO_IMAGE_COMPONENT").to_uppercase();
    let version = projected("CADRUMO_ID_VERSION");
    let build_id = projected(&format!("CADRUMO_{component}_BUILD_ID"));
    let sequence = projected(&format!("CADRUMO_{component}_BUILD_SEQUENCE"));
    let date = projected(&format!("CADRUMO_{component}_BUILD_DATE"));
    format!(
        "#include \"build_layout.h\"\n\
         #define CADRUMO_BUILD_ID \"{build_id}\"\n\
         #define CADRUMO_BUILD_SEQUENCE \"{sequence}\"\n\
         #define CADRUMO_BUILD_NUMBER \"{sequence}\"\n\
         #define CADRUMO_BUILD_DATE \"{date}\"\n\
         #define CADRUMO_DISPLAY_VERSION_RELEASE \"{version}+{build_id}\"\n\
         #define CADRUMO_DISPLAY_VERSION_DEBUG \"{version}+{build_id}.debug\"\n\
         #if CADRUMO_BUILD_DEBUG\n\
         #define CADRUMO_BUILD_TYPE \"debug\"\n\
         #define CADRUMO_DISPLAY_VERSION CADRUMO_DISPLAY_VERSION_DEBUG\n\
         #else\n\
         #define CADRUMO_BUILD_TYPE \"release\"\n\
         #define CADRUMO_DISPLAY_VERSION CADRUMO_DISPLAY_VERSION_RELEASE\n\
         #endif\n"
    )
}
