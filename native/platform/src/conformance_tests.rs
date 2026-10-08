use crate::storage::{Profile, child_environment};
use crate::*;
use std::ffi::OsString;
use std::time::{SystemTime, UNIX_EPOCH};

pub(crate) struct Scratch(pub PathBuf);

impl Scratch {
    pub(crate) fn new(label: &str) -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let temporary = env::temp_dir();
        #[cfg(unix)]
        let temporary = temporary.canonicalize().unwrap();
        let path = temporary.join(format!(
            "platform-conformance-{label}-{}-{nonce}",
            std::process::id()
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn value<'a>(environment: &'a [(OsString, OsString)], name: &str) -> &'a OsString {
    &environment.iter().find(|(key, _)| key == name).unwrap().1
}

#[test]
fn child_pins_normalize_absolute_root_and_relative_temporary_member() {
    let scratch = Scratch::new("normalized");
    let root = scratch.0.join("unused").join("..").join("datos con ñ");
    let environment = child_environment(
        Profile::Operator,
        vec![(
            OsString::from(TEMPORARY_ENV),
            OsString::from("unused-temp/../scratch"),
        )],
        &root,
    )
    .unwrap();
    let expected_root = scratch.0.join("datos con ñ");
    assert_eq!(
        value(&environment, ROOT_VARIABLE),
        expected_root.as_os_str()
    );
    for name in PINNED_ENV.iter().filter(|name| **name != ROOT_VARIABLE) {
        assert_eq!(
            value(&environment, name),
            expected_root.join("scratch").as_os_str()
        );
    }
    assert!(!scratch.0.join("unused").exists());
    assert!(!expected_root.join("unused-temp").exists());
}

#[test]
fn child_pins_expand_current_user_temporary_override_and_keep_inherited_pins() {
    let scratch = Scratch::new("home");
    let root = scratch.0.join("root");
    let rule = INSTALLED_DEFAULTS
        .iter()
        .find(|rule| rule.platform == env::consts::OS)
        .unwrap();
    let mut ambient = vec![
        (
            OsString::from(rule.home_variable),
            scratch.0.as_os_str().to_owned(),
        ),
        (OsString::from(TEMPORARY_ENV), OsString::from("~/scratch")),
    ];
    let inherited = scratch.0.join("authority con ñ");
    ambient.extend(
        HOST_INHERITED_ENV
            .iter()
            .map(|name| (OsString::from(name), inherited.as_os_str().to_owned())),
    );
    let operator = child_environment(Profile::Operator, ambient.clone(), &root).unwrap();
    let strict = child_environment(Profile::Strict, ambient, &root).unwrap();
    for environment in [&operator, &strict] {
        for name in HOST_INHERITED_ENV {
            assert_eq!(value(environment, name), inherited.as_os_str());
        }
    }
    for name in PINNED_ENV.iter().filter(|name| **name != ROOT_VARIABLE) {
        assert_eq!(
            value(&operator, name),
            scratch.0.join("scratch").as_os_str()
        );
        assert_eq!(
            value(&strict, name),
            root.join(storage::relative_components(TEMPORARY_DEFAULT))
                .as_os_str()
        );
    }
}

fn empty_buffer() -> Buffer {
    Buffer {
        data: ptr::null_mut(),
        len: 0,
    }
}

#[test]
fn abi_mismatch_and_invalid_arguments_return_declared_statuses() {
    assert_eq!(cadrumo_platform_abi(), ABI);
    let mut context = ptr::dangling_mut::<Context>();
    let mut error = empty_buffer();
    unsafe {
        assert_eq!(
            cadrumo_platform_create(ABI + 1, &mut context, &mut error),
            1
        );
        assert!(context.is_null());
        assert!(!error.data.is_null() && error.len > 0);
        let message = std::slice::from_raw_parts(error.data, error.len as usize);
        assert_eq!(message, b"Incompatible platform ABI");
        cadrumo_platform_release(&mut error);
        cadrumo_platform_release(&mut error);
        assert!(error.data.is_null() && error.len == 0);
        assert_eq!(cadrumo_platform_create(ABI, ptr::null_mut(), &mut error), 2);
        assert_eq!(
            cadrumo_platform_create(ABI, &mut context, ptr::null_mut()),
            2
        );
        assert_eq!(cadrumo_platform_path(ptr::null_mut(), 0, &mut error), 2);
        assert_eq!(cadrumo_platform_prepare(ptr::null_mut(), &mut error), 2);
        cadrumo_platform_release(ptr::null_mut());
        cadrumo_platform_destroy(ptr::null_mut());
    }
}

#[test]
fn abi_paths_preserve_utf8_bytes_and_provider_owned_buffer_lifetime() {
    let expected = "datos con ñ/根";
    let context = Box::into_raw(Box::new(Context {
        paths: vec![PathBuf::from(expected)],
    }));
    let mut output = empty_buffer();
    unsafe {
        assert_eq!(cadrumo_platform_path(context, 0, &mut output), 0);
        let bytes = std::slice::from_raw_parts(output.data, output.len as usize);
        assert_eq!(bytes, expected.as_bytes());
        assert_eq!(output.len, expected.len() as u64);
        cadrumo_platform_destroy(context);
        assert_eq!(
            std::slice::from_raw_parts(output.data, output.len as usize),
            expected.as_bytes()
        );
        cadrumo_platform_release(&mut output);
        assert!(output.data.is_null() && output.len == 0);
    }
}

#[test]
fn abi_bad_path_key_returns_invalid_argument_with_empty_output() {
    let mut context = Context { paths: vec![] };
    let mut output = empty_buffer();
    unsafe {
        assert_eq!(
            cadrumo_platform_path(&mut context, u32::MAX, &mut output),
            2
        );
    }
    assert!(output.data.is_null() && output.len == 0);
}

pub(crate) fn invalid_unicode() -> OsString {
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStringExt;
        OsString::from_wide(INVALID_NATIVE_PATH_UTF16)
    }
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStringExt;
        OsString::from_vec(INVALID_NATIVE_PATH_BYTES.to_vec())
    }
}

