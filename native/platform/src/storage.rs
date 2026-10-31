//! Storage-root resolution and child environments from the generated native contract.
//!
//! The root is the one root variable when it is set, which must be absolute, and otherwise
//! the declared per-user platform data base joined with the build channel's directory. Every
//! image resolves it the same way, whatever configuration built it: nothing is baked in at
//! compile time and nothing is read from the working directory. Every other location is a
//! declared path beneath the root.

use crate::{
    BUILD_CHANNEL, CHANNEL_SEPARATOR, CLEARED_NAMES, CLEARED_PREFIXES, ENTRYPOINT_FILES,
    HOST_INHERITED_ENV, HOST_INHERITED_FIELDS, INHERITED_KIND_DIRECTORY_PATH, INSTALLED_DEFAULTS,
    InstalledDefault, NAMESPACE_PREFIX, NATIVE, PACKAGE_MANIFEST, PACKAGE_ROOT_FROM_EXECUTABLE,
    PINNED_ENV, PRODUCT_DIRECTORY, ROOT_REFUSAL_FILESYSTEM_PATH_REFUSED,
    ROOT_REFUSAL_HOME_UNAVAILABLE, ROOT_REFUSAL_INSTALLED_BASE_UNAVAILABLE,
    ROOT_REFUSAL_INVALID_PATH_INPUT, ROOT_REFUSAL_NON_ABSOLUTE_PIN,
    ROOT_REFUSAL_RELATIVE_OVERRIDE_INSTALLED, ROOT_REFUSALS, ROOT_VARIABLE, STABLE_CHANNEL,
    STORAGE_NORMALIZE_ABSOLUTE, STORAGE_REFUSE_LINKS, STORAGE_UNICODE_REQUIRED, TEMPORARY_MEMBER,
};
#[cfg(windows)]
use std::os::windows::ffi::OsStringExt;
use std::{
    env,
    ffi::OsString,
    path::{Component, Path, PathBuf},
};
#[cfg(windows)]
use std::{ffi::c_void, ptr};

/// The package one executable belongs to; the working directory is never read.
///
/// Package evidence locates package files only. It never selects a storage root.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Package {
    /// The package root the executable belongs to.
    pub root: PathBuf,
    /// Whether the package root holds the package manifest.
    pub packaged: bool,
}

impl Package {
    /// Locate the package `exe` belongs to without requiring its manifest.
    pub fn locate(exe: &Path) -> Result<Self, String> {
        if !exe.is_absolute() {
            return Err("Package location requires an absolute executable path".into());
        }
        let root = package_root(exe)?.join(relative_components(PACKAGE_ROOT_FROM_EXECUTABLE));
        let packaged = root.join(relative_components(PACKAGE_MANIFEST)).is_file();
        Ok(Self { root, packaged })
    }

    /// Locate the package `exe` belongs to and require its manifest.
    pub fn installed(exe: &Path) -> Result<Self, String> {
        let package = Self::locate(exe)?;
        if !package.packaged {
            return Err(format!(
                "{} is not part of an installed CADRUMO package: {PACKAGE_MANIFEST} is \
                 missing. Reinstall CADRUMO.",
                exe.display()
            ));
        }
        Ok(package)
    }
}

/// A declared refusal: `code` is one of the contract's root refusals.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Refusal {
    pub code: &'static str,
    pub message: String,
}

impl std::fmt::Display for Refusal {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for Refusal {}

impl From<Refusal> for std::io::Error {
    fn from(refused: Refusal) -> Self {
        let kind = if refused.code == ROOT_REFUSAL_FILESYSTEM_PATH_REFUSED {
            std::io::ErrorKind::Other
        } else {
            std::io::ErrorKind::InvalidInput
        };
        std::io::Error::new(kind, refused)
    }
}

/// What selected a resolved storage root.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RootSource {
    /// The operator's absolute root variable.
    Override,
    /// The per-user, per-channel installed default.
    InstalledDefault,
}

/// One resolved storage root and what selected it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ResolvedRoot {
    pub root: PathBuf,
    pub source: RootSource,
}

fn refusal(code: &'static str, message: String) -> Refusal {
    debug_assert!(ROOT_REFUSALS.contains(&code), "undeclared refusal {code}");
    Refusal { code, message }
}

