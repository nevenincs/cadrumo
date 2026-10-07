//! Query the actual packaged interpreter with the production strict projection.
#![cfg(feature = "live-package-tests")]

use cadrumo_application::{child::ChildConfiguration, runtime};
use cadrumo_manager::{contract, supervision::environment::runtime_environment};
use std::{fs, path::PathBuf, time::Duration};

#[test]
fn packaged_identity_is_stable_and_does_not_acquire_runtime_ownership() {
    let package = PathBuf::from(
        std::env::var_os("CADRUMO_TEST_PACKAGE_ROOT")
            .expect("live-package-tests requires CADRUMO_TEST_PACKAGE_ROOT"),
    );
    let root =
        std::env::temp_dir().join(format!("cadrumo-manager-identity-{}", std::process::id()));
    fs::create_dir(&root).expect("fresh isolated root");
    struct Cleanup(PathBuf);
    impl Drop for Cleanup {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    let _cleanup = Cleanup(root.clone());
    let environment = runtime_environment(&root, Some(&package), std::env::vars_os()).unwrap();
    let configuration = ChildConfiguration::new(
        package.join(contract::EXECUTABLE),
        package.clone(),
        environment.into_iter().collect(),
    )
    .unwrap();
    let executor = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    let first = executor
        .block_on(runtime::identity(&configuration, Duration::from_secs(30)))
        .unwrap();
    let second = executor
        .block_on(runtime::identity(&configuration, Duration::from_secs(30)))
        .unwrap();
    assert_eq!(
        fs::canonicalize(first.storage).unwrap(),
        fs::canonicalize(&root).unwrap()
    );
    assert_eq!(first.storage_identity, second.storage_identity);
    assert_eq!(first.version, cadrumo_manager::identity::VERSION);
    assert!(
        matches!(
            executor.block_on(runtime::identity(&configuration, Duration::from_nanos(1))),
            Err(cadrumo_application::error::Error::TimedOut)
        ),
        "the identity query must terminate and reap its child on deadline"
    );
    assert!(
        !root.join(".runtime/boot.json").exists(),
        "identity query started a runtime"
    );
    assert!(
        !root.join(".runtime/manager-start.lock").exists(),
        "identity query took ownership"
    );
    #[cfg(all(windows, feature = "fixture-test-mode"))]
    start_packaged_runtime(&package, &root, first.storage_identity, first.version);
}

/// Exercise the composed supervisor against a real packaged native runtime.
/// Fixture mode changes only the isolated root/admission used by this test;
/// it never starts the GUI manager in the user's session or storage.
#[cfg(all(windows, feature = "fixture-test-mode"))]
fn start_packaged_runtime(
    package: &std::path::Path,
    root: &std::path::Path,
    identity: String,
    version: String,
) {
    use cadrumo_manager::{
        session::{
            ManagerSession,
            ownership::{BootRecordLocator, Ownership, StartKind},
        },
        startup::{self, Start},
        supervision::{
            adoption::{InstalledVersion, InstalledVersions},
            launch::{LaunchTarget, runtime_image},
            stop::PlatformStopSignal,
            supervisor::{
                Collaborators, Event, Outcome, Request, SessionActivity, SupervisorConfig,
                VersionProbe,
            },
        },
    };
    struct Active;
    impl SessionActivity for Active {
        fn is_active(&self) -> bool {
            true
        }
    }
    struct NoAdoption;
    impl VersionProbe for NoAdoption {
        fn reprobe(&mut self) -> Option<String> {
            None
        }
    }
    impl InstalledVersions for NoAdoption {
        fn containing(&self, _: &std::path::Path) -> Option<InstalledVersion> {
            None
        }
        fn failed(&self, _: &str) -> bool {
            true
        }
    }
    let target =
        LaunchTarget::fixture(runtime_image(package), root.to_owned(), identity, version).unwrap();
    let mut ownership = Ownership::new(
        root.to_owned(),
        ManagerSession::current().unwrap(),
        Box::new(Active),
        Box::new(BootRecordLocator::new(root)),
    );
    let Start::Running(mut running) = startup::start(
        target,
        SupervisorConfig::default(),
        Collaborators {
            session: Box::new(Active),
            probe: Box::new(NoAdoption),
            versions: Box::new(NoAdoption),
            stop_signal: Box::new(PlatformStopSignal::default()),
        },
        &mut ownership,
        Some(StartKind::Manual),
    )
    .unwrap() else {
        panic!("fresh isolated root must start");
    };
    let deadline = std::time::Instant::now() + Duration::from_secs(60);
    let ready = loop {
        match running
            .events
            .recv_timeout(deadline.saturating_duration_since(std::time::Instant::now()))
        {
            Ok(Event::Ready { .. }) => break true,
            Ok(_) if std::time::Instant::now() < deadline => {}
            _ => break false,
        }
    };
    // Always request cleanup before asserting, including failed readiness.
    running.handle.request(Request::SessionEnd);
    let ended = running.ended.recv_timeout(Duration::from_secs(12));
    if ended.is_ok() {
        running.join().unwrap();
    }
    assert!(ready, "packaged native runtime did not become ready");
    assert!(matches!(ended.unwrap().unwrap(), Outcome::Stopped { .. }));
    assert!(
        !root.join(".runtime/boot.json").exists(),
        "packaged runtime retained its boot record after exit"
    );
}
