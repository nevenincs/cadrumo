use cadrumo_application::{
    error::Error,
    package::{
        Readiness,
        release::{ReleaseExpectation, inspect_release},
    },
    value::{RelativePath, Sha256Digest},
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{fs, path::Path};

fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn fixture(root: &Path, mutate: impl FnOnce(&mut Value)) -> (RelativePath, ReleaseExpectation) {
    let build = json!({"version": "1.2.3", "python": "3.13.11", "layout_abi": 1,
        "target": "canonical-target", "channel": "preview", "build_number": 42});
    let metadata = serde_json::to_vec(&build).unwrap();
    fs::write(root.join("build.json"), &metadata).unwrap();
    fs::write(root.join("python.zip"), b"stdlib").unwrap();
    let mut manifest = json!({
        "layout": {"abi": 1, "platform": "physical-target", "files": {"build_metadata": "build.json"}},
        "build": build, "python": "3.13.11", "distributions": {"product": "1.2.3", "companion": "1.2.3"},
        "files": {"build.json": digest(&metadata), "python.zip": digest(b"stdlib")},
        "user_docs": {"directory": "docs/user", "bundled": false}
    });
    mutate(&mut manifest);
    let bytes = serde_json::to_vec(&manifest).unwrap();
    fs::write(root.join("manifest.json"), &bytes).unwrap();
    (
        RelativePath::new("manifest.json").unwrap(),
        ReleaseExpectation {
            manifest_sha256: Sha256Digest::new(digest(&bytes)).unwrap(),
            platform: "physical-target".into(),
            abi: 1,
            target: "canonical-target".into(),
            python: "3.13.11".into(),
            version: "1.2.3".into(),
            channel: "preview".into(),
            cohort: vec!["product".into(), "companion".into()],
        },
    )
}

fn directory() -> tempfile::TempDir {
    fs::create_dir_all(env!("CARGO_TARGET_TMPDIR")).unwrap();
    tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap()
}

#[test]
fn release_admission_checks_external_identity_and_existing_inventory() {
    let temp = directory();
    let (path, expected) = fixture(temp.path(), |_| {});
    assert_eq!(
        inspect_release(temp.path(), &path, &expected)
            .unwrap()
            .readiness,
        Readiness::Ready
    );
    fs::write(temp.path().join("python.zip"), b"modified").unwrap();
    assert!(matches!(
        inspect_release(temp.path(), &path, &expected)
            .unwrap()
            .readiness,
        Readiness::Incompatible(_)
    ));
    fs::remove_file(temp.path().join("python.zip")).unwrap();
    assert!(matches!(
        inspect_release(temp.path(), &path, &expected)
            .unwrap()
            .readiness,
        Readiness::Missing(_)
    ));
}

#[test]
fn release_admission_rejects_inconsistent_identity_and_cohort() {
    for pointer in [
        "/build/version",
        "/build/python",
        "/build/target",
        "/build/channel",
        "/python",
        "/distributions/companion",
    ] {
        let temp = directory();
        let (path, expected) = fixture(temp.path(), |value| {
            *value.pointer_mut(pointer).unwrap() = json!("wrong")
        });
        assert!(
            matches!(
                inspect_release(temp.path(), &path, &expected)
                    .unwrap()
                    .readiness,
                Readiness::Incompatible(_)
            ),
            "{pointer}"
        );
    }
    let temp = directory();
    let (path, expected) = fixture(temp.path(), |value| {
        value["distributions"]
            .as_object_mut()
            .unwrap()
            .remove("companion");
    });
    assert!(matches!(
        inspect_release(temp.path(), &path, &expected)
            .unwrap()
            .readiness,
        Readiness::Missing(_)
    ));
    let (path, expected) = fixture(temp.path(), |value| value["build"]["layout_abi"] = json!(2));
    assert!(matches!(
        inspect_release(temp.path(), &path, &expected)
            .unwrap()
            .readiness,
        Readiness::Incompatible(_)
    ));
}

#[test]
fn metadata_must_agree_even_when_each_inventory_digest_is_correct() {
    let temp = directory();
    let (path, expected) = fixture(temp.path(), |value| {
        value["build"]["build_number"] = json!(43)
    });
    assert!(matches!(
        inspect_release(temp.path(), &path, &expected)
            .unwrap()
            .readiness,
        Readiness::Incompatible(_)
    ));
}

#[test]
fn manifest_digest_and_required_expectations_cannot_be_bypassed() {
    let temp = directory();
    let (path, mut expected) = fixture(temp.path(), |_| {});
    fs::write(path.under(temp.path()), b"{}").unwrap();
    assert!(matches!(
        inspect_release(temp.path(), &path, &expected),
        Err(Error::Integrity(_))
    ));
    expected.cohort.clear();
    assert!(matches!(
        inspect_release(temp.path(), &path, &expected),
        Err(Error::Invalid(_))
    ));
}
