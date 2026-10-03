use cadrumo_application::{
    capability::{Capability, Requirement},
    child::ChildConfiguration,
    component::{Artifact, Cancellation, ComponentStore},
    error::Error,
    package::{PackageManifest, Readiness},
    value::{RelativePath, Sha256Digest},
};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    ffi::OsString,
    fs,
    io::{Cursor, Read, Write},
    path::Path,
    sync::{Arc, Barrier},
};
use zip::{ZipWriter, write::SimpleFileOptions};

fn directory() -> tempfile::TempDir {
    let root = Path::new(env!("CARGO_TARGET_TMPDIR"));
    fs::create_dir_all(root).unwrap();
    tempfile::tempdir_in(root).unwrap()
}

fn archive(entries: &[(&str, &[u8])]) -> Vec<u8> {
    let mut zip = ZipWriter::new(Cursor::new(Vec::new()));
    for (name, content) in entries {
        zip.start_file(*name, SimpleFileOptions::default().unix_permissions(0o755))
            .unwrap();
        zip.write_all(content).unwrap();
    }
    zip.finish().unwrap().into_inner()
}

fn artifact(bytes: &[u8], revision: &str) -> Artifact {
    Artifact {
        id: "chromium".into(),
        revision: revision.into(),
        target: "fixture-target".into(),
        sha256: Sha256Digest::new(format!("{:x}", Sha256::digest(bytes))).unwrap(),
        archive_bytes: bytes.len() as u64,
        max_unpacked_bytes: 100_000,
        max_entries: 100,
        executable: RelativePath::new("chrome/browser").unwrap(),
        url: None,
    }
}

