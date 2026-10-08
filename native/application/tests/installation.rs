//! Real filesystem/package/binary discovery fixtures; no installation or registry writes.
use cadrumo_application::{
    component::Cancellation,
    error::Error,
    installation::{DiscoveryContract, RegistrationHints},
};
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

    fn native(&mut self, prefix: &Path) -> cadrumo_application::installation::maintenance::Store {
        use cadrumo_application::{
            installation::maintenance::{Identity, Store},
            value::RelativePath,
        };
        let relative = RelativePath::new("data/installation-state").unwrap();
        self.contract.layout.installation.publication = Some(relative.clone());
        let marker = prefix.join("data/installation.json");
        let mut value: serde_json::Value =
            serde_json::from_slice(&fs::read(&marker).unwrap()).unwrap();
        value["publication"] = json!(relative.as_str());
        fs::write(marker, serde_json::to_vec(&value).unwrap()).unwrap();
        Store::new(
            relative.under(prefix),
            Identity {
                application_id: "test.discovery".into(),
                channel: "stable".into(),
                platform: self.contract.layout.platform.clone(),
            },
            128,
        )
        .unwrap()
    }
}

#[test]
fn native_publication_refuses_missing_pending_changed_and_removing_versions() {
    use cadrumo_application::value::Sha256Digest;
    let mut fixture = Fixture::new();
    let prefix = fixture.prefix("native");
    let package = fixture.version(&prefix, "1.0.0");
    let store = fixture.native(&prefix);
    assert!(
        fixture
            .contract
            .inspect_cancellable(&prefix, &Cancellation::default())
            .is_err()
    );
    store.initialize().unwrap();
    let manifest = Sha256Digest::new(format!(
        "{:x}",
        Sha256::digest(fs::read(package.join("data/package-manifest.json")).unwrap())
    ))
    .unwrap();
    use cadrumo_application::installation::maintenance::{NativeContext, NativeOwner};
    let product = NativeOwner::new(
        "12345678-1234-1234-1234-123456789abc".to_owned(),
        NativeContext::Machine,
        prefix.clone(),
    )
    .unwrap();
    let install = store
        .prepare("1.0.0", product.clone(), manifest.clone())
        .unwrap();
    assert!(
        fixture
            .contract
            .inspect_cancellable(&prefix, &Cancellation::default())
            .is_err()
    );
    let other = Sha256Digest::new("0".repeat(64)).unwrap();
    assert!(store.prepare("1.0.0", product, other).is_err());
    fs::write(package.join("python.zip"), b"changed").unwrap();
    assert!(store.publish("1.0.0", &package, &fixture.contract).is_err());
    fs::write(
        package.join("python.zip"),
        b"inventoried fixture dependency",
    )
    .unwrap();
    store.publish("1.0.0", &package, &fixture.contract).unwrap();
    assert!(store.acquire("1.0.0", &manifest).is_err());
    drop(install);
    let selection = fixture
        .contract
        .inspect_cancellable(&prefix, &Cancellation::default())
        .unwrap();
    assert!(matches!(store.begin_removal("1.0.0"), Err(Error::Busy)));
    let clone = selection.clone();
    drop(selection);
    assert!(matches!(store.begin_removal("1.0.0"), Err(Error::Busy)));
    drop(clone);
    store.anchors(Some("1.0.0"), None).unwrap();
    let snapshot = store.snapshot().unwrap();
    assert_eq!(snapshot.manager_anchor(), Some("1.0.0"));
    assert_eq!(snapshot.desktop_anchor(), None);
    assert_eq!(snapshot.versions().count(), 1);
    assert!(matches!(store.begin_removal("1.0.0"), Err(Error::Busy)));
    store.anchors(None, Some("1.0.0")).unwrap();
    assert!(matches!(store.begin_removal("1.0.0"), Err(Error::Busy)));
    store.anchors(None, None).unwrap();
    let removal = store.begin_removal("1.0.0").unwrap();
    assert!(store.acquire("1.0.0", &manifest).is_err());
    drop(removal);
    assert!(store.acquire("1.0.0", &manifest).is_err());
    assert!(
        fixture
            .contract
            .inspect_cancellable(&prefix, &Cancellation::default())
            .is_err()
    );
}