#[test]
fn invalid_temporary_override_refuses_without_effects_or_lossy_replacement() {
    let scratch = Scratch::new("invalid-temp");
    let root = scratch.0.join("root");
    let invalid = vec![(OsString::from(TEMPORARY_ENV), invalid_unicode())];
    let error = child_environment(Profile::Operator, invalid.clone(), &root).unwrap_err();
    assert_eq!(error.kind(), std::io::ErrorKind::InvalidInput);
    assert!(!root.exists());
    let strict = child_environment(Profile::Strict, invalid, &root).unwrap();
    assert!(!strict.iter().any(|(name, _)| name == TEMPORARY_ENV));
}

#[test]
fn native_bootstrap_does_not_ignore_an_invalid_selected_root_override() {
    let lookup = |name: &str| (name == ROOT_VARIABLE).then(invalid_unicode);
    for mode in [storage::Mode::Installed, storage::Mode::Development] {
        let refusal = storage::resolve_root(mode, &lookup, None, None, BUILD_CHANNEL).unwrap_err();
        assert_eq!(refusal.code, ROOT_REFUSAL_INVALID_PATH_INPUT);
    }

    let scratch = Scratch::new("effective-root");
    let root = scratch.0.join("selected");
    let selected = |name: &str| {
        if name == ROOT_VARIABLE {
            Some(root.as_os_str().to_owned())
        } else if name == DEVELOPMENT_ROOT_VARIABLE {
            Some(invalid_unicode())
        } else {
            None
        }
    };
    assert!(
        storage::resolve_root(
            storage::Mode::Development,
            &selected,
            None,
            None,
            BUILD_CHANNEL
        )
        .is_ok()
    );
    let lower = |name: &str| (name == DEVELOPMENT_ROOT_VARIABLE).then(invalid_unicode);
    if let Err(refused) = storage::resolve_root(
        storage::Mode::Installed,
        &lower,
        None,
        Some(&scratch.0),
        BUILD_CHANNEL,
    ) {
        assert_eq!(refused.code, ROOT_REFUSAL_INSTALLED_BASE_UNAVAILABLE);
    }
    assert_eq!(
        storage::resolve_root(
            storage::Mode::Development,
            &lower,
            None,
            None,
            BUILD_CHANNEL
        )
        .unwrap_err()
        .code,
        ROOT_REFUSAL_INVALID_PATH_INPUT
    );
}