pub(crate) fn relative_components(relative: &str) -> PathBuf {
    relative
        .split('/')
        .filter(|part| !part.is_empty() && *part != ".")
        .collect()
}

pub(crate) fn filename_matches(left: &str, right: &str) -> bool {
    if cfg!(windows) {
        left.eq_ignore_ascii_case(right)
    } else {
        left == right
    }
}

/// Declared console entrypoints live in NATIVE; every other image sits at the package root.
pub(crate) fn package_root(exe: &Path) -> Result<PathBuf, String> {
    let directory = exe.parent().ok_or("Executable has no parent")?;
    let declared = exe
        .file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| {
            ENTRYPOINT_FILES
                .iter()
                .any(|file| filename_matches(file, name))
        });
    if !declared {
        return Ok(directory.to_path_buf());
    }
    let mut package = directory;
    for expected in Path::new(NATIVE).components().rev() {
        let inside = package
            .file_name()
            .and_then(|name| name.to_str())
            .zip(expected.as_os_str().to_str())
            .is_some_and(|(actual, expected)| filename_matches(actual, expected));
        if !inside {
            return Err(format!(
                "Entrypoint must reside in the package {NATIVE} directory: {}",
                exe.display()
            ));
        }
        package = package.parent().ok_or("Entrypoint has no package root")?;
    }
    Ok(package.to_path_buf())
}

pub(crate) fn channel_directory(channel: &str) -> String {
    if channel == STABLE_CHANNEL {
        PRODUCT_DIRECTORY.to_owned()
    } else {
        format!("{PRODUCT_DIRECTORY}{CHANNEL_SEPARATOR}{channel}")
    }
}

fn platform_rule() -> &'static InstalledDefault {
    INSTALLED_DEFAULTS
        .iter()
        .find(|rule| rule.platform == std::env::consts::OS)
        .expect("the contract declares the target installed default")
}

fn checked_path_value(name: &str, value: &std::ffi::OsStr) -> Result<String, Refusal> {
    let value = value
        .to_str()
        .filter(|value| !value.contains('\0'))
        .ok_or_else(|| {
            refusal(
                ROOT_REFUSAL_INVALID_PATH_INPUT,
                format!("{name} cannot be represented as a Unicode path"),
            )
        })?;
    Ok(value.to_owned())
}

pub(crate) fn validate_inherited_pin(
    field: &crate::InheritedEnvironmentField,
    value: &std::ffi::OsStr,
) -> Result<(), Refusal> {
    if field.kind == INHERITED_KIND_DIRECTORY_PATH {
        checked_path_value(field.name, value)?;
        if !Path::new(value).is_absolute() {
            return Err(refusal(
                ROOT_REFUSAL_NON_ABSOLUTE_PIN,
                format!("{} must be an absolute inherited pin", field.name),
            ));
        }
    }
    Ok(())
}

fn nonblank(
    lookup: &dyn Fn(&str) -> Option<OsString>,
    name: &str,
) -> Result<Option<String>, Refusal> {
    lookup(name)
        .map(|value| checked_path_value(name, &value))
        .transpose()
        .map(|value| {
            value
                .map(|value| value.trim().to_owned())
                .filter(|value| !value.is_empty())
        })
}

fn absolute_path_input(path: &Path) -> Result<(), Refusal> {
    if STORAGE_UNICODE_REQUIRED {
        checked_path_value("Storage path", path.as_os_str())?;
    }
    if !path.is_absolute() {
        return Err(refusal(
            ROOT_REFUSAL_NON_ABSOLUTE_PIN,
            "Storage path must be absolute".into(),
        ));
    }
    Ok(())
}

fn normalized_absolute_components(path: &Path) -> PathBuf {
    let mut normalized = PathBuf::new();
    if STORAGE_NORMALIZE_ABSOLUTE {
        for component in path.components() {
            match component {
                Component::CurDir => {}
                Component::ParentDir => {
                    normalized.pop();
                }
                component => normalized.push(component),
            }
        }
    } else {
        normalized = path.to_path_buf();
    }
    normalized
}

