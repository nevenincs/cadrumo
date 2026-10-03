//! Opt-in acceptance: prerequisites are mandatory when the feature is selected.
#![cfg(feature = "live-python-tests")]
use cadrumo_application::{
    child::ChildConfiguration,
    component::Cancellation,
    error::Error,
    python::{self, BrowserQuery, BrowserState, PythonExpectation},
    value::Sha256Digest,
};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, path::PathBuf, time::Duration};

#[tokio::test]
async fn live_interpreter_and_canonical_browser_probe() {
    let executable = PathBuf::from(
        std::env::var_os("CADRUMO_TEST_PYTHON").expect("CADRUMO_TEST_PYTHON is required"),
    );
    let version = std::env::var("CADRUMO_TEST_PYTHON_VERSION")
        .expect("CADRUMO_TEST_PYTHON_VERSION is required");
    let expected_browser = std::env::var("CADRUMO_TEST_BROWSER_STATE")
        .expect("CADRUMO_TEST_BROWSER_STATE is required");
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let mut environment = BTreeMap::new();
    // Test fixture projection only. The production platform owner supplies its environment.
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
    ] {
        environment.insert(key.into(), directory.path().as_os_str().to_owned());
    }
    let configuration =
        ChildConfiguration::new(executable.clone(), directory.path().to_owned(), environment)
            .unwrap();
    let mut expected = PythonExpectation {
        executable_sha256: Sha256Digest::new(format!(
            "{:x}",
            Sha256::digest(std::fs::read(&executable).unwrap())
        ))
        .unwrap(),
        version,
        distributions: BTreeMap::new(),
    };
    let browser = BrowserQuery {
        root: Some(directory.path().join("empty-browser-cache")),
    };
    let cancellation = Cancellation::default();
    let report = python::probe(
        &configuration,
        &expected,
        Some(&browser),
        Duration::from_secs(60),
        &cancellation,
    )
    .await
    .unwrap();
    let browser_report = report.browser.unwrap();
    let state = match expected_browser.as_str() {
        "missing_dependency" => BrowserState::MissingDependency,
        "missing_builds" => BrowserState::MissingBuilds,
        "unreadable_manifest" => BrowserState::UnreadableManifest,
        _ => panic!("unexpected browser expectation"),
    };
    assert_eq!(browser_report.state, state);
    assert!(
        !browser.root.as_ref().unwrap().exists(),
        "inspection created browser data"
    );
    expected.version = "0.0.0".into();
    assert!(matches!(
        python::probe(
            &configuration,
            &expected,
            None,
            Duration::from_secs(30),
            &cancellation
        )
        .await,
        Err(Error::Incompatible(_))
    ));
    expected.version = report.version;
    expected
        .distributions
        .insert("cadrumo-nonexistent-test-distribution".into(), "1".into());
    assert!(matches!(
        python::probe(
            &configuration,
            &expected,
            None,
            Duration::from_secs(30),
            &cancellation
        )
        .await,
        Err(Error::Incompatible(_))
    ));
    println!(
        "CPython {}: {:?}, {} canonical browser builds",
        expected.version,
        browser_report.state,
        browser_report.builds.len()
    );
}
