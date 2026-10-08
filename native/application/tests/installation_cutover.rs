//! Catalogue rollback selection uses complete native inventory and stable-anchor proof.
use cadrumo_application::{component::Cancellation, installation::DiscoveryContract};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{fs, path::Path};

fn executable(path: &Path) {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o755)).unwrap();
    }
    #[cfg(not(unix))]
    let _ = path;
}

fn release(contract: &DiscoveryContract, prefix: &Path, release: &str, image: &[u8]) {
    let package = prefix.join("versions").join(release);
    fs::create_dir_all(package.join("data")).unwrap();
    let member = contract.manager_member().unwrap();
    fs::write(member.under(&package), image).unwrap();
    executable(&member.under(&package));
    fs::write(package.join("data/package-manifest.json"), serde_json::to_vec(&json!({
        "build": {"application_id":"test.cutover", "channel":"stable", "version": release,
            "target": if cfg!(windows) {"windows-x86-64"} else {"fixture"}},
        "layout": {"abi":1,"platform":contract.layout.platform}, "python":"fixture", "distributions":{},
        "files":{member.as_str():format!("{:x}",Sha256::digest(image))},
        "user_docs":{"directory":"docs/user","bundled":false}
    })).unwrap()).unwrap();
}

#[test]
fn rollback_selects_exact_complete_version_without_changing_normal_newest_selection() {
    let temporary = tempfile::tempdir().unwrap();
    let prefix = temporary.path();
    let platform = if cfg!(windows) {
        "windows-x64"
    } else {
        "fixture"
    };
    let contract: DiscoveryContract = serde_json::from_value(json!({
        "installation_identity":{"application_id":"test.cutover","channel":"stable"},
        "layout":{"abi":1,"platform":platform,
            "installation":{"schema":1,"marker":"data/installation.json","versions":"versions","maximum_versions":8},
            "files":{"package_manifest":"data/package-manifest.json"},
            "application_images":[{"name":"manager","placement":".","target":"rust_manager"}],
            "entrypoint_suffix":if cfg!(windows) {".exe"} else {""}}
    })).unwrap();
    fs::create_dir(prefix.join("data")).unwrap();
    fs::write(prefix.join("data/installation.json"),serde_json::to_vec(&json!({
        "schema":1,"application_id":"test.cutover","channel":"stable","platform":platform,"abi":1
    })).unwrap()).unwrap();
    #[cfg(windows)]
    let image =
        fs::read(Path::new(&std::env::var_os("SystemRoot").unwrap()).join("System32/where.exe"))
            .unwrap();
    #[cfg(not(windows))]
    let image = fs::read(std::env::current_exe().unwrap()).unwrap();
    fs::write(contract.manager_member().unwrap().under(prefix), &image).unwrap();
    executable(&contract.manager_member().unwrap().under(prefix));
    for version in ["1.0.0", "2.0.0", "3.0.0"] {
        release(&contract, prefix, version, &image);
    }
    fs::write(
        contract
            .manager_member()
            .unwrap()
            .under(&prefix.join("versions/3.0.0")),
        b"damaged",
    )
    .unwrap();
    let cancel = Cancellation::default();
    let catalogue = contract.catalogue_cancellable(prefix, &cancel).unwrap();
    assert_eq!(
        catalogue.iter().map(|v| v.version).collect::<Vec<_>>(),
        [[2, 0, 0], [1, 0, 0]]
    );
    assert_eq!(contract.inspect(prefix).unwrap().version, [2, 0, 0]);
    assert_eq!(
        contract
            .inspect_version_cancellable(prefix, "1.0.0", &cancel)
            .unwrap()
            .version,
        [1, 0, 0]
    );
    assert!(
        contract
            .inspect_version_cancellable(prefix, "3.0.0", &cancel)
            .is_err()
    );
    assert!(
        contract
            .inspect_version_cancellable(prefix, "01.0.0", &cancel)
            .is_err()
    );
    fs::remove_file(contract.manager_member().unwrap().under(prefix)).unwrap();
    assert!(
        contract
            .inspect_version_cancellable(prefix, "1.0.0", &cancel)
            .is_err()
    );
}