pub fn validated_absolute_path(path: &Path) -> Result<PathBuf, Refusal> {
    absolute_path_input(path)?;
    if STORAGE_REFUSE_LINKS {
        crate::refuse_links(path)
            .map_err(|message| refusal(ROOT_REFUSAL_FILESYSTEM_PATH_REFUSED, message))?;
    }
    let normalized = normalized_absolute_components(path);
    if STORAGE_REFUSE_LINKS {
        crate::refuse_links(&normalized)
            .map_err(|message| refusal(ROOT_REFUSAL_FILESYSTEM_PATH_REFUSED, message))?;
    }
    Ok(normalized)
}

/// Expand a leading `~` (the current user only) against the platform home variable.
fn expand_home(value: &str, lookup: &dyn Fn(&str) -> Option<OsString>) -> Result<PathBuf, Refusal> {
    #[cfg(windows)]
    let normalized = value.replace('\\', "/");
    #[cfg(unix)]
    let normalized = value.to_owned();
    let (head, tail) = normalized.split_once('/').unwrap_or((&normalized, ""));
    if head != "~" {
        if head.starts_with('~') && (cfg!(windows) || !head.starts_with("~\\")) {
            return Err(refusal(
                ROOT_REFUSAL_INVALID_PATH_INPUT,
                "Named-user home expansion is not supported".into(),
            ));
        }
        return Ok(PathBuf::from(value));
    }
    let home_variable = platform_rule().home_variable;
    match nonblank(lookup, home_variable)?.map(PathBuf::from) {
        Some(home) if home.is_absolute() => Ok(home.join(relative_components(tail))),
        _ => Err(refusal(
            ROOT_REFUSAL_HOME_UNAVAILABLE,
            format!("{ROOT_VARIABLE} starts with '~' but {home_variable} is not an absolute path."),
        )),
    }
}

/// The contract's root algorithm on explicit inputs.
///
/// `known_folder` replaces the environment base the command line reads, because the
/// native host asks the shell for `FOLDERID_LocalAppData` directly.
fn anchored_root(
    lookup: &dyn Fn(&str) -> Option<OsString>,
    known_folder: Option<&Path>,
    channel: &str,
) -> Result<ResolvedRoot, Refusal> {
    if let Some(raw) = nonblank(lookup, ROOT_VARIABLE)? {
        let candidate = expand_home(&raw, lookup)?;
        if candidate.is_absolute() {
            return Ok(ResolvedRoot {
                root: candidate,
                source: RootSource::Override,
            });
        }
        return Err(refusal(
            ROOT_REFUSAL_RELATIVE_OVERRIDE_INSTALLED,
            format!("{ROOT_VARIABLE} must be an absolute directory."),
        ));
    }
    #[cfg(unix)]
    let selected = {
        let mut selected = None;
        for candidate in platform_rule().candidates {
            if let Some(base) = nonblank(lookup, candidate.variable)?.map(PathBuf::from)
                && base.is_absolute()
            {
                selected = Some((base, candidate));
                break;
            }
        }
        selected
    };
    #[cfg(unix)]
    let (base, subpath) = selected.map_or((None, PathBuf::new()), |(base, candidate)| {
        (Some(base), candidate.subpath.iter().collect())
    });
    #[cfg(unix)]
    let known_folder = {
        let _ = known_folder;
        base.as_deref()
    };
    #[cfg(windows)]
    let subpath: PathBuf = platform_rule().candidates[0].subpath.iter().collect();
    if let Some(base) = known_folder {
        checked_path_value("Installed base", base.as_os_str())?;
    }
    match known_folder {
        Some(base) if base.is_absolute() => Ok(ResolvedRoot {
            root: base.join(subpath).join(channel_directory(channel)),
            source: RootSource::InstalledDefault,
        }),
        _ => Err(refusal(
            ROOT_REFUSAL_INSTALLED_BASE_UNAVAILABLE,
            format!(
                "CADRUMO cannot locate the per-user local application data folder. \
                 Set {ROOT_VARIABLE} to an absolute directory."
            ),
        )),
    }
}

