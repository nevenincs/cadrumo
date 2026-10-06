//! The manager consumes the canonical strict environment in isolated synthetic roots.

use cadrumo_manager::contract::{
    AUTHORITY, HOST_INHERITED_ENV, PINNED_ENV, PRODUCT_ENV_ALLOWLIST, ROOT_VARIABLE,
    TEMPORARY_DEFAULT, TEMPORARY_ENV,
};
use cadrumo_manager::supervision::environment::{ManagedLocations, runtime_environment};
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

#[cfg(unix)]
use cadrumo_manager::{
    contract::{EXECUTABLE, INSTALLED_DEFAULTS, INSTALLED_ROOT_PRECEDENCE, MODE_PACKAGE_MANIFEST},
    supervision::{boot_record::boot_record_path, launch::LaunchTarget},
};

struct Root(PathBuf);
impl Root {
    fn new() -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let temporary = std::env::temp_dir();
        // Fixture roots use the physical existing temp base (macOS can expose /var).
        #[cfg(unix)]
        let temporary = temporary.canonicalize().unwrap();
        let path = temporary.join(format!(
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

#[cfg(windows)]
#[test]
fn unicode_aliases_of_inherited_pins_are_removed_before_package_authority_is_added() {
    let root = Root::new();
    let storage = root.0.join("storage");
    let package = root.0.join("package");
    for value in ["untrusted", ""] {
        let inherited = HOST_INHERITED_ENV
            .iter()
            .map(|name| {
                let alias = name.to_lowercase().replace('i', "ı");
                assert_ne!(alias.to_ascii_uppercase(), *name);
                assert_eq!(alias.to_uppercase(), *name);
                (OsString::from(alias), OsString::from(value))
            })
            .collect::<Vec<_>>();
        for selected in [None, Some(package.as_path())] {
            let environment = runtime_environment(&storage, selected, inherited.clone()).unwrap();
            for pin in HOST_INHERITED_ENV {
                let entries = environment
                    .iter()
                    .filter(|(name, _)| {
                        name.to_str()
                            .is_some_and(|name| name.to_uppercase() == *pin)
                    })
                    .collect::<Vec<_>>();
                if selected.is_some() {
                    assert_eq!(entries.len(), 1, "duplicate inherited pin {pin}");
                    assert_eq!(entries[0].0, OsString::from(pin));
                    assert_eq!(entries[0].1, package.join(AUTHORITY).into_os_string());
                } else {
                    assert!(entries.is_empty(), "ambient inherited pin {pin}");
                }
            }
        }
    }
}

#[cfg(unix)]
#[test]
fn normalized_default_root_is_shared_by_manager_arguments_and_child_pins() {
    const FIXTURE: &str = "B2_MANAGER_NORMALIZATION_FIXTURE";
    if let Some(fixture) = std::env::var_os(FIXTURE) {
        let fixture = PathBuf::from(fixture);
        let package = fixture.join("package");
        let discarded = fixture.join("unused");
        let selected = fixture.join("selected");
        assert!(!discarded.exists() && !selected.exists());
        let locations = ManagedLocations::resolve(&package.join(EXECUTABLE)).unwrap();
        assert_eq!(locations.package_root(), package);
        assert!(locations.storage_root().starts_with(&selected));
        assert!(!discarded.exists() && !selected.exists());
        let target = LaunchTarget::installed(&locations, "a".repeat(64), "1.0".into()).unwrap();
        assert_eq!(target.storage_root(), locations.storage_root());
        assert_eq!(target.arguments()[1], locations.storage_root().as_os_str());
        let environment =
            runtime_environment(locations.storage_root(), Some(&package), []).unwrap();
        let root_pin = environment
            .iter()
            .find(|(name, _)| name == ROOT_VARIABLE)
            .unwrap();
        assert_eq!(root_pin.1, locations.storage_root().as_os_str());
        let record = boot_record_path(locations.storage_root());
        std::fs::create_dir_all(record.parent().unwrap()).unwrap();
        std::fs::write(&record, b"owned normalization probe").unwrap();
        assert_eq!(
            std::fs::read(boot_record_path(target.storage_root())).unwrap(),
            b"owned normalization probe"
        );
        assert!(!discarded.exists());
        return;
    }
    let fixture = Root::new();
    let package = fixture.0.join("package");
    let manifest = package.join(MODE_PACKAGE_MANIFEST);
    std::fs::create_dir_all(manifest.parent().unwrap()).unwrap();
    std::fs::write(manifest, b"{}").unwrap();
    let rule = INSTALLED_DEFAULTS
        .iter()
        .find(|rule| rule.platform == std::env::consts::OS)
        .unwrap();
    let candidate = rule.candidates.first().unwrap();
    let mut child = std::process::Command::new(std::env::current_exe().unwrap());
    child
        .args([
            "--exact",
            "normalized_default_root_is_shared_by_manager_arguments_and_child_pins",
            "--nocapture",
        ])
        .env(FIXTURE, &fixture.0)
        .env(
            candidate.variable,
            fixture.0.join("unused").join("..").join("selected"),
        );
    for name in INSTALLED_ROOT_PRECEDENCE.iter().chain(HOST_INHERITED_ENV) {
        child.env_remove(name);
    }
    let outcome = child.output().unwrap();
    assert!(
        outcome.status.success(),
        "{}{}",
        String::from_utf8_lossy(&outcome.stdout),
        String::from_utf8_lossy(&outcome.stderr)
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