#[test]
fn generated_filesystem_vectors_preserve_original_link_evidence_and_have_no_effects() {
    for vector in STORAGE_PATH_VECTORS {
        let scratch = Scratch::new(vector.name);
        for directory in vector.directories {
            fs::create_dir(scratch.0.join(directory)).unwrap();
        }
        for file in vector.files {
            fs::write(scratch.0.join(file), b"fixture").unwrap();
        }
        for (name, target) in vector.links {
            #[cfg(unix)]
            std::os::unix::fs::symlink(scratch.0.join(target), scratch.0.join(name)).unwrap();
            #[cfg(windows)]
            {
                let result = std::process::Command::new("cmd.exe")
                    .args(["/c", "mklink", "/J"])
                    .arg(scratch.0.join(name))
                    .arg(scratch.0.join(target))
                    .output()
                    .unwrap();
                assert!(result.status.success(), "{}: {:?}", vector.name, result);
            }
        }
        let original = scratch
            .0
            .join(vector.components.iter().collect::<PathBuf>());
        let lookup = |name: &str| (name == ROOT_VARIABLE).then(|| original.as_os_str().to_owned());
        let actual =
            storage::resolve_root(storage::Mode::Installed, &lookup, None, None, BUILD_CHANNEL);
        match (actual, vector.expected_components, vector.refusal) {
            (Ok(resolved), Some(parts), None) => assert_eq!(
                resolved.root,
                scratch.0.join(parts.iter().collect::<PathBuf>()),
                "{}",
                vector.name
            ),
            (Err(refused), None, Some(code)) => assert_eq!(refused.code, code, "{}", vector.name),
            outcome => panic!("{}: {outcome:?}", vector.name),
        }
        assert!(!scratch.0.join("selected").exists());
        assert!(!scratch.0.join("missing").exists());
    }
}

#[test]
fn inherited_path_pins_refuse_relative_and_invalid_values_before_creation() {
    for profile in [Profile::Operator, Profile::Strict] {
        for field in HOST_INHERITED_FIELDS
            .iter()
            .filter(|field| field.kind == INHERITED_KIND_DIRECTORY_PATH)
        {
            for value in [OsString::from("relative"), invalid_unicode()] {
                let scratch = Scratch::new("inherited-refusal");
                let root = scratch.0.join("root");
                let error = child_environment(profile, vec![(field.name.into(), value)], &root)
                    .unwrap_err();
                assert_eq!(error.kind(), std::io::ErrorKind::InvalidInput);
                assert!(!root.exists());
            }
        }
    }
}

#[test]
fn child_and_public_root_share_normalized_spelling_without_discarded_creation() {
    let scratch = Scratch::new("resolved-pin");
    let raw = scratch.0.join("unused/../selected");
    let lookup = |name: &str| (name == ROOT_VARIABLE).then(|| raw.as_os_str().to_owned());
    let resolved =
        storage::resolve_root(storage::Mode::Installed, &lookup, None, None, BUILD_CHANNEL)
            .unwrap();
    assert_eq!(resolved.root, scratch.0.join("selected"));
    assert!(!resolved.root.exists() && !scratch.0.join("unused").exists());
    let environment = child_environment(Profile::Strict, Vec::new(), &resolved.root).unwrap();
    assert_eq!(
        value(&environment, ROOT_VARIABLE),
        resolved.root.as_os_str()
    );
    assert!(!scratch.0.join("unused").exists());
}

