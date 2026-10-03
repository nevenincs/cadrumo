//! Explicit acceptance against a separately extracted artifact, never the assembler's tree.
#![cfg(feature = "live-package-tests")]
use cadrumo_application::{
    child::ChildConfiguration,
    component::Cancellation,
    package::{PackageManifest, Readiness},
    python::{self, BrowserQuery, PythonExpectation},
    value::RelativePath,
};
use std::{collections::BTreeMap, path::PathBuf, time::Duration};

#[tokio::test]
async fn manifest_cohort_matches_relocated_packaged_interpreter() {
    let root = PathBuf::from(
        std::env::var_os("CADRUMO_TEST_PACKAGE_ROOT")
            .expect("CADRUMO_TEST_PACKAGE_ROOT is required"),
    );
    let manifest_path = RelativePath::new("data/package-manifest.json").unwrap();
    let manifest_bytes = std::fs::read(manifest_path.under(&root)).unwrap();
    let layout: serde_json::Value = serde_json::from_slice(&manifest_bytes).unwrap();
    let executable = RelativePath::new(
        layout["layout"]["paths"]["executable"]
            .as_str()
            .expect("projected executable path"),
    )
    .unwrap();
    let manifest = PackageManifest::read(&root, &manifest_path).unwrap();
    let platform = manifest.layout.platform.clone();
    let abi = manifest.layout.abi;
    let inspection = manifest
        .inspect(&root, &manifest_path, &platform, abi)
        .unwrap();
    assert_eq!(inspection.readiness, Readiness::Ready);
    let expected = PythonExpectation::from_manifest(&inspection.manifest, &executable).unwrap();
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let mut environment = BTreeMap::new();
    for key in ["SystemRoot", "WINDIR", "COMSPEC"] {
        if let Some(value) = std::env::var_os(key) {
            environment.insert(key.into(), value);
        }
    }
    for key in [
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "TEMP",
        "TMP",
        "CADRUMO_LOCAL_STORAGE_ROOT",
        "CADRUMO_STORAGE_ROOT",
    ] {
        environment.insert(key.into(), directory.path().as_os_str().to_owned());
    }
    let configuration = ChildConfiguration::new(
        executable.under(&root),
        directory.path().to_owned(),
        environment,
    )
    .unwrap();
    let browser = BrowserQuery {
        root: Some(directory.path().join("empty-browser-cache")),
    };
    let report = python::probe(
        &configuration,
        &expected,
        Some(&browser),
        Duration::from_secs(60),
        &Cancellation::default(),
    )
    .await
    .unwrap();
    assert!(!browser.root.unwrap().exists());
    let expected_state: python::BrowserState = serde_json::from_value(serde_json::Value::String(
        std::env::var("CADRUMO_TEST_BROWSER_STATE")
            .expect("CADRUMO_TEST_BROWSER_STATE is required"),
    ))
    .unwrap();
    assert_eq!(report.browser.as_ref().unwrap().state, expected_state);
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
        "Relocated CPython {}: {} exact distribution versions; browser {:?}",
        report.version,
        report.distributions.len(),
        report.browser.unwrap().state
    );
}