pub(crate) fn resolve_root(
    lookup: &dyn Fn(&str) -> Option<OsString>,
    known_folder: Option<&Path>,
    channel: &str,
) -> Result<ResolvedRoot, Refusal> {
    let resolved = anchored_root(lookup, known_folder, channel)?;
    Ok(ResolvedRoot {
        root: validated_absolute_path(&resolved.root)?,
        source: resolved.source,
    })
}

/// Replay the pure declaration independently of synthetic paths on the test host.
/// Filesystem vectors exercise `resolve_root` with actual isolated fixtures.
#[cfg(test)]
pub(crate) fn resolve_root_vector(
    lookup: &dyn Fn(&str) -> Option<OsString>,
    known_folder: Option<&Path>,
    channel: &str,
) -> Result<ResolvedRoot, Refusal> {
    let resolved = anchored_root(lookup, known_folder, channel)?;
    absolute_path_input(&resolved.root)?;
    Ok(ResolvedRoot {
        root: normalized_absolute_components(&resolved.root),
        source: resolved.source,
    })
}

#[cfg(windows)]
#[repr(C)]
struct Guid {
    data1: u32,
    data2: u16,
    data3: u16,
    data4: [u8; 8],
}
/// FOLDERID_LocalAppData, {F1B32785-6FBA-4FCF-9D55-7B8E7F157091}.
#[cfg(windows)]
const FOLDERID_LOCAL_APP_DATA: Guid = Guid {
    data1: 0xF1B3_2785,
    data2: 0x6FBA,
    data3: 0x4FCF,
    data4: [0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91],
};
#[cfg(windows)]
#[link(name = "shell32")]
unsafe extern "system" {
    fn SHGetKnownFolderPath(
        id: *const Guid,
        flags: u32,
        token: *mut c_void,
        path: *mut *mut u16,
    ) -> i32;
}
#[cfg(windows)]
#[link(name = "ole32")]
unsafe extern "system" {
    fn CoTaskMemFree(memory: *mut c_void);
}

/// The current user's local application data folder from the shell, never the environment.
#[cfg(windows)]
pub(crate) fn local_app_data() -> Option<PathBuf> {
    let mut raw: *mut u16 = ptr::null_mut();
    let status =
        unsafe { SHGetKnownFolderPath(&FOLDERID_LOCAL_APP_DATA, 0, ptr::null_mut(), &mut raw) };
    let folder = if status >= 0 && !raw.is_null() {
        let length = (0..)
            .take_while(|&index| unsafe { *raw.add(index) } != 0)
            .count();
        let wide = unsafe { std::slice::from_raw_parts(raw, length) };
        Some(PathBuf::from(OsString::from_wide(wide)))
    } else {
        None
    };
    // The shell allocates the string even on some failures; freeing null is a no-op.
    unsafe { CoTaskMemFree(raw.cast()) };
    folder
}

/// Resolve this process's storage root from its environment and the shell.
pub fn resolve_storage_root() -> Result<ResolvedRoot, Refusal> {
    resolve_storage_root_with(&|name| env::var_os(name))
}

/// Resolve against a captured environment without mutating the current process.
pub fn resolve_storage_root_with(
    lookup: &dyn Fn(&str) -> Option<OsString>,
) -> Result<ResolvedRoot, Refusal> {
    #[cfg(windows)]
    let known_folder = if nonblank(lookup, ROOT_VARIABLE)?.is_some() {
        None
    } else {
        local_app_data()
    };
    #[cfg(unix)]
    let known_folder: Option<PathBuf> = None;
    resolve_root(lookup, known_folder.as_deref(), BUILD_CHANNEL)
}

/// A location beneath `root`: the slash-separated declared `relative` path, without creating it.
pub fn member_path(root: &Path, relative: &str) -> Result<PathBuf, Refusal> {
    validated_absolute_path(&root.join(relative_components(relative)))
}

/// The temporary-files member beneath `root`.
pub(crate) fn temporary_path(root: &Path) -> Result<PathBuf, Refusal> {
    member_path(root, TEMPORARY_MEMBER)
}

