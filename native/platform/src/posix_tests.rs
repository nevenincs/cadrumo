use crate::conformance_tests::Scratch;
use crate::storage::{Mode, Profile, child_environment, resolve_root, resolve_root_vector};
use crate::*;
use std::ffi::OsString;
use std::os::unix::fs::{PermissionsExt, symlink};
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn generated_target_root_vectors() {
    let mut count = 0;
    for vector in STORAGE_ROOT_VECTORS
        .iter()
        .filter(|v| v.platform == env::consts::OS)
    {
        count += 1;
        let lookup = |name: &str| {
            if vector.invalid_environment.contains(&name) {
                return Some(crate::conformance_tests::invalid_unicode());
            }
            vector
                .environment
                .iter()
                .find(|(key, _)| *key == name)
                .map(|(_, value)| OsString::from(*value))
        };
        let mode = match vector.mode {
            "installed" => Mode::Installed,
            "development" => Mode::Development,
            _ => panic!("Unknown mode"),
        };
        let checkout = if vector.invalid_checkout {
            Some(PathBuf::from(crate::conformance_tests::invalid_unicode()))
        } else {
            vector.checkout.map(PathBuf::from)
        };
        let actual = resolve_root_vector(mode, &lookup, checkout.as_deref(), None, vector.channel);
        match (actual, vector.expected_root, vector.refusal) {
            (Ok(root), Some(expected), None) => {
                assert_eq!(root.root, Path::new(expected), "{}", vector.name)
            }
            (Err(error), None, Some(expected)) => {
                assert_eq!(error.code, expected, "{}", vector.name)
            }
            other => panic!("{}: {other:?}", vector.name),
        }
    }
    assert!(count > 0, "Target conformance vectors are required");
}

#[test]
fn environment_case_and_loader_controls_follow_the_posix_declaration() {
    for name in [
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "DYLD_LIBRARY_PATH",
        "PYTHONPATH",
    ] {
        assert!(storage::cleared(name, Profile::Operator, &[]), "{name}");
        assert!(!storage::cleared(
            &name.to_lowercase(),
            Profile::Strict,
            &[]
        ));
    }
}

#[test]
fn child_pins_refuse_relative_roots_and_symlinks_and_create_private_directories() {
    assert!(child_environment(Profile::Strict, Vec::new(), Path::new("relative")).is_err());
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let scratch = env::temp_dir()
        .canonicalize()
        .unwrap()
        .join(format!("platform-{}-{nonce}", std::process::id()));
    let root = scratch.join("datos con ñ");
    let received = vec![
        (OsString::from("PYTHONPATH"), OsString::from("hostile")),
        (
            OsString::from(TEMPORARY_ENV),
            OsString::from("operator-temp"),
        ),
    ];
    let strict = child_environment(Profile::Strict, received.clone(), &root).unwrap();
    assert_eq!(
        fs::metadata(&root).unwrap().permissions().mode() & 0o777,
        POSIX_DIRECTORY_MODE
    );
    assert!(
        !strict
            .iter()
            .any(|(key, _)| key == "PYTHONPATH" || key == TEMPORARY_ENV)
    );
    assert!(
        strict
            .iter()
            .any(|(key, value)| key == ROOT_VARIABLE && value == root.as_os_str())
    );
    let operator = child_environment(Profile::Operator, received, &root).unwrap();
    assert!(operator.iter().any(|(key, _)| key == TEMPORARY_ENV));
    symlink(&root, scratch.join("link")).unwrap();
    assert!(child_environment(Profile::Strict, Vec::new(), &scratch.join("link/child")).is_err());
    fs::remove_dir_all(scratch).unwrap();
}

#[test]
fn package_root_entrypoint_mapping_and_case_match_the_generated_projection() {
    let scratch = Scratch::new("package");
    let package = &scratch.0;
    assert_eq!(
        storage::package_root(&package.join(EXECUTABLE)).unwrap(),
        *package
    );
    for file in ENTRYPOINT_FILES {
        let directory = package.join(NATIVE);
        assert_eq!(
            storage::package_root(&directory.join(file)).unwrap(),
            *package
        );
        assert!(storage::package_root(&package.join(file)).is_err());
        let uppercase_directory = package.join(NATIVE.to_uppercase());
        if uppercase_directory != directory {
            assert!(storage::package_root(&uppercase_directory.join(file)).is_err());
        }
        let uppercase_file = file.to_uppercase();
        if uppercase_file != *file {
            assert_eq!(
                storage::package_root(&directory.join(uppercase_file)).unwrap(),
                directory
            );
        }
    }
}