#[test]
fn mode_detection_refuses_relative_executable_input() {
    assert!(storage::detect_mode(Path::new(EXECUTABLE)).is_err());
    assert!(storage::detect_mode(&Path::new(NATIVE).join(ENTRYPOINT_FILES[0])).is_err());
}

#[test]
fn absolute_temporary_override_normalizes_without_changing_the_root_pin() {
    let scratch = Scratch::new("absolute-member");
    let root = scratch.0.join("root");
    let temporary = scratch.0.join("unused-member/../temporary con ñ");
    let environment = child_environment(
        Profile::Operator,
        vec![(
            OsString::from(TEMPORARY_ENV),
            temporary.as_os_str().to_owned(),
        )],
        &root,
    )
    .unwrap();
    assert_eq!(value(&environment, ROOT_VARIABLE), root.as_os_str());
    for name in PINNED_ENV.iter().filter(|name| **name != ROOT_VARIABLE) {
        assert_eq!(
            value(&environment, name),
            scratch.0.join("temporary con ñ").as_os_str()
        );
    }
    assert!(!scratch.0.join("unused-member").exists());
}

#[test]
fn abi_prepare_filesystem_refusal_returns_a_provider_error_without_panicking() {
    let scratch = Scratch::new("prepare-refusal");
    let file = scratch.0.join("file");
    fs::write(&file, b"preserved").unwrap();
    let mut context = Context {
        paths: vec![file.clone(); 9],
    };
    let mut error = empty_buffer();
    unsafe {
        assert_eq!(cadrumo_platform_prepare(&mut context, &mut error), 3);
        assert!(!error.data.is_null() && error.len > 0);
        let bytes = std::slice::from_raw_parts(error.data, error.len as usize);
        assert!(std::str::from_utf8(bytes).is_ok());
        cadrumo_platform_release(&mut error);
        assert!(error.data.is_null() && error.len == 0);
    }
    assert_eq!(fs::read(file).unwrap(), b"preserved");
}

#[cfg(windows)]
#[test]
fn windows_environment_names_follow_the_declarations_unicode_uppercase_rule() {
    let scratch = Scratch::new("unicode-case");
    let root = scratch.0.join("root");
    let temporary_name = TEMPORARY_ENV.to_lowercase().replace('i', "ı");
    assert_eq!(temporary_name.to_uppercase(), TEMPORARY_ENV);
    let inherited_name = HOST_INHERITED_ENV[0].to_lowercase().replace('i', "ı");
    assert_eq!(inherited_name.to_uppercase(), HOST_INHERITED_ENV[0]);
    let authority = scratch.0.join("authority");
    let ambient = vec![
        (
            OsString::from(temporary_name),
            OsString::from("worker-temp"),
        ),
        (
            OsString::from(inherited_name),
            authority.as_os_str().to_owned(),
        ),
    ];
    assert!(storage::authority_override_present(ambient.clone()));
    let environment = child_environment(Profile::Operator, ambient, &root).unwrap();
    assert_eq!(value(&environment, TEMPORARY_ENV), "worker-temp");
    assert_eq!(
        value(&environment, HOST_INHERITED_ENV[0]),
        authority.as_os_str()
    );
    for name in PINNED_ENV.iter().filter(|name| **name != ROOT_VARIABLE) {
        assert_eq!(
            value(&environment, name),
            root.join("worker-temp").as_os_str()
        );
    }
}

#[test]
fn abi_unrepresentable_path_returns_failure_and_an_empty_buffer() {
    let mut context = Context {
        paths: vec![PathBuf::from(invalid_unicode())],
    };
    let mut output = empty_buffer();
    unsafe {
        assert_eq!(cadrumo_platform_path(&mut context, 0, &mut output), 3);
        assert!(output.data.is_null() && output.len == 0);
        cadrumo_platform_release(&mut output);
    }
}