fn package(root: &Path) -> RelativePath {
    fs::write(root.join("python.zip"), b"abc").unwrap();
    let manifest = serde_json::json!({
        "layout": {"abi": 1, "platform": "projected-target", "paths": {"stdlib": "python.zip"}},
        "python": "3.13.11", "distributions": {"cadrumo": "0.5.1"},
        "files": {"python.zip": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
        "build": {"version": "0.5.1"}
    });
    fs::write(
        root.join("manifest.json"),
        serde_json::to_vec(&manifest).unwrap(),
    )
    .unwrap();
    RelativePath::new("manifest.json").unwrap()
}

#[test]
fn manifest_inspection_detects_missing_corrupt_extra_and_incompatible_files() {
    let temp = directory();
    let path = package(temp.path());
    let inspect = |target, abi| {
        PackageManifest::read(temp.path(), &path)
            .unwrap()
            .inspect(temp.path(), &path, target, abi)
            .unwrap()
            .readiness
    };
    assert_eq!(inspect("projected-target", 1), Readiness::Ready);
    assert!(matches!(inspect("other", 1), Readiness::Incompatible(_)));
    assert!(matches!(
        inspect("projected-target", 2),
        Readiness::Incompatible(_)
    ));
    fs::write(temp.path().join("unexpected"), b"x").unwrap();
    assert!(matches!(
        inspect("projected-target", 1),
        Readiness::Incompatible(_)
    ));
    fs::remove_file(temp.path().join("unexpected")).unwrap();
    fs::write(temp.path().join("python.zip"), b"abd").unwrap();
    assert!(matches!(
        inspect("projected-target", 1),
        Readiness::Incompatible(_)
    ));
    fs::remove_file(temp.path().join("python.zip")).unwrap();
    assert!(matches!(
        inspect("projected-target", 1),
        Readiness::Missing(_)
    ));
}

#[test]
fn portable_paths_reject_all_platform_escapes_and_aliases() {
    for path in [
        "",
        "../x",
        "a/../../x",
        "/tmp/x",
        "C:/x",
        "a\\x",
        "a//x",
        "./x",
        "NUL",
        "a/COM1.txt",
        "a/x.",
        "a/x ",
        "a:x",
        "a\0x",
    ] {
        assert!(RelativePath::new(path).is_err(), "accepted {path:?}");
    }
    assert!(RelativePath::new("á 漢字/chrome").is_ok());
    assert!(Sha256Digest::new("not a hash").is_err());
}

#[test]
fn capability_reports_optional_dependency_user_action_and_unimplemented_flow() {
    let temp = directory();
    let path = package(temp.path());
    let inspection = PackageManifest::read(temp.path(), &path)
        .unwrap()
        .inspect(temp.path(), &path, "projected-target", 1)
        .unwrap();
    let capability = Capability {
        id: "google".into(),
        requirements: vec![
            Requirement::PythonDistribution {
                name: "google-api-python-client".into(),
                version: "1".into(),
            },
            Requirement::UserAction {
                action: "Connect Google account".into(),
            },
            Requirement::Unimplemented {
                reason: "Public client registration not provisioned".into(),
            },
        ],
    };
    let findings = capability.inspect(&inspection, &BTreeMap::new());
    assert!(matches!(
        findings.as_slice(),
        [
            Readiness::Missing(_),
            Readiness::NeedsUser(_),
            Readiness::Incompatible(_)
        ]
    ));
}

#[test]
fn child_configuration_is_an_immutable_complete_environment() {
    if std::env::var("CADRUMO_TEST_VALUE").as_deref() == Ok("selected") {
        for absent in ["PATH", "PYTHONPATH", "CARGO_TARGET_DIR", "HOME"] {
            assert!(std::env::var_os(absent).is_none(), "inherited {absent}");
        }
        return;
    }
    let temp = directory();
    let before: BTreeMap<_, _> = std::env::vars_os().collect();
    let environment = BTreeMap::from([(
        OsString::from("CADRUMO_TEST_VALUE"),
        OsString::from("selected"),
    )]);
    let configuration = ChildConfiguration::new(
        std::env::current_exe().unwrap(),
        temp.path().into(),
        environment.clone(),
    )
    .unwrap();
    let command = configuration.command();
    let actual: BTreeMap<_, _> = command
        .get_envs()
        .map(|(k, v)| (k.to_os_string(), v.unwrap().to_os_string()))
        .collect();
    assert_eq!(actual, environment);
    let child = configuration
        .command()
        .args([
            "--exact",
            "child_configuration_is_an_immutable_complete_environment",
            "--nocapture",
        ])
        .output()
        .unwrap();
    assert!(
        child.status.success(),
        "{}",
        String::from_utf8_lossy(&child.stderr)
    );
    assert_eq!(std::env::vars_os().collect::<BTreeMap<_, _>>(), before);
    let ambiguous = BTreeMap::from([
        (OsString::from("PATH"), OsString::new()),
        (OsString::from("Path"), OsString::new()),
    ]);
    assert!(
        ChildConfiguration::new(
            std::env::current_exe().unwrap(),
            temp.path().into(),
            ambiguous
        )
        .is_err()
    );
}

#[test]
fn inspection_does_not_create_store_or_download() {
    let temp = directory();
    let root = temp.path().join("absent");
    let store = ComponentStore::new(root.clone(), "fixture-target".into()).unwrap();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    assert!(matches!(
        store.inspect(&artifact(&bytes, "1")).unwrap().readiness,
        Readiness::Missing(_)
    ));
    assert!(!root.exists());
}

#[test]
fn install_upgrade_and_reuse_preserve_previous_version() {
    let temp = directory();
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    let first = archive(&[("chrome/browser", b"version one")]);
    let first_spec = artifact(&first, "1");
    let installed = store
        .provision(
            &first_spec,
            || Ok(Cursor::new(&first)),
            &Cancellation::default(),
        )
        .unwrap();
    assert_eq!(fs::read(&installed.executable).unwrap(), b"version one");
    assert_eq!(
        store.inspect(&first_spec).unwrap().readiness,
        Readiness::Ready
    );
    store
        .provision::<Cursor<Vec<u8>>>(
            &first_spec,
            || panic!("ready component downloaded"),
            &Cancellation::default(),
        )
        .unwrap();
    let next = archive(&[("chrome/browser", b"version two")]);
    let next_spec = artifact(&next, "2");
    let upgraded = store
        .provision(
            &next_spec,
            || Ok(Cursor::new(&next)),
            &Cancellation::default(),
        )
        .unwrap();
    assert_eq!(fs::read(upgraded.executable).unwrap(), b"version two");
    assert_eq!(fs::read(installed.executable).unwrap(), b"version one");
    assert_eq!(
        store.inspect(&next_spec).unwrap().readiness,
        Readiness::Ready
    );
}

#[test]
fn bad_digest_failed_activation_and_cancellation_keep_active_version() {
    let temp = directory();
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    let first = archive(&[("chrome/browser", b"first")]);
    let original = artifact(&first, "1");
    store
        .provision(
            &original,
            || Ok(Cursor::new(&first)),
            &Cancellation::default(),
        )
        .unwrap();
    let bytes = archive(&[("chrome/browser", b"second")]);
    let mut bad = artifact(&bytes, "2");
    bad.sha256 = Sha256Digest::new("0".repeat(64)).unwrap();
    assert!(matches!(
        store.provision(&bad, || Ok(Cursor::new(&bytes)), &Cancellation::default()),
        Err(Error::Integrity(_))
    ));
    assert_eq!(
        store.inspect(&original).unwrap().readiness,
        Readiness::Ready
    );
    let next = artifact(&bytes, "2");
    let cancellation = Cancellation::default();
    cancellation.cancel();
    assert!(matches!(
        store.provision::<Cursor<Vec<u8>>>(
            &next,
            || panic!("cancelled source opened"),
            &cancellation
        ),
        Err(Error::Cancelled)
    ));
    assert_eq!(
        store.inspect(&original).unwrap().readiness,
        Readiness::Ready
    );
    let pointer_obstacle = temp.path().join("chromium/active.next.json");
    let failed = store.provision(
        &next,
        || {
            fs::create_dir(&pointer_obstacle).unwrap();
            Ok(Cursor::new(&bytes))
        },
        &Cancellation::default(),
    );
    assert!(failed.is_err());
    assert_eq!(
        store.inspect(&original).unwrap().readiness,
        Readiness::Ready
    );
    fs::remove_dir(pointer_obstacle).unwrap();
    store
        .provision::<Cursor<Vec<u8>>>(
            &next,
            || panic!("completed version redownloaded"),
            &Cancellation::default(),
        )
        .unwrap();
    assert_eq!(store.inspect(&next).unwrap().readiness, Readiness::Ready);
}

#[test]
fn wrong_target_fails_before_source_or_filesystem_effects() {
    let temp = directory();
    let root = temp.path().join("absent");
    let store = ComponentStore::new(root.clone(), "other-target".into()).unwrap();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let result = store.provision::<Cursor<Vec<u8>>>(
        &artifact(&bytes, "1"),
        || panic!("foreign source opened"),
        &Cancellation::default(),
    );
    assert!(matches!(result, Err(Error::Incompatible(_))));
    assert!(!root.exists());
}

#[test]
fn extraction_refuses_traversal_case_aliases_missing_executable_and_limits() {
    for bad_path in [
        "../escape",
        "C:/escape",
        "chrome\\escape",
        "chrome/../../escape",
        "NUL",
    ] {
        let temp = directory();
        let bytes = archive(&[("chrome/browser", b"browser"), (bad_path, b"escape")]);
        let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
        assert!(
            store
                .provision(
                    &artifact(&bytes, "1"),
                    || Ok(Cursor::new(&bytes)),
                    &Cancellation::default()
                )
                .is_err(),
            "accepted {bad_path}"
        );
        assert!(!temp.path().join("chromium/active.json").exists());
        assert!(!temp.path().join("chromium/staging").exists());
    }
    for entries in [
        vec![
            ("chrome/browser", b"x".as_slice()),
            ("CHROME/BROWSER", b"y".as_slice()),
        ],
        vec![("other", b"x".as_slice())],
    ] {
        let temp = directory();
        let bytes = archive(&entries);
        let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
        assert!(
            store
                .provision(
                    &artifact(&bytes, "1"),
                    || Ok(Cursor::new(&bytes)),
                    &Cancellation::default()
                )
                .is_err()
        );
    }
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"too large")]);
    let mut spec = artifact(&bytes, "1");
    spec.max_unpacked_bytes = 2;
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    assert!(matches!(
        store.provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default()),
        Err(Error::LimitExceeded)
    ));
}

