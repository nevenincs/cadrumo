//! Explicit acceptance against a selected staged or independently relocated package.
#![cfg(feature = "live-package-tests")]
use cadrumo_application::{
    child::ChildConfiguration,
    component::Cancellation,
    package::Readiness,
    provisioning::{
        browser::{BrowserLayout, DRIVER_PACKAGE, DriverManifest},
        pins::{ComponentPins, Platform},
        receipts::ReceiptReading,
        state::Observation,
    },
    python::{self, PythonExpectation},
    value::RelativePath,
};
use std::{path::PathBuf, time::Duration};

#[tokio::test]
async fn manifest_cohort_matches_selected_packaged_interpreter() {
    let root = PathBuf::from(
        std::env::var_os("CADRUMO_TEST_PACKAGE_ROOT")
            .expect("CADRUMO_TEST_PACKAGE_ROOT is required"),
    );
    let manifest_path = RelativePath::new(
        std::env::var("CADRUMO_TEST_PACKAGE_MANIFEST")
            .expect("CADRUMO_TEST_PACKAGE_MANIFEST is required from the selected layout"),
    )
    .unwrap();
    let manifest_bytes = std::fs::read(manifest_path.under(&root)).unwrap();
    let layout: serde_json::Value = serde_json::from_slice(&manifest_bytes).unwrap();
    let executable = RelativePath::new(
        layout["layout"]["paths"]["executable"]
            .as_str()
            .expect("projected executable path"),
    )
    .unwrap();
    let platform = std::env::var("CADRUMO_TEST_PACKAGE_PLATFORM")
        .expect("CADRUMO_TEST_PACKAGE_PLATFORM is required from the selected layout");
    let abi = std::env::var("CADRUMO_TEST_PACKAGE_ABI")
        .expect("CADRUMO_TEST_PACKAGE_ABI is required from the selected layout")
        .parse()
        .expect("package ABI must be an integer");
    #[cfg(feature = "live-release-tests")]
    let inspection = {
        use cadrumo_application::package::release::{ReleaseExpectation, inspect_release};
        let expectations = std::env::var_os("CADRUMO_TEST_RELEASE_EXPECTATION").expect(
            "CADRUMO_TEST_RELEASE_EXPECTATION must name verifier-supplied release expectations",
        );
        let expected: ReleaseExpectation =
            serde_json::from_slice(&std::fs::read(expectations).unwrap()).unwrap();
        assert_eq!(expected.platform, platform);
        assert_eq!(expected.abi, abi);
        inspect_release(&root, &manifest_path, &expected).unwrap()
    };
    #[cfg(not(feature = "live-release-tests"))]
    let inspection = cadrumo_application::package::PackageManifest::read(&root, &manifest_path)
        .unwrap()
        .inspect(&root, &manifest_path, &platform, abi)
        .unwrap();
    assert_eq!(inspection.readiness, Readiness::Ready);
    let expected = PythonExpectation::from_manifest(&inspection.manifest, &executable).unwrap();
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let configuration = ChildConfiguration::from_platform(
        executable.under(&root),
        directory.path().to_owned(),
        directory.path(),
        std::env::vars_os(),
    )
    .unwrap();
    let report = python::probe(
        &configuration,
        &expected,
        Duration::from_secs(60),
        &Cancellation::default(),
    )
    .await
    .unwrap();
    let package_path = |key: &str| {
        RelativePath::new(
            layout["layout"]["paths"][key]
                .as_str()
                .expect("projected package path"),
        )
        .unwrap()
        .under(&root)
    };
    let driver = DriverManifest::read(&package_path("packages").join(DRIVER_PACKAGE)).unwrap();
    let pins = ComponentPins::load(&package_path("component_pins")).unwrap();
    let browser_root = directory.path().join("empty-browser-cache");
    let browser = BrowserLayout::new(
        browser_root.clone(),
        &driver,
        pins.browser.as_ref(),
        Platform::current().expect("supported package host"),
    )
    .unwrap();
    assert!(
        browser.pinned(),
        "package browser pins must cover its driver"
    );
    assert_eq!(
        browser.quick_check(&ReceiptReading::Absent).observation,
        Observation::Absent
    );
    assert!(!browser_root.exists(), "browser inspection created data");
    assert_eq!(
        std::fs::read(manifest_path.under(&root)).unwrap(),
        manifest_bytes,
        "probe changed manifest"
    );
    let after = inspection
        .manifest
        .inspect(&root, &manifest_path, &platform, abi)
        .unwrap();
    assert_eq!(
        after.readiness,
        Readiness::Ready,
        "probe changed package inventory"
    );
    println!(
        "Packaged CPython {}: {} exact distribution versions; browser absent",
        report.version,
        report.distributions.len()
    );
}
