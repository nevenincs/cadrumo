//! Real filesystem/package/binary discovery fixtures; no installation or registry writes.
use cadrumo_application::installation::DiscoveryContract;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
};
use tempfile::TempDir;

struct Fixture {
    directory: TempDir,
    contract: DiscoveryContract,
    source: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        #[cfg(windows)]
        let source =
            PathBuf::from(std::env::var_os("SystemRoot").unwrap()).join("System32/where.exe");
        #[cfg(not(windows))]
        let source = std::env::current_exe().unwrap();
        let contract = serde_json::from_value(json!({
            "installation_identity": {"application_id": "test.discovery", "channel": "stable"},
            "layout": {"abi": 1, "platform": if cfg!(windows) {"windows-x64"} else {"fixture"},
                "installation": {"schema": 1, "marker": "data/installation.json", "versions": "versions", "maximum_versions": 128},
                "files": {"package_manifest": "data/package-manifest.json"},
                "application_images": [{"name": "manager", "placement": ".", "target": "rust_manager"}],
                "entrypoint_suffix": if cfg!(windows) {".exe"} else {""}}
        })).unwrap();
        Self {
            directory: tempfile::tempdir().unwrap(),
            contract,
            source,
        }
    }
    fn prefix(&self, name: &str) -> PathBuf {
        let prefix = self.directory.path().join(name);
        fs::create_dir_all(prefix.join("data")).unwrap();
        fs::write(
            prefix.join("data/installation.json"),
            serde_json::to_vec(&json!({
                "schema": 1, "application_id": "test.discovery", "channel": "stable",
                "platform": self.contract.layout.platform, "abi": 1
            }))
            .unwrap(),
        )
        .unwrap();
        fs::copy(
            &self.source,
            self.contract.manager_member().unwrap().under(&prefix),
        )
        .unwrap();
        prefix
    }
    fn version(&self, prefix: &Path, version: &str) -> PathBuf {
        let package = prefix.join("versions").join(version);
        fs::create_dir_all(package.join("data")).unwrap();
        let member = self.contract.manager_member().unwrap();
        fs::copy(&self.source, member.under(&package)).unwrap();
        fs::write(
            package.join("python.zip"),
            b"inventoried fixture dependency",
        )
        .unwrap();
        fs::write(package.join("data/package-manifest.json"), serde_json::to_vec(&json!({
            "build": {"application_id": "test.discovery", "channel": "stable", "version": version,
                "target": if cfg!(windows) {"windows-x86-64"} else {"fixture"}},
            "layout": {"abi": 1, "platform": self.contract.layout.platform}, "python": "fixture", "distributions": {},
            "files": {(member.as_str()): format!("{:x}", Sha256::digest(fs::read(&self.source).unwrap())),
                "python.zip": format!("{:x}", Sha256::digest(b"inventoried fixture dependency"))},
            "user_docs": {"directory": "docs/user", "bundled": false}
        })).unwrap()).unwrap();
        package
    }
    fn amend(&self, package: &Path, edit: impl FnOnce(&mut serde_json::Value)) {
        let file = package.join("data/package-manifest.json");
        let mut value = serde_json::from_slice(&fs::read(&file).unwrap()).unwrap();
        edit(&mut value);
        fs::write(file, serde_json::to_vec(&value).unwrap()).unwrap();
    }
}

#[test]
fn old_image_and_old_stable_entry_select_newest_complete_numeric_version() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("relocated ü space");
    let old = fixture.version(&prefix, "0.9.0");
    let newest = fixture.version(&prefix, "0.10.0");
    let incomplete = fixture.version(&prefix, "0.11.0");
    fs::remove_file(incomplete.join("python.zip")).unwrap();
    let member = fixture.contract.manager_member().unwrap();
    for image in [member.under(&old), member.under(&prefix)] {
        let result = fixture.contract.discover(&image, &[]).unwrap();
        assert_eq!(result.package, newest);
        assert_eq!(result.manager, member.under(&newest));
        assert_eq!(result.entrypoint, member.under(&prefix));
        assert_eq!(result.version, [0, 10, 0]);
    }
}

#[test]
fn registry_hints_select_across_scopes_but_never_authorize_foreign_or_incomplete_versions() {
    let fixture = Fixture::new();
    let machine = fixture.prefix("machine");
    let old = fixture.version(&machine, "1.0.0");
    let user = fixture.prefix("user");
    let newest = fixture.version(&user, "1.1.0");
    let preview = fixture.version(&user, "9.0.0");
    fixture.amend(&preview, |value| {
        value["build"]["channel"] = json!("preview")
    });
    let wrong = fixture.version(&user, "8.0.0");
    fixture.amend(&wrong, |value| {
        value["build"]["application_id"] = json!("foreign")
    });
    let member = fixture.contract.manager_member().unwrap();
    let result = fixture
        .contract
        .discover(&member.under(&old), &[member.under(&user)])
        .unwrap();
    assert_eq!(result.package, newest);
    fs::write(member.under(&user), b"damaged stable entry").unwrap();
    assert_eq!(
        fixture
            .contract
            .discover(&member.under(&old), &[member.under(&user)])
            .unwrap()
            .package,
        old
    );
}

