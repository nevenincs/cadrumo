//! Opt-in acceptance: prerequisites are mandatory when the feature is selected.
#![cfg(feature = "live-python-tests")]
use cadrumo_application::{
    child::ChildConfiguration,
    component::Cancellation,
    error::Error,
    python::{self, PythonExpectation},
    value::Sha256Digest,
};
use std::{collections::BTreeMap, path::PathBuf, time::Duration};

#[tokio::test]
async fn live_interpreter_probe() {
    let executable = PathBuf::from(
        std::env::var_os("CADRUMO_TEST_PYTHON").expect("CADRUMO_TEST_PYTHON is required"),
    );
    let version = std::env::var("CADRUMO_TEST_PYTHON_VERSION")
        .expect("CADRUMO_TEST_PYTHON_VERSION is required");
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
        executable_sha256: Sha256Digest::of(std::fs::read(&executable).unwrap()),
        version,
        distributions: BTreeMap::new(),
    };
    let cancellation = Cancellation::default();
    let report = python::probe(
        &configuration,
        &expected,
        Duration::from_secs(60),
        &cancellation,
    )
    .await
    .unwrap();
    expected.version = "0.0.0".into();
    assert!(matches!(
        python::probe(
            &configuration,
            &expected,
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
            Duration::from_secs(30),
            &cancellation
        )
        .await,
        Err(Error::Incompatible(_))
    ));
    println!("CPython {}", expected.version);
}