/// Whether a strict child filter clears `name`: the declared host classes and every
/// product-namespace name except a received host-inherited pin.
pub(crate) fn cleared(name: &str) -> bool {
    let upper = if cfg!(windows) {
        name.to_uppercase()
    } else {
        name.to_owned()
    };
    CLEARED_PREFIXES
        .iter()
        .any(|prefix| upper.starts_with(prefix))
        || CLEARED_NAMES.contains(&upper.as_str())
        || (upper.starts_with(NAMESPACE_PREFIX) && !HOST_INHERITED_ENV.contains(&upper.as_str()))
}

/// Clear the canonical strict host classes without pinning a runtime storage root.
/// Manager entry dispatch must let its successor resolve the installed default itself.
pub fn strict_host_environment(
    ambient: impl IntoIterator<Item = (OsString, OsString)>,
) -> Vec<(OsString, OsString)> {
    ambient
        .into_iter()
        .filter(|(name, _)| !cleared(&name.to_string_lossy()))
        .collect()
}

/// Whether `ambient` carries a host-inherited pin such as the authority root.
///
/// A launcher that must derive authority only from its own package refuses up front.
pub fn authority_override_present<I, K, V>(ambient: I) -> bool
where
    I: IntoIterator<Item = (K, V)>,
    K: AsRef<std::ffi::OsStr>,
    V: AsRef<std::ffi::OsStr>,
{
    ambient.into_iter().any(|(name, value)| {
        !value.as_ref().is_empty()
            && HOST_INHERITED_ENV
                .iter()
                .any(|pin| environment_name_matches(name.as_ref(), pin))
    })
}

fn environment_name_matches(name: &std::ffi::OsStr, expected: &str) -> bool {
    if cfg!(windows) {
        name.to_str()
            .is_some_and(|name| name.to_uppercase() == expected)
    } else {
        name == expected
    }
}

