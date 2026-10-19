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
    // The desktop component's identity for `env!`/`option_env!`: CADRUMO_ID_VERSION and
    // CADRUMO_DESKTOP_BUILD_{ID,SEQUENCE,DATE} come from the build, the type from the profile.
    // Only the desktop's own variables are watched, so another component's identity moving
    // never reruns this script.
    let build_type = match std::env::var("PROFILE").as_deref() {
        Ok("debug") => "debug",
        _ => "release",
    };
    println!("cargo:rustc-env=CADRUMO_BUILD_TYPE={build_type}");
    for name in [
        "CADRUMO_ID_VERSION",
        "CADRUMO_DESKTOP_BUILD_ID",
        "CADRUMO_DESKTOP_BUILD_SEQUENCE",
        "CADRUMO_DESKTOP_BUILD_DATE",
    ] {
        println!("cargo:rerun-if-env-changed={name}");
    }
    if let (Ok(version), Ok(build_id)) = (
        std::env::var("CADRUMO_ID_VERSION"),
        std::env::var("CADRUMO_DESKTOP_BUILD_ID"),
    ) {
        let suffix = if build_type == "debug" { ".debug" } else { "" };
        println!("cargo:rustc-env=CADRUMO_DISPLAY_VERSION={version}+{build_id}{suffix}");
    }
    let mut windows = tauri_build::WindowsAttributes::new();
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        // The window claims the package identity of its build kind, rendered beside the contract
        // from windows/desktop.manifest: Tauri's Common Controls dependency, the interpreter
        // host's Windows 10 and long-path claims its runtime and CLI roles rely on, plus that claim.
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
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows")
        && std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc")
    {
        stamp_windows_version_resource(build_type);
    }
}

/// Give the desktop image's version resource its component build sequence and identity.
///
/// tauri-build writes `resource.rc` (version, icon and the application manifest) into this
/// script's `OUT_DIR` and compiles it to `resource.lib`, which it has already told Cargo to
/// link. Its FILEVERSION takes a fourth field only from purely numeric semantic-version build
/// metadata, which the desktop's display version is not. This rewrites the two fixed-version
/// lines with the sequence, adds the `BuildId` and `BuildType` strings the other images carry,
/// and recompiles the same file in place with the pinned SDK resource compiler, so the link
/// Cargo was told about embeds the stamped resource.
fn stamp_windows_version_resource(build_type: &str) {
    let sequence_text = std::env::var("CADRUMO_DESKTOP_BUILD_SEQUENCE").expect(
        "CADRUMO_DESKTOP_BUILD_SEQUENCE must come from the desktop component's build identity",
    );
    let sequence: u16 = sequence_text
        .parse()
        .ok()
        .filter(|&value| value > 0)
        .unwrap_or_else(|| {
            panic!("CADRUMO_DESKTOP_BUILD_SEQUENCE must be 1 to 65535: {sequence_text}")
        });
    let build_id = std::env::var("CADRUMO_DESKTOP_BUILD_ID")
        .expect("CADRUMO_DESKTOP_BUILD_ID must come from the desktop component's build identity");
    println!("cargo:rerun-if-env-changed=CADRUMO_RC_COMPILER");
    let compiler = std::env::var_os("CADRUMO_RC_COMPILER")
        .expect("CADRUMO_RC_COMPILER must name the selected Windows SDK resource compiler");
    let out_dir =
        std::path::PathBuf::from(std::env::var_os("OUT_DIR").expect("Cargo sets OUT_DIR"));
    let resource = out_dir.join("resource.rc");
    let compiled = out_dir.join("resource.lib");
    let source = std::fs::read_to_string(&resource).expect("tauri-build writes resource.rc");
    assert!(
        compiled.is_file(),
        "tauri-build compiles resource.rc to resource.lib"
    );
    let mut stamped = String::with_capacity(source.len() + 128);
    let (mut fixed, mut strings) = (0, false);
    for line in source.lines() {
        if let Some((key, numbers)) = line
            .strip_prefix("FILEVERSION ")
            .map(|rest| ("FILEVERSION", rest))
            .or_else(|| {
                line.strip_prefix("PRODUCTVERSION ")
                    .map(|rest| ("PRODUCTVERSION", rest))
            })
        {
            let parts: Vec<&str> = numbers.split(", ").collect();
            assert_eq!(
                parts.len(),
                4,
                "tauri-build writes four version fields: {line}"
            );
            stamped.push_str(&format!(
                "{key} {}, {}, {}, {sequence}\n",
                parts[0], parts[1], parts[2]
            ));
            fixed += 1;
            continue;
        }
        if !strings && line.starts_with("VALUE \"FileVersion\"") {
            stamped.push_str(&format!("VALUE \"BuildId\", \"{build_id}\"\n"));
            stamped.push_str(&format!("VALUE \"BuildType\", \"{build_type}\"\n"));
            strings = true;
        }
        stamped.push_str(line);
        stamped.push('\n');
    }
    assert!(
        fixed == 2 && strings,
        "tauri-build's version resource changed shape; update this stamp"
    );
    std::fs::write(&resource, stamped).expect("write the stamped version resource");
    let status = std::process::Command::new(&compiler)
        .arg("/nologo")
        .arg("/fo")
        .arg(&compiled)
        .arg("/I")
        .arg(&out_dir)
        .arg(&resource)
        .status()
        .expect("run the Windows SDK resource compiler");
    assert!(
        status.success(),
        "the resource compiler refused the stamped version resource"
    );
}