#[test]
fn installed_and_checkout_evidence_come_from_absolute_executable_ancestors() {
    let scratch = Scratch::new("mode");
    let package = scratch.0.join("package");
    let manifest = package.join(storage::relative_components(MODE_PACKAGE_MANIFEST));
    fs::create_dir_all(manifest.parent().unwrap()).unwrap();
    fs::write(manifest, b"{}").unwrap();
    let installed = storage::detect_mode(&package.join(EXECUTABLE)).unwrap();
    assert_eq!(installed.mode, Mode::Installed);
    assert_eq!(installed.package, package);
    let installed_entrypoint =
        storage::detect_mode(&package.join(NATIVE).join(ENTRYPOINT_FILES[0])).unwrap();
    assert_eq!(installed_entrypoint.mode, Mode::Installed);
    assert_eq!(installed_entrypoint.package, package);
    fs::write(scratch.0.join(MODE_CHECKOUT_MARKER), b"[project]\n").unwrap();
    let checkout = storage::detect_mode(&scratch.0.join("build").join(EXECUTABLE)).unwrap();
    assert_eq!(checkout.mode, Mode::Development);
    assert_eq!(checkout.checkout.as_deref(), Some(scratch.0.as_path()));
}

#[test]
fn lower_case_posix_names_do_not_override_declared_paths_or_authority() {
    let scratch = Scratch::new("case");
    let root = scratch.0.join("root");
    let lower_temporary = TEMPORARY_ENV.to_lowercase();
    let lower_pin = HOST_INHERITED_ENV[0].to_lowercase();
    let ambient = vec![
        (OsString::from(&lower_temporary), OsString::from("other")),
        (
            OsString::from(&lower_pin),
            OsString::from("lower-authority"),
        ),
        (OsString::from("ld_preload"), OsString::from("inert")),
        (OsString::from("LD_PRELOAD"), OsString::from("hostile")),
    ];
    assert!(!storage::authority_override_present(ambient.clone()));
    let environment = child_environment(Profile::Operator, ambient, &root).unwrap();
    assert!(
        environment
            .iter()
            .any(|(key, _)| key == lower_temporary.as_str())
    );
    assert!(environment.iter().any(|(key, _)| key == lower_pin.as_str()));
    assert!(environment.iter().any(|(key, _)| key == "ld_preload"));
    assert!(!environment.iter().any(|(key, _)| key == "LD_PRELOAD"));
    for name in PINNED_ENV.iter().filter(|name| **name != ROOT_VARIABLE) {
        assert!(environment.iter().any(|(key, value)| {
            key == *name
                && value
                    == root
                        .join(storage::relative_components(TEMPORARY_DEFAULT))
                        .as_os_str()
        }));
    }
}

#[test]
fn normalization_does_not_hide_symlinks_before_parent_components() {
    let scratch = Scratch::new("links");
    let destination = scratch.0.join("destination");
    fs::create_dir(&destination).unwrap();
    symlink(&destination, scratch.0.join("link")).unwrap();
    for path in [
        scratch.0.join("link/../state"),
        scratch.0.join("link/child"),
    ] {
        assert!(child_environment(Profile::Strict, Vec::new(), &path).is_err());
    }
    symlink(scratch.0.join("absent"), scratch.0.join("dangling")).unwrap();
    assert!(
        child_environment(
            Profile::Strict,
            Vec::new(),
            &scratch.0.join("dangling/state")
        )
        .is_err()
    );
    assert!(!scratch.0.join("state").exists());
    let root = scratch.0.join("root");
    fs::create_dir(&root).unwrap();
    symlink(&destination, root.join("link")).unwrap();
    assert!(
        child_environment(
            Profile::Operator,
            vec![(
                OsString::from(TEMPORARY_ENV),
                OsString::from("link/../temporary"),
            )],
            &root,
        )
        .is_err()
    );
    assert!(!root.join("temporary").exists());
}

#[test]
fn nested_new_storage_and_temporary_directories_are_private() {
    let scratch = Scratch::new("permissions");
    let root = scratch.0.join("new-parent/state");
    child_environment(
        Profile::Operator,
        vec![(
            OsString::from(TEMPORARY_ENV),
            OsString::from("nested/scratch"),
        )],
        &root,
    )
    .unwrap();
    for path in [
        scratch.0.join("new-parent"),
        root.clone(),
        root.join("nested"),
        root.join("nested/scratch"),
    ] {
        assert_eq!(
            fs::metadata(path).unwrap().permissions().mode() & 0o777,
            POSIX_DIRECTORY_MODE
        );
    }
}

#[test]
fn non_unicode_ambient_values_are_not_replaced() {
    use std::os::unix::ffi::OsStringExt;
    let scratch = Scratch::new("os-bytes");
    let invalid = OsString::from_vec(vec![b'd', 0xFF]);
    let root = scratch.0.join("root");
    let environment = child_environment(
        Profile::Strict,
        vec![(OsString::from("AMBIENT_VALUE"), invalid.clone())],
        &root,
    )
    .unwrap();
    assert!(
        environment
            .iter()
            .any(|(key, value)| key == "AMBIENT_VALUE" && value == &invalid)
    );
}

#[test]
fn native_path_pins_refuse_non_unicode_bytes_without_replacement() {
    let scratch = Scratch::new("native-path-bytes");
    let root = scratch.0.join(crate::conformance_tests::invalid_unicode());
    let error = child_environment(Profile::Strict, Vec::new(), &root).unwrap_err();
    assert_eq!(error.kind(), std::io::ErrorKind::InvalidInput);
    assert!(error.to_string().contains(ROOT_REFUSAL_INVALID_PATH_INPUT));
    assert!(!root.exists());
    assert!(!scratch.0.join("d\u{FFFD}").exists());
}
