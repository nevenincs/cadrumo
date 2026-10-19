//! Windows linkage for the manager image.
//!
//! The image embeds the rendered native-host process manifest unchanged as resource 1,
//! because linker manifest merging rewrites the document and can discard compatibility
//! entries. The build supplies that document, which carries the package identity claim.
//! The manager binary also carries a version resource named from the identity projection
//! and the manager component's build id and sequence, which the shell shows for the image, for example in
//! Task Manager's startup list. Both are serialized here as `.res` files, so the build
//! needs no resource compiler. Load-time imports resolve from System32 only, like the C hosts.

use std::{env, fs, path::PathBuf};

include!("version_resource.rs");

const RT_MANIFEST: u16 = 24;
const CREATEPROCESS_MANIFEST_RESOURCE_ID: u16 = 1;

/// The Cargo binary that is the packaged manager image; other binaries keep no version resource.
const MANAGER_BINARY: &str = "cadrumo-manager";

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=version_resource.rs");
    // Only the manager image's own build reads its identity; as a library of the desktop
    // the crate compiles without one, and its executable cannot.
    let build = BuildIdentity::for_image("manager");
    if let Some(build) = &build {
        println!("cargo:rustc-env=CADRUMO_BUILD_TYPE={}", build.build_type);
        println!(
            "cargo:rustc-env=CADRUMO_DISPLAY_VERSION={}",
            build.display_version()
        );
    }
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let target_env = env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
    if target_os != "windows" || target_env != "msvc" {
        return;
    }
    let out_dir = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo sets OUT_DIR"));
    let manifest = PathBuf::from(projected("CADRUMO_PROCESS_MANIFEST"));
    println!("cargo:rerun-if-changed={}", manifest.display());
    let document = fs::read(&manifest).expect("read the rendered native-host process manifest");
    let manifest_resource = out_dir.join("manager-manifest.res");
    fs::write(
        &manifest_resource,
        resource_file(&[(RT_MANIFEST, CREATEPROCESS_MANIFEST_RESOURCE_ID, &document)]),
    )
    .expect("write the manifest resource");
    // The resource is the only manifest; a linker-generated one would duplicate resource 1.
    println!("cargo:rustc-link-arg-bins=/MANIFEST:NO");
    // LOAD_LIBRARY_SEARCH_SYSTEM32: the image sits at the package root beside other DLLs.
    println!("cargo:rustc-link-arg-bins=/DEPENDENTLOADFLAG:0x800");
    println!("cargo:rustc-link-arg-bins={}", manifest_resource.display());
    if let Some(build) = &build {
        let version_resource = out_dir.join("manager-version.res");
        let names = VersionNames {
            product_name: projected("CADRUMO_ID_NAME"),
            file_description: projected("CADRUMO_ID_MANAGER_NAME"),
            original_filename: format!("{MANAGER_BINARY}.exe"),
            file_type: VFT_APP,
        };
        fs::write(
            &version_resource,
            resource_file(&[(RT_VERSION, VS_VERSION_INFO, &version_info(&names, build))]),
        )
        .expect("write the version resource");
        println!(
            "cargo:rustc-link-arg-bin={MANAGER_BINARY}={}",
            version_resource.display()
        );
    }
}