/// Build a strict child environment that inherits `root` instead of re-resolving it.
///
/// The declared host classes and every product-namespace name are cleared from
/// `ambient`; received host-inherited pins pass unchanged; the root variable and the
/// temporary variables are pinned, and both directories are created. A packaged
/// interpreter image defines its own environment from its launch profile instead.
pub fn child_environment<I>(ambient: I, root: &Path) -> std::io::Result<Vec<(OsString, OsString)>>
where
    I: IntoIterator<Item = (OsString, OsString)>,
{
    let root = crate::normalize_absolute_path(root)?;
    let ambient = ambient.into_iter();
    #[cfg(windows)]
    let ambient = ambient.map(|(name, value)| {
        let name = name
            .to_str()
            .map(|name| OsString::from(name.to_uppercase()))
            .unwrap_or_else(|| name.to_ascii_uppercase());
        (name, value)
    });
    let mut environment: Vec<(OsString, OsString)> = ambient
        .filter(|(name, _)| !cleared(&name.to_string_lossy()))
        .collect::<std::collections::BTreeMap<_, _>>()
        .into_iter()
        .collect();
    let lookup_os = |name: &str| {
        environment
            .iter()
            .find(|(key, _)| environment_name_matches(key, name))
            .map(|(_, value)| value.as_os_str())
    };
    for field in HOST_INHERITED_FIELDS {
        if let Some(value) = lookup_os(field.name) {
            validate_inherited_pin(field, value)?;
        }
    }
    let temporary = temporary_path(&root).map_err(std::io::Error::from)?;
    let temporary = crate::normalize_absolute_path(&temporary)?;
    crate::create_private_directory(&root)?;
    crate::create_private_directory(&temporary)?;
    environment.retain(|(name, _)| {
        !PINNED_ENV
            .iter()
            .any(|pinned| environment_name_matches(name, pinned))
    });
    for name in PINNED_ENV {
        let value = if *name == ROOT_VARIABLE {
            root.as_path()
        } else {
            temporary.as_path()
        };
        environment.push((OsString::from(name), value.as_os_str().to_owned()));
    }
    Ok(environment)
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;
    use crate::EXECUTABLE;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Scratch(PathBuf);
    impl Scratch {
        fn new(label: &str) -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = env::temp_dir().join(format!(
                "cadrumo-platform-{label}-{}-{nanos}",
                std::process::id()
            ));
            fs::create_dir_all(&path).unwrap();
            Scratch(path)
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn same_path(actual: &Path, expected: &str) -> bool {
        actual.components().eq(Path::new(expected).components())
    }

    #[test]
    fn package_root_maps_declared_entrypoints_from_the_native_directory() {
        let package = Path::new(r"C:\Program Files\CADRUMO\app");
        let interpreter = package.join(EXECUTABLE);
        assert_eq!(package_root(&interpreter).unwrap(), package);
        for file in ENTRYPOINT_FILES {
            let entrypoint = package.join(NATIVE).join(file);
            assert_eq!(package_root(&entrypoint).unwrap(), package);
            let uppercase = package
                .join(NATIVE.to_uppercase())
                .join(file.to_uppercase());
            assert_eq!(package_root(&uppercase).unwrap(), package);
        }
    }

    #[test]
    fn package_root_refuses_a_declared_entrypoint_outside_the_native_directory() {
        assert!(!ENTRYPOINT_FILES.is_empty());
        let package = Path::new(r"C:\Program Files\CADRUMO\app");
        for file in ENTRYPOINT_FILES {
            assert!(package_root(&package.join(file)).is_err());
            assert!(package_root(&package.join("data").join(file)).is_err());
        }
        let undeclared = package.join(NATIVE).join("other.exe");
        assert_eq!(package_root(&undeclared).unwrap(), package.join(NATIVE));
    }

    #[test]
    fn resolver_reproduces_every_windows_contract_vector() {
        let windows: Vec<_> = crate::STORAGE_ROOT_VECTORS
            .iter()
            .filter(|vector| vector.platform == "windows")
            .collect();
        assert!(
            windows.len() >= 10,
            "the contract carries the Windows vectors"
        );
        for vector in windows {
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
            let known_folder = if vector.invalid_known_folder {
                Some(PathBuf::from(crate::conformance_tests::invalid_unicode()))
            } else {
                vector.known_folder.map(PathBuf::from)
            };
            let outcome = resolve_root_vector(&lookup, known_folder.as_deref(), vector.channel);
            match (outcome, vector.expected_root, vector.refusal) {
                (Ok(resolved), Some(expected), None) => assert!(
                    same_path(&resolved.root, expected),
                    "{}: resolved {} expected {expected}",
                    vector.name,
                    resolved.root.display()
                ),
                (Err(refused), None, Some(code)) => {
                    assert_eq!(refused.code, code, "{}", vector.name)
                }
                (outcome, expected, code) => panic!(
                    "{}: got {outcome:?}, expected root {expected:?} refusal {code:?}",
                    vector.name
                ),
            }
        }
    }

    #[test]
    fn resolved_root_reports_whether_an_override_or_a_default_selected_it() {
        let base = Path::new(r"C:\Users\ada\AppData\Local");
        let none = |_: &str| None;
        let installed = resolve_root(&none, Some(base), STABLE_CHANNEL).unwrap();
        assert_eq!(installed.source, RootSource::InstalledDefault);
        let overridden = |name: &str| (name == ROOT_VARIABLE).then(|| OsString::from(r"D:\data"));
        let explicit = resolve_root(&overridden, Some(base), STABLE_CHANNEL).unwrap();
        assert_eq!(explicit.source, RootSource::Override);
        assert_eq!(explicit.root, PathBuf::from(r"D:\data"));
    }

    #[test]
    fn known_folder_default_matches_the_shell_local_application_data() {
        let folder = local_app_data().expect("the shell reports FOLDERID_LocalAppData");
        assert!(folder.is_absolute());
        if let Some(local) = env::var_os("LOCALAPPDATA") {
            assert_eq!(folder, PathBuf::from(local));
        }
        let none = |_: &str| None;
        let resolved = resolve_root(&none, Some(&folder), BUILD_CHANNEL).unwrap();
        assert_eq!(resolved.root, folder.join(channel_directory(BUILD_CHANNEL)));
    }

    #[test]
    fn package_evidence_comes_from_the_image_never_the_working_directory() {
        let installed = Scratch::new("installed");
        let manifest = installed.0.join(relative_components(PACKAGE_MANIFEST));
        fs::create_dir_all(manifest.parent().unwrap()).unwrap();
        fs::write(&manifest, b"{}").unwrap();
        let unrelated = Scratch::new("unrelated");
        let previous = env::current_dir().unwrap();
        env::set_current_dir(&installed.0).unwrap();

        let packaged = Package::installed(&installed.0.join(EXECUTABLE));
        let entrypoint = ENTRYPOINT_FILES[0];
        let packaged_entrypoint = Package::installed(&installed.0.join(NATIVE).join(entrypoint));
        // The working directory holds a package manifest, but the image beside it does not.
        let refused = Package::installed(&unrelated.0.join(EXECUTABLE));
        let located = Package::locate(&unrelated.0.join(EXECUTABLE));
        env::set_current_dir(previous).unwrap();

        assert_eq!(
            packaged.unwrap(),
            Package {
                root: installed.0.clone(),
                packaged: true,
            }
        );
        assert_eq!(packaged_entrypoint.unwrap().root, installed.0);
        assert!(refused.unwrap_err().contains(PACKAGE_MANIFEST));
        assert!(!located.unwrap().packaged);
    }

    fn ambient() -> Vec<(OsString, OsString)> {
        [
            ("PATH", "ambient-path"),
            ("SYSTEMROOT", "ambient-system-root"),
            (ROOT_VARIABLE, r"C:\parent-root"),
            (
                crate::conformance_tests::RETIRED_TEMPORARY_OVERRIDE,
                "worker-temp",
            ),
            ("PYTHONPATH", "must-not-cross"),
            ("XDG_CACHE_HOME", r"C:\former-cache"),
        ]
        .into_iter()
        .chain(
            HOST_INHERITED_ENV
                .iter()
                .map(|name| (*name, r"C:\authority")),
        )
        .chain(std::iter::once((
            "CADRUMO_SECRET_PASSPHRASE",
            "must-not-cross",
        )))
        .map(|(name, value)| (OsString::from(name), OsString::from(value)))
        .collect()
    }

    fn value<'a>(environment: &'a [(OsString, OsString)], name: &str) -> Option<&'a OsString> {
        environment
            .iter()
            .find(|(key, _)| key.to_string_lossy().eq_ignore_ascii_case(name))
            .map(|(_, value)| value)
    }

    #[test]
    fn child_environment_pins_the_root_and_keeps_no_product_setting() {
        let scratch = Scratch::new("child");
        let root = scratch.0.join("root");
        let environment = child_environment(ambient(), &root).unwrap();
        assert_eq!(
            value(&environment, ROOT_VARIABLE).unwrap(),
            root.as_os_str()
        );
        assert!(value(&environment, "PYTHONPATH").is_none());
        assert!(value(&environment, "CADRUMO_SECRET_PASSPHRASE").is_none());
        assert_eq!(value(&environment, "PATH").unwrap(), "ambient-path");
        for name in HOST_INHERITED_ENV {
            assert_eq!(value(&environment, name).unwrap(), r"C:\authority");
        }
        assert_eq!(
            environment
                .iter()
                .filter(|(key, _)| key.to_string_lossy().eq_ignore_ascii_case(ROOT_VARIABLE))
                .count(),
            1
        );
        // A received temporary override is a product setting: the declared member applies.
        assert!(
            value(
                &environment,
                crate::conformance_tests::RETIRED_TEMPORARY_OVERRIDE
            )
            .is_none()
        );
        let temporary = root.join(relative_components(TEMPORARY_MEMBER));
        assert_eq!(value(&environment, "TEMP").unwrap(), temporary.as_os_str());
        assert!(temporary.is_dir() && !root.join("worker-temp").exists());
    }

    #[test]
    fn authority_override_presence_reads_only_the_host_inherited_pins() {
        assert!(!HOST_INHERITED_ENV.is_empty());
        assert!(authority_override_present(ambient()));
        let without: Vec<_> = ambient()
            .into_iter()
            .filter(|(name, _)| {
                !HOST_INHERITED_ENV
                    .iter()
                    .any(|pin| name.to_string_lossy().eq_ignore_ascii_case(pin))
            })
            .collect();
        assert!(!authority_override_present(without));
        let blank = HOST_INHERITED_ENV
            .iter()
            .map(|name| (OsString::from(name), OsString::new()));
        assert!(!authority_override_present(blank));
    }
}