#[test]
fn native_publication_identity_and_path_must_match_the_catalogue() {
    use cadrumo_application::installation::maintenance::{Identity, Store};
    let mut fixture = Fixture::new();
    let prefix = fixture.prefix("native");
    fixture.version(&prefix, "1.0.0");
    let store = fixture.native(&prefix);
    store.initialize().unwrap();
    let wrong = Store::new(
        prefix.join("data/installation-state"),
        Identity {
            application_id: "foreign".into(),
            channel: "stable".into(),
            platform: fixture.contract.layout.platform.clone(),
        },
        128,
    )
    .unwrap();
    assert!(wrong.initialize().is_err());
    let marker = prefix.join("data/installation.json");
    let mut value: serde_json::Value = serde_json::from_slice(&fs::read(&marker).unwrap()).unwrap();
    value["publication"] = json!("other/state");
    fs::write(marker, serde_json::to_vec(&value).unwrap()).unwrap();
    assert!(
        fixture
            .contract
            .inspect_cancellable(&prefix, &Cancellation::default())
            .is_err()
    );
}

#[test]
fn committed_registration_absence_is_positive_evidence_and_releases_anchors_atomically() {
    use cadrumo_application::{
        installation::maintenance::{
            NativeContext, NativeOwner, NativeProductInventory, RegistrationPhase,
        },
        value::Sha256Digest,
    };
    struct Inventory(bool);
    impl NativeProductInventory for Inventory {
        fn locate(&self, owner: &NativeOwner) -> Result<Option<NativeOwner>, Error> {
            Ok(self.0.then(|| owner.clone()))
        }
    }
    let mut fixture = Fixture::new();
    let prefix = fixture.prefix("registration");
    let package = fixture.version(&prefix, "1.0.0");
    let store = fixture.native(&prefix);
    store.initialize().unwrap();
    assert!(store.snapshot().unwrap().registration().is_none());
    let manifest = Sha256Digest::new(format!(
        "{:x}",
        Sha256::digest(fs::read(package.join("data/package-manifest.json")).unwrap())
    ))
    .unwrap();
    let owner = NativeOwner::new(
        "12345678-1234-1234-1234-123456789abc".into(),
        NativeContext::Machine,
        prefix.clone(),
    )
    .unwrap();
    let registration = NativeOwner::new(
        "22345678-1234-1234-1234-123456789abc".into(),
        NativeContext::Machine,
        prefix,
    )
    .unwrap();
    let writer = store
        .prepare("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    assert!(
        store
            .publish_registered("1.0.0", &package, &fixture.contract, true, owner)
            .is_err()
    );
    assert!(store.snapshot().unwrap().manager_anchor().is_none());
    store
        .publish_registered(
            "1.0.0",
            &package,
            &fixture.contract,
            true,
            registration.clone(),
        )
        .unwrap();
    drop(writer);
    let snapshot = store.snapshot().unwrap();
    assert_eq!(
        snapshot.registration().unwrap().phase,
        RegistrationPhase::Ready
    );
    assert_eq!(snapshot.manager_anchor(), Some("1.0.0"));
    assert_eq!(snapshot.desktop_anchor(), Some("1.0.0"));
    assert!(store.anchors(None, None).is_err());
    assert!(store.begin_removal("1.0.0").is_err());
    assert!(store.resume_removal("1.0.0").is_err());
    assert!(store.resume_registration_removal(&registration).is_err());
    let removal = store.begin_registration_removal(&registration).unwrap();
    assert!(store.exclusive_maintenance().is_err());
    drop(removal); // Interrupted uninstall is not positive absence evidence.
    assert_eq!(
        store.snapshot().unwrap().registration().unwrap().phase,
        RegistrationPhase::Removing
    );
    assert_eq!(store.snapshot().unwrap().manager_anchor(), Some("1.0.0"));
    let wrong_account = NativeOwner::new(
        registration.product_code().into(),
        NativeContext::User {
            sid: "S-1-5-21-1000".into(),
        },
        registration.prefix().to_owned(),
    )
    .unwrap();
    assert!(store.resume_registration_removal(&wrong_account).is_err());
    let resumed = store.resume_registration_removal(&registration).unwrap();
    assert!(store.exclusive_maintenance().is_err());
    drop(resumed);
    assert!(
        store
            .begin_registration_removal(&registration)
            .unwrap()
            .rollback(&fixture.contract, &Inventory(false))
            .is_err()
    );
    let stable = fixture
        .contract
        .manager_member()
        .unwrap()
        .under(registration.prefix());
    fs::write(&stable, b"damaged registration rollback").unwrap();
    assert!(
        store
            .begin_registration_removal(&registration)
            .unwrap()
            .rollback(&fixture.contract, &Inventory(true))
            .is_err()
    );
    fs::copy(&fixture.source, &stable).unwrap();
    store
        .begin_registration_removal(&registration)
        .unwrap()
        .rollback(&fixture.contract, &Inventory(true))
        .unwrap();
    assert_eq!(
        store.snapshot().unwrap().registration().unwrap().phase,
        RegistrationPhase::Ready
    );
    assert!(
        store
            .begin_registration_removal(&registration)
            .unwrap()
            .complete(&Inventory(true))
            .is_err()
    );
    store
        .resume_registration_removal(&registration)
        .unwrap()
        .complete(&Inventory(false))
        .unwrap();
    let snapshot = store.snapshot().unwrap();
    assert_eq!(
        snapshot.registration().unwrap().phase,
        RegistrationPhase::Absent
    );
    assert!(snapshot.manager_anchor().is_none());
    assert!(snapshot.desktop_anchor().is_none());
    assert!(store.acquire("1.0.0", &manifest).is_ok());
    assert!(store.begin_registration_removal(&registration).is_err());
    assert!(store.resume_registration_removal(&registration).is_err());
}

