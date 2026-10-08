#![cfg(feature = "platform")]

use cadrumo_application::child::ChildConfiguration;
use cadrumo_platform::{ROOT_VARIABLE, storage::Profile};
use std::{collections::BTreeMap, ffi::OsString, fs, path::PathBuf};

#[test]
fn platform_child_pins_root_without_mutating_host_environment() {
    if let Some(expected) = std::env::var_os("B3_PLATFORM_CHILD_ROOT") {
        assert_eq!(
            PathBuf::from(std::env::var_os(ROOT_VARIABLE).unwrap()),
            PathBuf::from(expected)
        );
        return;
    }
    fs::create_dir_all(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let temporary = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let before: BTreeMap<_, _> = std::env::vars_os().collect();
    let root = temporary.path().join("owned root");
    // Exercise the forward-slash paths supplied by CMake on Windows too.
    #[cfg(windows)]
    let root = PathBuf::from(root.to_str().unwrap().replace('\\', "/"));
    let configuration = ChildConfiguration::from_platform(
        std::env::current_exe().unwrap(),
        temporary.path().into(),
        &root,
        Profile::Strict,
        before.clone(),
    )
    .unwrap();
    assert_eq!(
        PathBuf::from(&configuration.environment()[&OsString::from(ROOT_VARIABLE)]),
        root
    );
    assert_eq!(std::env::vars_os().collect::<BTreeMap<_, _>>(), before);
    assert!(root.is_dir());
    let output = configuration
        .command()
        .args([
            "--exact",
            "platform_child_pins_root_without_mutating_host_environment",
        ])
        .env("B3_PLATFORM_CHILD_ROOT", &root)
        .output()
        .unwrap();
    assert!(output.status.success(), "platform-configured child failed");
    assert_eq!(std::env::vars_os().collect::<BTreeMap<_, _>>(), before);
    let expected: BTreeMap<_, _> =
        cadrumo_platform::storage::child_environment(Profile::Strict, before, &root)
            .unwrap()
            .into_iter()
            .collect();
    assert_eq!(configuration.environment(), &expected);
}

#[test]
fn invalid_command_does_not_prepare_storage() {
    fs::create_dir_all(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let temporary = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let root = temporary.path().join("not-created");
    assert!(
        ChildConfiguration::from_platform(
            "relative-executable".into(),
            temporary.path().into(),
            &root,
            Profile::Strict,
            BTreeMap::new(),
        )
        .is_err()
    );
    assert!(!root.exists());
    assert!(
        ChildConfiguration::from_platform(
            std::env::current_exe().unwrap(),
            temporary.path().into(),
            &root.join("../escape"),
            Profile::Strict,
            BTreeMap::new(),
        )
        .is_err()
    );
    assert!(!root.exists());
}