#[test]
fn extraction_refuses_symbolic_links() {
    let temp = directory();
    let mut zip = ZipWriter::new(Cursor::new(Vec::new()));
    zip.add_symlink(
        "chrome/browser",
        "../../outside",
        SimpleFileOptions::default(),
    )
    .unwrap();
    let bytes = zip.finish().unwrap().into_inner();
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    assert!(matches!(
        store.provision(
            &artifact(&bytes, "1"),
            || Ok(Cursor::new(&bytes)),
            &Cancellation::default()
        ),
        Err(Error::Invalid(_))
    ));
}

#[test]
fn stale_staging_is_recovered_under_os_writer_lock() {
    let temp = directory();
    let stage = temp.path().join("chromium/staging/partial");
    fs::create_dir_all(&stage).unwrap();
    fs::write(stage.join("incomplete"), b"truncated").unwrap();
    fs::write(temp.path().join("chromium/active.next.json"), b"truncated").unwrap();
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let spec = artifact(&bytes, "1");
    store
        .provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    assert!(!stage.exists());
    assert_eq!(store.inspect(&spec).unwrap().readiness, Readiness::Ready);
}

#[test]
fn concurrent_writer_is_refused_without_opening_its_source() {
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let spec = artifact(&bytes, "1");
    let root = temp.path().to_path_buf();
    let barrier = Arc::new(Barrier::new(2));
    std::thread::scope(|scope| {
        let barrier_worker = barrier.clone();
        let spec_worker = spec.clone();
        let root_worker = root.clone();
        let worker = scope.spawn(move || {
            let store = ComponentStore::new(root_worker, "fixture-target".into()).unwrap();
            store
                .provision(
                    &spec_worker,
                    || {
                        barrier_worker.wait();
                        barrier_worker.wait();
                        Ok(Cursor::new(bytes))
                    },
                    &Cancellation::default(),
                )
                .unwrap();
        });
        barrier.wait();
        let store = ComponentStore::new(root, "fixture-target".into()).unwrap();
        let result = store.provision::<Cursor<Vec<u8>>>(
            &spec,
            || panic!("competing source opened"),
            &Cancellation::default(),
        );
        barrier.wait();
        worker.join().unwrap();
        assert!(matches!(result, Err(Error::Busy)));
    });
}