#[test]
fn native_repair_fences_discovery_and_removal_recovery_rechecks_native_and_file_ownership() {
    use cadrumo_application::{
        installation::maintenance::{NativeContext, NativeOwner, NativeProductInventory},
        value::Sha256Digest,
    };
    struct Inventory(Result<Option<NativeOwner>, &'static str>);
    impl NativeProductInventory for Inventory {
        fn locate(&self, _owner: &NativeOwner) -> Result<Option<NativeOwner>, Error> {
            self.0
                .clone()
                .map_err(|message| Error::Integrity(message.into()))
        }
    }
    let mut fixture = Fixture::new();
    let prefix = fixture.prefix("recovery");
    let package = fixture.version(&prefix, "1.0.0");
    let store = fixture.native(&prefix);
    store.initialize().unwrap();
    let manifest = Sha256Digest::new(format!(
        "{:x}",
        Sha256::digest(fs::read(package.join("data/package-manifest.json")).unwrap())
    ))
    .unwrap();
    let owner = NativeOwner::new(
        "12345678-1234-1234-1234-123456789abc".into(),
        NativeContext::Machine,
        prefix.clone(),
    )
    .unwrap();
    let install = store
        .prepare("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    assert!(store.begin_removal("1.0.0").is_err());
    assert!(store.resume_removal("1.0.0").is_err());
    store.publish("1.0.0", &package, &fixture.contract).unwrap();
    drop(install);
    assert!(store.resume_removal("1.0.0").is_err());
    let reader = store.acquire("1.0.0", &manifest).unwrap();
    assert!(matches!(
        store.prepare("1.0.0", owner.clone(), manifest.clone()),
        Err(Error::Busy)
    ));
    drop(reader);
    store.anchors(Some("1.0.0"), None).unwrap();
    assert!(matches!(
        store.prepare("1.0.0", owner.clone(), manifest.clone()),
        Err(Error::Busy)
    ));
    assert!(store.acquire("1.0.0", &manifest).is_ok());
    store.anchors(None, None).unwrap();
    let repair = store
        .prepare("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    drop(repair); // A dead installer leaves the durable Pending fence.
    assert!(store.acquire("1.0.0", &manifest).is_err());
    store.publish("1.0.0", &package, &fixture.contract).unwrap();

    let present = Inventory(Ok(Some(owner.clone())));
    let absent = Inventory(Ok(None));
    let unavailable = Inventory(Err("native inventory unavailable"));
    assert!(store.resume_removal("1.0.0").is_err());
    assert!(
        store
            .begin_removal("1.0.0")
            .unwrap()
            .complete(&present)
            .is_err()
    );
    assert!(store.acquire("1.0.0", &manifest).is_err());
    let resumed = store.resume_removal("1.0.0").unwrap();
    assert!(store.resume_removal("1.0.0").is_err());
    drop(resumed);
    assert!(
        store
            .resume_removal("1.0.0")
            .unwrap()
            .complete(&unavailable)
            .is_err()
    );
    assert!(
        store
            .begin_removal("1.0.0")
            .unwrap()
            .rollback(&fixture.contract, &absent)
            .is_err()
    );
    fs::write(package.join("python.zip"), b"damaged rollback").unwrap();
    assert!(
        store
            .begin_removal("1.0.0")
            .unwrap()
            .rollback(&fixture.contract, &present)
            .is_err()
    );
    fs::write(
        package.join("python.zip"),
        b"inventoried fixture dependency",
    )
    .unwrap();
    let different = NativeOwner::new(
        owner.product_code().into(),
        NativeContext::User {
            sid: "S-1-5-21-1000".into(),
        },
        prefix.clone(),
    )
    .unwrap();
    assert!(
        store
            .begin_removal("1.0.0")
            .unwrap()
            .rollback(&fixture.contract, &Inventory(Ok(Some(different))))
            .is_err()
    );
    store
        .begin_removal("1.0.0")
        .unwrap()
        .rollback(&fixture.contract, &present)
        .unwrap();
    assert!(store.acquire("1.0.0", &manifest).is_ok());
    assert!(store.resume_removal("1.0.0").is_err());
    drop(store.begin_removal("1.0.0").unwrap());
    store
        .resume_removal("1.0.0")
        .unwrap()
        .complete(&absent)
        .unwrap();
    assert!(store.acquire("1.0.0", &manifest).is_err());
    assert!(store.resume_removal("1.0.0").is_err());
    // Even after native absence, the shared owner never substitutes direct deletion.
    assert!(package.join("python.zip").is_file());
}

#[test]
fn install_rollback_restores_only_prior_verified_ready_state_and_forgets_proved_absence() {
    use cadrumo_application::{
        installation::maintenance::{
            NativeContext, NativeOwner, NativeProductInventory, RollbackPublication,
        },
        value::Sha256Digest,
    };
    struct Inventory(bool);
    impl NativeProductInventory for Inventory {
        fn locate(&self, owner: &NativeOwner) -> Result<Option<NativeOwner>, Error> {
            Ok(self.0.then(|| owner.clone()))
        }
    }
    let mut fixture = Fixture::new();
    let prefix = fixture.prefix("install-rollback");
    let package = fixture.version(&prefix, "1.0.0");
    let store = fixture.native(&prefix);
    store.initialize().unwrap();
    let manifest = Sha256Digest::new(format!(
        "{:x}",
        Sha256::digest(fs::read(package.join("data/package-manifest.json")).unwrap())
    ))
    .unwrap();
    let owner = NativeOwner::new(
        "12345678-1234-1234-1234-123456789abc".into(),
        NativeContext::Machine,
        prefix,
    )
    .unwrap();
    let fresh = store
        .prepare_transaction("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    assert_eq!(
        fresh
            .rollback(&fixture.contract, &Inventory(false))
            .unwrap(),
        RollbackPublication::ReservationRemoved
    );
    assert_eq!(store.snapshot().unwrap().versions().count(), 0);
    let fresh = store
        .prepare_transaction("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    assert!(fresh.rollback(&fixture.contract, &Inventory(true)).is_err());
    assert!(store.acquire("1.0.0", &manifest).is_err());
    let interrupted = store
        .prepare_transaction("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    assert_eq!(
        interrupted
            .rollback(&fixture.contract, &Inventory(true))
            .unwrap(),
        RollbackPublication::PendingRetained
    );
    assert!(store.acquire("1.0.0", &manifest).is_err());
    store.publish("1.0.0", &package, &fixture.contract).unwrap();
    let repair = store
        .prepare_transaction("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    assert!(store.acquire("1.0.0", &manifest).is_err());
    assert_eq!(
        repair
            .rollback(&fixture.contract, &Inventory(true))
            .unwrap(),
        RollbackPublication::ReadyRestored
    );
    assert!(store.acquire("1.0.0", &manifest).is_ok());
    let repair = store
        .prepare_transaction("1.0.0", owner, manifest.clone())
        .unwrap();
    fs::write(package.join("python.zip"), b"damaged rollback").unwrap();
    assert!(
        repair
            .rollback(&fixture.contract, &Inventory(true))
            .is_err()
    );
    assert!(store.acquire("1.0.0", &manifest).is_err());
}

#[test]
fn native_publication_rejects_foreign_paths_contexts_and_legacy_unscoped_state() {
    use cadrumo_application::{
        installation::maintenance::{NativeContext, NativeOwner},
        value::Sha256Digest,
    };
    let mut fixture = Fixture::new();
    let prefix = fixture.prefix("owner");
    let package = fixture.version(&prefix, "1.0.0");
    let other = fixture.prefix("foreign");
    let foreign_package = fixture.version(&other, "1.0.0");
    let store = fixture.native(&prefix);
    store.initialize().unwrap();
    let manifest = Sha256Digest::new(format!(
        "{:x}",
        Sha256::digest(fs::read(package.join("data/package-manifest.json")).unwrap())
    ))
    .unwrap();
    let owner = NativeOwner::new(
        "12345678-1234-1234-1234-123456789abc".into(),
        NativeContext::Machine,
        prefix.clone(),
    )
    .unwrap();
    let foreign_owner =
        NativeOwner::new(owner.product_code().into(), NativeContext::Machine, other).unwrap();
    assert!(
        store
            .prepare("1.0.0", foreign_owner, manifest.clone())
            .is_err()
    );
    let install = store
        .prepare("1.0.0", owner.clone(), manifest.clone())
        .unwrap();
    assert!(
        store
            .publish("1.0.0", &foreign_package, &fixture.contract)
            .is_err()
    );
    drop(install);
    let user_owner = NativeOwner::new(
        owner.product_code().into(),
        NativeContext::User {
            sid: "S-1-5-21-1000".into(),
        },
        prefix.clone(),
    )
    .unwrap();
    assert!(
        store
            .prepare("1.0.0", user_owner.clone(), manifest.clone())
            .is_err()
    );
    assert!(store.prepare("2.0.0", user_owner, manifest).is_err());
    for sid in ["", "S-1-1-0", "S-1-5--1", "S-1-05-21", "S-1-5-4294967296"] {
        assert!(
            NativeOwner::new(
                owner.product_code().into(),
                NativeContext::User { sid: sid.into() },
                prefix.clone()
            )
            .is_err()
        );
    }
    let state_path = prefix.join("data/installation-state/state.json");
    let mut state: serde_json::Value =
        serde_json::from_slice(&fs::read(&state_path).unwrap()).unwrap();
    state["schema"] = json!(1);
    fs::write(&state_path, serde_json::to_vec(&state).unwrap()).unwrap();
    assert!(store.initialize().is_err());
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
        let result = fixture
            .contract
            .discover(&image, &RegistrationHints::default())
            .unwrap();
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
            &RegistrationHints {
                this_user: Some(&member.under(&prefix)),
                ..Default::default()
            },
            &cancellation
        ),
        Err(Error::Cancelled)
    ));
    assert_eq!(
        fixture
            .contract
            .discover(&member.under(&package), &RegistrationHints::default())
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
    let fallback_entry = member.under(&fallback);
    let registered = RegistrationHints {
        all_users: Some(&fallback_entry),
        ..Default::default()
    };
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
        let selected = fixture
            .contract
            .discover(&image, &RegistrationHints::default())
            .unwrap();
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
        .discover(
            &member.under(&old),
            &RegistrationHints {
                this_user: Some(&member.under(&user)),
                ..Default::default()
            },
        )
        .unwrap();
    assert_eq!(result.package, newest);
    fs::write(member.under(&user), b"damaged stable entry").unwrap();
    assert_eq!(
        fixture
            .contract
            .discover(
                &member.under(&old),
                &RegistrationHints {
                    this_user: Some(&member.under(&user)),
                    ..Default::default()
                }
            )
            .unwrap()
            .package,
        old
    );
}

#[test]
fn verified_this_user_registration_precedes_newer_machine_and_local_versions() {
    let fixture = Fixture::new();
    let machine = fixture.prefix("machine ü prefix");
    let newer_machine = fixture.version(&machine, "3.0.0");
    let user = fixture.prefix("user ü prefix");
    let older_user = fixture.version(&user, "1.0.0");
    let member = fixture.contract.manager_member().unwrap();
    let user_entry = member.under(&user);
    let machine_entry = member.under(&machine);
    let hints = RegistrationHints {
        this_user: Some(&user_entry),
        all_users: Some(&machine_entry),
    };
    for image in [
        &machine_entry,
        &member.under(&newer_machine),
        &user_entry,
        &member.under(&older_user),
    ] {
        assert_eq!(
            fixture.contract.discover(image, &hints).unwrap().package,
            older_user
        );
    }
    fs::write(older_user.join("python.zip"), b"corrupted user package").unwrap();
    assert_eq!(
        fixture
            .contract
            .discover(&machine_entry, &hints)
            .unwrap()
            .package,
        newer_machine
    );
}

#[test]
fn a_local_prefix_does_not_become_user_scope_without_a_matching_registration() {
    let fixture = Fixture::new();
    let local = fixture.prefix("unregistered archive");
    let old = fixture.version(&local, "1.0.0");
    let machine = fixture.prefix("registered machine");
    let newest = fixture.version(&machine, "2.0.0");
    let member = fixture.contract.manager_member().unwrap();
    let machine_entry = member.under(&machine);
    let hints = RegistrationHints {
        all_users: Some(&machine_entry),
        ..Default::default()
    };
    assert_eq!(
        fixture
            .contract
            .discover(&member.under(&old), &hints)
            .unwrap()
            .package,
        newest
    );
    let unrelated_entry = machine.join("other.exe");
    let unrelated = RegistrationHints {
        this_user: Some(&unrelated_entry),
        ..Default::default()
    };
    assert_eq!(
        fixture
            .contract
            .discover(&member.under(&old), &unrelated)
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
