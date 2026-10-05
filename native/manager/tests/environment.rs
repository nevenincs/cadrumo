//! The manager consumes the canonical strict environment in isolated synthetic roots.

use cadrumo_manager::contract::{
    AUTHORITY, HOST_INHERITED_ENV, PINNED_ENV, PRODUCT_ENV_ALLOWLIST, ROOT_VARIABLE,
    TEMPORARY_DEFAULT, TEMPORARY_ENV,
};
use cadrumo_manager::supervision::environment::{ManagedLocations, runtime_environment};
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

struct Root(PathBuf);
impl Root {
    fn new() -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let path = std::env::temp_dir().join(format!(
            "cadrumo-manager-environment-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Root {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn strict_children_pin_canonical_paths_and_never_inherit_operator_settings() {
    let root = Root::new();
    let storage = root.0.join("storage");
    let package = root.0.join("package");
    let mut inherited: Vec<_> = PRODUCT_ENV_ALLOWLIST
        .iter()
        .chain(HOST_INHERITED_ENV)
        .map(|name| (OsString::from(name), OsString::from("untrusted")))
        .collect();
    inherited.extend([
        (OsString::from("PYTHONPATH"), OsString::from("untrusted")),
        (OsString::from("PATH"), OsString::from("os-path")),
        (OsString::from("TEMP"), OsString::from("untrusted")),
    ]);
    let environment = runtime_environment(&storage, Some(&package), inherited).unwrap();
    let value = |name: &str| {
        environment
            .iter()
            .find(|(key, _)| key == name)
            .map(|(_, value)| value)
    };
    assert_eq!(
        value(ROOT_VARIABLE),
        Some(&storage.clone().into_os_string())
    );
    assert_eq!(value("PATH"), Some(&OsString::from("os-path")));
    assert_eq!(value("PYTHONPATH"), None);
    assert_eq!(value(TEMPORARY_ENV), None);
    let temporary = TEMPORARY_DEFAULT
        .split('/')
        .fold(storage.clone(), |path, part| path.join(part));
    for name in PINNED_ENV.iter().filter(|name| **name != ROOT_VARIABLE) {
        assert_eq!(value(name), Some(&temporary.clone().into_os_string()));
    }
    for name in HOST_INHERITED_ENV {
        assert_eq!(value(name), Some(&package.join(AUTHORITY).into_os_string()));
    }
    for name in PRODUCT_ENV_ALLOWLIST
        .iter()
        .filter(|name| **name != ROOT_VARIABLE)
    {
        assert_eq!(value(name), None, "operator setting {name}");
    }
    assert!(storage.is_dir() && temporary.is_dir());
}

#[test]
fn fixture_children_do_not_receive_a_package_authority_pin() {
    let root = Root::new();
    let inherited = HOST_INHERITED_ENV
        .iter()
        .map(|name| (OsString::from(name), OsString::from("untrusted")));
    let environment = runtime_environment(&root.0, None, inherited).unwrap();
    assert!(
        !environment
            .iter()
            .any(|(name, _)| HOST_INHERITED_ENV.iter().any(|pin| name == pin))
    );
}

#[test]
fn invalid_paths_are_refused_before_creating_storage() {
    let root = Root::new();
    let storage = root.0.join("not-created");
    assert!(runtime_environment(&storage, Some(Path::new("relative")), []).is_err());
    assert!(!storage.exists());
    assert!(runtime_environment(Path::new("relative"), None, []).is_err());
}

#[test]
fn a_checkout_binary_is_not_a_managed_installation() {
    assert!(ManagedLocations::resolve(&std::env::current_exe().unwrap()).is_err());
}