struct CancelDuringRead<'a> {
    cursor: Cursor<Vec<u8>>,
    cancellation: &'a Cancellation,
}
impl Read for CancelDuringRead<'_> {
    fn read(&mut self, buffer: &mut [u8]) -> std::io::Result<usize> {
        let count = self.cursor.read(buffer)?;
        self.cancellation.cancel();
        Ok(count)
    }
}

#[test]
fn cancellation_during_download_cleans_partial_state() {
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let spec = artifact(&bytes, "1");
    let cancellation = Cancellation::default();
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    let result = store.provision(
        &spec,
        || {
            Ok(CancelDuringRead {
                cursor: Cursor::new(bytes),
                cancellation: &cancellation,
            })
        },
        &cancellation,
    );
    assert!(matches!(result, Err(Error::Cancelled)));
    assert!(!temp.path().join("chromium/staging").exists());
    assert!(!temp.path().join("chromium/active.json").exists());
}

#[test]
fn mutated_or_extra_payload_is_never_ready() {
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let spec = artifact(&bytes, "1");
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    let active = store
        .provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    fs::write(active.root.join("unexpected"), b"x").unwrap();
    assert!(matches!(
        store.inspect(&spec).unwrap().readiness,
        Readiness::Incompatible(_)
    ));
    fs::remove_file(active.root.join("unexpected")).unwrap();
    fs::write(active.executable, b"changed").unwrap();
    assert!(matches!(
        store.inspect(&spec).unwrap().readiness,
        Readiness::Incompatible(_)
    ));
}

#[test]
fn explicit_repair_retains_damaged_tree_and_activates_verified_generation() {
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let mut spec = artifact(&bytes, "1");
    spec.max_unpacked_bytes = 7;
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    let original = store
        .provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    fs::write(&original.executable, b"damaged and oversized").unwrap();
    assert!(matches!(
        store.inspect(&spec).unwrap().readiness,
        Readiness::Incompatible(_)
    ));
    let repaired = store
        .provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    assert_ne!(original.root, repaired.root);
    assert_eq!(
        fs::read(original.executable).unwrap(),
        b"damaged and oversized"
    );
    assert_eq!(fs::read(repaired.executable).unwrap(), b"browser");
    assert_eq!(store.inspect(&spec).unwrap().readiness, Readiness::Ready);
}

#[test]
fn mirror_rotation_preserves_ready_content_identity() {
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let mut spec = artifact(&bytes, "1");
    spec.url = Some("https://first.invalid/chromium.zip".into());
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    store
        .provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    spec.url = Some("https://second.invalid/chromium.zip".into());
    assert_eq!(store.inspect(&spec).unwrap().readiness, Readiness::Ready);
    store
        .provision::<Cursor<Vec<u8>>>(
            &spec,
            || panic!("identical content downloaded"),
            &Cancellation::default(),
        )
        .unwrap();
}

#[test]
fn cache_admission_counts_archive_directories_too() {
    let temp = directory();
    let mut zip = ZipWriter::new(Cursor::new(Vec::new()));
    zip.add_directory("chrome/", SimpleFileOptions::default())
        .unwrap();
    zip.start_file(
        "chrome/browser",
        SimpleFileOptions::default().unix_permissions(0o755),
    )
    .unwrap();
    zip.write_all(b"browser").unwrap();
    let bytes = zip.finish().unwrap().into_inner();
    let mut spec = artifact(&bytes, "1");
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    store
        .provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    spec.max_entries = 1;
    assert!(matches!(
        store.inspect(&spec).unwrap().readiness,
        Readiness::Incompatible(_)
    ));
    assert!(matches!(
        store.provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default()),
        Err(Error::LimitExceeded)
    ));
}