#[test]
fn incompatible_marker_and_version_metadata_cannot_win_selection() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("metadata");
    let old = fixture.version(&prefix, "1.0.0");
    let newer = fixture.version(&prefix, "1.1.0");
    fixture.amend(&newer, |value| value["layout"]["abi"] = json!(99));
    assert_eq!(fixture.contract.inspect(&prefix).unwrap().package, old);
    fixture.version(&prefix, "1.1.0");
    fixture.amend(&newer, |value| value["build"]["version"] = json!("1.2.0"));
    assert_eq!(fixture.contract.inspect(&prefix).unwrap().package, old);
    fixture.version(&prefix, "01.2.0");
    assert_eq!(fixture.contract.inspect(&prefix).unwrap().package, old);
    let marker = prefix.join("data/installation.json");
    let original: serde_json::Value = serde_json::from_slice(&fs::read(&marker).unwrap()).unwrap();
    for (key, value) in [
        ("channel", json!("preview")),
        ("application_id", json!("foreign")),
        ("schema", json!(99)),
        ("platform", json!("foreign")),
        ("abi", json!(99)),
        ("unknown", json!(true)),
    ] {
        let mut changed = original.clone();
        changed[key] = value;
        fs::write(&marker, serde_json::to_vec(&changed).unwrap()).unwrap();
        assert!(fixture.contract.inspect(&prefix).is_err());
    }
}

#[test]
fn catalogue_rejects_tampering_extras_wrong_target_links_traversal_and_unbounded_inventory() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("isolated");
    let package = fixture.version(&prefix, "1.0.0");
    assert!(fixture.contract.inspect(&prefix).is_ok());
    fs::write(package.join("unexpected"), b"extra").unwrap();
    assert!(fixture.contract.inspect(&prefix).is_err());
    fs::remove_file(package.join("unexpected")).unwrap();
    fixture.amend(&package, |value| {
        value["build"]["target"] = json!("foreign-target")
    });
    assert!(fixture.contract.inspect(&prefix).is_err());
    fixture.version(&prefix, "1.0.0");
    fixture.amend(&package, |value| {
        value["files"] = json!({"../foreign": "00".repeat(32)})
    });
    assert!(fixture.contract.inspect(&prefix).is_err());
    fixture.version(&prefix, "1.0.0");
    fs::write(package.join("python.zip"), b"modified").unwrap();
    assert!(fixture.contract.inspect(&prefix).is_err());
    fixture.version(&prefix, "1.0.0");
    for i in 0..128 {
        fs::create_dir(prefix.join("versions").join(format!("incomplete-{i}"))).unwrap();
    }
    assert!(matches!(
        fixture.contract.inspect(&prefix),
        Err(cadrumo_application::error::Error::LimitExceeded)
    ));
    assert!(
        fixture
            .contract
            .inspect(&prefix.join("../isolated"))
            .is_err()
    );
}

#[cfg(windows)]
#[test]
fn linked_prefix_and_version_are_not_admitted() {
    use std::os::windows::process::CommandExt;
    let fixture = Fixture::new();
    let prefix = fixture.prefix("original");
    let package = fixture.version(&prefix, "1.0.0");
    let linked = fixture.directory.path().join("linked");
    let status = std::process::Command::new("cmd.exe")
        .args(["/d", "/c", "mklink", "/J"])
        .arg(&linked)
        .arg(&prefix)
        .creation_flags(0x0800_0000)
        .output()
        .unwrap();
    assert!(
        status.status.success(),
        "junction creation failed: {} {}",
        String::from_utf8_lossy(&status.stdout),
        String::from_utf8_lossy(&status.stderr)
    );
    assert!(fixture.contract.inspect(&linked).is_err());
    fs::remove_dir(&linked).unwrap();
    let alias = prefix.join("versions").join("2.0.0");
    let status = std::process::Command::new("cmd.exe")
        .args(["/d", "/c", "mklink", "/J"])
        .arg(&alias)
        .arg(&package)
        .creation_flags(0x0800_0000)
        .output()
        .unwrap();
    assert!(
        status.status.success(),
        "junction creation failed: {} {}",
        String::from_utf8_lossy(&status.stdout),
        String::from_utf8_lossy(&status.stderr)
    );
    assert_eq!(fixture.contract.inspect(&prefix).unwrap().package, package);
    fs::remove_dir(&alias).unwrap();
    assert!(package.join("python.zip").is_file());
}
