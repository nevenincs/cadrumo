//! Real filesystem/package/binary discovery fixtures; no installation or registry writes.
use cadrumo_application::{component::Cancellation, error::Error, installation::DiscoveryContract};
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
    fn version_with_distinct_manager(&self, prefix: &Path, version: &str) -> PathBuf {
        let package = self.version(prefix, version);
        let member = self.contract.manager_member().unwrap();
        // Native object parsing permits an inert overlay without changing the
        // executable's target. These bytes are never executed by this fixture.
        let mut bytes = fs::read(member.under(&package)).unwrap();
        bytes.extend_from_slice(b"distinct fixture manager overlay");
        fs::write(member.under(&package), &bytes).unwrap();
        self.amend(&package, |value| {
            value["files"][member.as_str()] = json!(format!("{:x}", Sha256::digest(&bytes)));
        });
        package
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
fn pre_cancelled_discovery_and_prefix_inspection_never_fall_back() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("cancelled discovery");
    let package = fixture.version(&prefix, "1.0.0");
    let member = fixture.contract.manager_member().unwrap();
    let cancellation = Cancellation::default();
    cancellation.cancel();
    assert!(matches!(
        fixture.contract.inspect_cancellable(&prefix, &cancellation),
        Err(Error::Cancelled)
    ));
    assert!(matches!(
        fixture.contract.discover_cancellable(
            &member.under(&package),
            &[member.under(&prefix)],
            &cancellation
        ),
        Err(Error::Cancelled)
    ));
    assert_eq!(
        fixture
            .contract
            .discover(&member.under(&package), &[])
            .unwrap()
            .package,
        package
    );
}

#[test]
fn cancellation_during_candidate_verification_propagates_through_both_fallbacks() {
    use std::{
        sync::{Arc, mpsc},
        thread,
        time::Duration,
    };
    let fixture = Fixture::new();
    let prefix = fixture.prefix("active verification");
    let older = fixture.version(&prefix, "1.0.0");
    let newest = fixture.version(&prefix, "2.0.0");
    let fallback = fixture.prefix("valid fallback prefix");
    fixture.version(&fallback, "1.0.0");
    let payload = fs::File::create(newest.join("large.bin")).unwrap();
    payload.set_len(512 * 1024 * 1024).unwrap();
    fixture.amend(&newest, |value| {
        value["files"]["large.bin"] = json!("00".repeat(32))
    });
    let cancellation = Arc::new(Cancellation::default());
    let worker_token = cancellation.clone();
    let member = fixture.contract.manager_member().unwrap();
    let image = member.under(&older);
    let registered = [member.under(&fallback)];
    let (entered, ready) = mpsc::channel();
    let result = thread::scope(|scope| {
        let contract = &fixture.contract;
        let worker = scope.spawn(move || {
            entered.send(()).unwrap();
            contract.discover_cancellable(&image, &registered, &worker_token)
        });
        ready.recv_timeout(Duration::from_secs(5)).unwrap();
        // A large logical member adds verification work without writing payload
        // bytes. This handshake precedes discover, so hashing entry is not
        // independently observed. The reader unit test proves the exact chunk
        // boundary; this integration exercises both public fallback layers.
        thread::sleep(Duration::from_millis(20));
        cancellation.cancel();
        worker.join().unwrap()
    });
    assert!(matches!(result, Err(Error::Cancelled)));
}

#[test]
fn damaged_newest_hash_falls_back_to_the_next_complete_version() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("damaged newest");
    let complete = fixture.version(&prefix, "1.0.0");
    let damaged = fixture.version(&prefix, "2.0.0");
    fs::write(damaged.join("python.zip"), b"modified dependency").unwrap();
    let selected = fixture.contract.inspect(&prefix).unwrap();
    assert_eq!(selected.package, complete);
    assert_eq!(selected.version, [1, 0, 0]);
}

#[test]
fn a_complete_older_stable_manager_with_different_bytes_still_selects_the_newest_package() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("older stable ü space");
    let old = fixture.version(&prefix, "1.0.0");
    let newest = fixture.version_with_distinct_manager(&prefix, "2.0.0");
    fixture.version(&prefix, "0.9.0");
    let member = fixture.contract.manager_member().unwrap();
    assert_eq!(
        fs::read(member.under(&prefix)).unwrap(),
        fs::read(member.under(&old)).unwrap()
    );
    assert_ne!(
        fs::read(member.under(&prefix)).unwrap(),
        fs::read(member.under(&newest)).unwrap()
    );
    let selected = fixture.contract.inspect(&prefix).unwrap();
    assert_eq!(selected.package, newest);
    assert_eq!(selected.version, [2, 0, 0]);
}

#[test]
fn an_incomplete_older_package_cannot_verify_the_stable_manager() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("incomplete stable match");
    let older = fixture.version(&prefix, "1.0.0");
    fixture.version_with_distinct_manager(&prefix, "2.0.0");
    fs::remove_file(older.join("python.zip")).unwrap();
    assert!(matches!(
        fixture.contract.inspect(&prefix),
        Err(cadrumo_application::error::Error::Integrity(_))
    ));
}

#[test]
fn a_modified_stable_manager_is_refused_even_when_newest_is_complete() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("modified stable");
    fixture.version(&prefix, "1.0.0");
    fixture.version(&prefix, "2.0.0");
    fs::write(
        fixture.contract.manager_member().unwrap().under(&prefix),
        b"modified stable image",
    )
    .unwrap();
    assert!(matches!(
        fixture.contract.inspect(&prefix),
        Err(cadrumo_application::error::Error::Integrity(_))
    ));
}

#[test]
fn moving_the_complete_prefix_keeps_versioned_and_stable_discovery_coherent() {
    let fixture = Fixture::new();
    let prefix = fixture.prefix("original prefix");
    fixture.version(&prefix, "1.0.0");
    let relocated = fixture.directory.path().join("relocated ü prefix");
    fs::rename(&prefix, &relocated).unwrap();
    let member = fixture.contract.manager_member().unwrap();
    let package = relocated.join("versions/1.0.0");
    for image in [member.under(&relocated), member.under(&package)] {
        let selected = fixture.contract.discover(&image, &[]).unwrap();
        assert_eq!(selected.package, package);
        assert_eq!(selected.entrypoint, member.under(&relocated));
        assert_eq!(selected.version, [1, 0, 0]);
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