#[cfg(unix)]
#[test]
fn unix_backslash_filename_cannot_alias_inventory_path() {
    let temp = directory();
    let path = package(temp.path());
    fs::write(temp.path().join("extra\\file"), b"x").unwrap();
    let result = PackageManifest::read(temp.path(), &path).unwrap().inspect(
        temp.path(),
        &path,
        "projected-target",
        1,
    );
    assert!(result.is_err());
    let store_root = directory();
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let spec = artifact(&bytes, "1");
    let store = ComponentStore::new(store_root.path().into(), "fixture-target".into()).unwrap();
    let active = store
        .provision(&spec, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    fs::write(active.root.join("chrome\\browser"), b"unexpected alias").unwrap();
    assert!(store.inspect(&spec).is_err());
}

#[test]
fn https_transport_refuses_untrusted_scheme_without_effects() {
    let temp = directory();
    let root = temp.path().join("absent");
    let bytes = archive(&[("chrome/browser", b"browser")]);
    let mut spec = artifact(&bytes, "1");
    spec.url = Some("http://localhost/component.zip".into());
    let store = ComponentStore::new(root.clone(), "fixture-target".into()).unwrap();
    assert!(matches!(
        store.download_and_activate(&spec, &Cancellation::default()),
        Err(Error::Invalid(_))
    ));
    assert!(!root.exists());
}

#[test]
fn archive_parent_case_alias_is_rejected_on_every_host() {
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"browser"), ("CHROME/data", b"data")]);
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    assert!(matches!(
        store.provision(
            &artifact(&bytes, "1"),
            || Ok(Cursor::new(&bytes)),
            &Cancellation::default()
        ),
        Err(Error::Invalid(_))
    ));
}

#[test]
fn killed_writer_releases_lock_and_preserves_previous_component() {
    let next_bytes = archive(&[("chrome/browser", b"after interruption")]);
    let next = artifact(&next_bytes, "2");
    if let Some(root) = std::env::var_os("CADRUMO_INTERRUPT_ROOT") {
        let root = std::path::PathBuf::from(root);
        let store = ComponentStore::new(root.clone(), "fixture-target".into()).unwrap();
        store
            .provision::<Cursor<Vec<u8>>>(
                &next,
                || {
                    fs::write(root.join("writer-ready"), b"locked").unwrap();
                    loop {
                        std::thread::park();
                    }
                },
                &Cancellation::default(),
            )
            .unwrap();
        return;
    }
    let temp = directory();
    let bytes = archive(&[("chrome/browser", b"before interruption")]);
    let first = artifact(&bytes, "1");
    let store = ComponentStore::new(temp.path().into(), "fixture-target".into()).unwrap();
    store
        .provision(&first, || Ok(Cursor::new(&bytes)), &Cancellation::default())
        .unwrap();
    let mut child = std::process::Command::new(std::env::current_exe().unwrap())
        .args([
            "--exact",
            "killed_writer_releases_lock_and_preserves_previous_component",
        ])
        .env("CADRUMO_INTERRUPT_ROOT", temp.path())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .unwrap();
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
    while !temp.path().join("writer-ready").exists() && std::time::Instant::now() < deadline {
        std::thread::sleep(std::time::Duration::from_millis(20));
    }
    let acquired = temp.path().join("writer-ready").exists();
    child.kill().unwrap();
    child.wait().unwrap();
    assert!(acquired, "child did not acquire the writer lock");
    assert_eq!(store.inspect(&first).unwrap().readiness, Readiness::Ready);
    store
        .provision(
            &next,
            || Ok(Cursor::new(&next_bytes)),
            &Cancellation::default(),
        )
        .unwrap();
    assert_eq!(store.inspect(&next).unwrap().readiness, Readiness::Ready);
}

#[cfg(unix)]
#[test]
fn linked_store_root_is_refused() {
    let temp = directory();
    let outside = directory();
    let link = temp.path().join("linked");
    std::os::unix::fs::symlink(outside.path(), &link).unwrap();
    assert!(matches!(
        ComponentStore::new(link, "fixture-target".into()),
        Err(Error::Invalid(_))
    ));
    assert_eq!(fs::read_dir(outside.path()).unwrap().count(), 0);
}
