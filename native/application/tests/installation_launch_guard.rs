//! Each process independently fences native removal of its exact own package.
use cadrumo_application::{
    error::Error,
    installation::{
        DiscoveryContract,
        maintenance::{Identity, NativeContext, NativeOwner, Store},
    },
    value::Sha256Digest,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
};

struct Fixture {
    _temporary: tempfile::TempDir,
    prefix: PathBuf,
    package: PathBuf,
    contract: DiscoveryContract,
}
impl Fixture {
    fn new() -> Self {
        let temporary = tempfile::tempdir().unwrap();
        let prefix = temporary.path().join("prefix");
        let package = prefix.join("versions/1.0.0");
        fs::create_dir_all(package.join("data")).unwrap();
        fs::create_dir_all(prefix.join("data")).unwrap();
        let platform = if cfg!(windows) {
            "windows-x64"
        } else {
            "fixture"
        };
        let contract = serde_json::from_value(json!({
            "installation_identity":{"application_id":"test.launch","channel":"stable"},
            "layout":{"abi":1,"platform":platform,
                "installation":{"schema":1,"marker":"data/installation.json","versions":"versions",
                    "maximum_versions":8,"publication":"data/installation-state"},
                "files":{"package_manifest":"data/package-manifest.json"},
                "application_images":[{"name":"manager","placement":".","target":"rust_manager"}],
                "entrypoint_suffix":if cfg!(windows) {".exe"} else {""}}
        }))
        .unwrap();
        let fixture = Self {
            _temporary: temporary,
            prefix,
            package,
            contract,
        };
        fixture.marker(json!({"launch_policy":"native", "publication":"data/installation-state"}));
        fixture
    }
    fn marker(&self, extra: serde_json::Value) {
        let mut marker = json!({"schema":1,"application_id":"test.launch","channel":"stable",
            "platform":self.contract.layout.platform,"abi":1});
        marker
            .as_object_mut()
            .unwrap()
            .extend(extra.as_object().unwrap().clone());
        fs::write(
            self.prefix.join("data/installation.json"),
            serde_json::to_vec(&marker).unwrap(),
        )
        .unwrap();
    }
    fn store(&self) -> Store {
        Store::new(
            self.prefix.join("data/installation-state"),
            Identity {
                application_id: "test.launch".into(),
                channel: "stable".into(),
                platform: self.contract.layout.platform.clone(),
            },
            8,
        )
        .unwrap()
    }
    fn prepare(&self) -> (Store, cadrumo_application::installation::maintenance::Lease) {
        #[cfg(windows)]
        let source =
            PathBuf::from(std::env::var_os("SystemRoot").unwrap()).join("System32/where.exe");
        #[cfg(not(windows))]
        let source = std::env::current_exe().unwrap();
        let member = self.contract.manager_member().unwrap();
        fs::copy(&source, member.under(&self.package)).unwrap();
        let manifest = serde_json::to_vec(&json!({
            "build":{"application_id":"test.launch","channel":"stable","version":"1.0.0",
                "target":if cfg!(windows) {"windows-x86-64"} else {"fixture"}},
            "layout":{"abi":1,"platform":self.contract.layout.platform},"python":"fixture","distributions":{},
            "files":{member.as_str():format!("{:x}",Sha256::digest(fs::read(source).unwrap()))},
            "user_docs":{"directory":"docs/user","bundled":false}
        })).unwrap();
        fs::write(self.package.join("data/package-manifest.json"), &manifest).unwrap();
        let store = self.store();
        store.initialize().unwrap();
        let owner = NativeOwner::new(
            "12345678-1234-1234-1234-123456789abc".into(),
            NativeContext::Machine,
            self.prefix.clone(),
        )
        .unwrap();
        let reservation = store
            .prepare(
                "1.0.0",
                owner,
                Sha256Digest::new(format!("{:x}", Sha256::digest(manifest))).unwrap(),
            )
            .unwrap();
        (store, reservation)
    }
}

#[test]
fn independent_lifetime_leases_block_removal_and_removing_blocks_direct_launch() {
    let f = Fixture::new();
    let (store, reservation) = f.prepare();
    assert!(f.contract.acquire_package(&f.package).is_err()); // Pending.
    store.publish("1.0.0", &f.package, &f.contract).unwrap();
    assert!(f.contract.acquire_package(&f.package).is_err()); // Native writer still owns it.
    drop(reservation);
    let manager = f.contract.acquire_package(&f.package).unwrap().unwrap();
    let runtime = f.contract.acquire_package(&f.package).unwrap().unwrap();
    drop(manager);
    assert!(matches!(store.begin_removal("1.0.0"), Err(Error::Busy)));
    drop(runtime);
    let removal = store.begin_removal("1.0.0").unwrap();
    assert!(f.contract.acquire_package(&f.package).is_err());
    drop(removal);
    assert!(f.contract.acquire_package(&f.package).is_err()); // Durable Removing, not lock-only.
}

#[test]
fn structural_native_path_never_falls_back_when_publication_is_missing() {
    let f = Fixture::new();
    assert!(f.contract.acquire_package(&f.package).is_err());
    f.marker(json!({})); // Legacy ambiguity is not explicit portable intent.
    assert!(f.contract.acquire_package(&f.package).is_err());
    f.marker(json!({"launch_policy":"native"}));
    assert!(f.contract.acquire_package(&f.package).is_err());
    fs::remove_file(f.prefix.join("data/installation.json")).unwrap();
    assert!(f.contract.acquire_package(&f.package).is_err());
    #[cfg(windows)]
    assert!(
        f.contract
            .acquire_package(&f.prefix.join("VERSIONS/1.0.0"))
            .is_err()
    );
    let invalid = f.prefix.join("versions/not-a-release");
    fs::create_dir(&invalid).unwrap();
    assert!(f.contract.acquire_package(&invalid).is_err());
    let nested = f.package.join("nested");
    fs::create_dir(&nested).unwrap();
    assert!(f.contract.acquire_package(&nested).is_err());
}

#[test]
fn portable_intent_is_explicit_and_cannot_hide_existing_native_publication() {
    let f = Fixture::new();
    f.marker(json!({"launch_policy":"portable"}));
    assert!(f.contract.acquire_package(&f.package).unwrap().is_none());
    assert!(f.contract.acquire_package(&f.prefix).is_err());
    f.store().initialize().unwrap();
    assert!(f.contract.acquire_package(&f.package).is_err());
    let standalone = f._temporary.path().join("assembled");
    fs::create_dir(&standalone).unwrap();
    assert!(f.contract.acquire_package(&standalone).unwrap().is_none());
    assert!(f.contract.acquire_package(Path::new("relative")).is_err());
}

#[test]
fn altered_manifest_cannot_borrow_ready_lease_or_another_release() {
    let f = Fixture::new();
    let (store, reservation) = f.prepare();
    store.publish("1.0.0", &f.package, &f.contract).unwrap();
    drop(reservation);
    let path = f.package.join("data/package-manifest.json");
    let bytes = fs::read(&path).unwrap();
    let mut changed = bytes.clone();
    changed.push(b' ');
    fs::write(&path, changed).unwrap();
    assert!(f.contract.acquire_package(&f.package).is_err());
    fs::write(&path, bytes).unwrap();
    let other = f.prefix.join("versions/2.0.0");
    fs::rename(&f.package, &other).unwrap();
    assert!(f.contract.acquire_package(&other).is_err());
}
