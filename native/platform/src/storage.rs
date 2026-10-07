//! Storage-root resolution and child environments from the generated native contract.
//!
//! Mirrors the Python storage declaration: mode comes from package or checkout evidence,
//! never the working directory; an absolute root override wins; the installed default is
//! the declared platform user-data base joined with the build channel's directory.

use crate::{
    BUILD_CHANNEL, CHANNEL_SEPARATOR, CLEARED_NAMES, CLEARED_PREFIXES, DEVELOPMENT_DEFAULT,
    DEVELOPMENT_RELATIVE_OVERRIDE, DEVELOPMENT_ROOT_PRECEDENCE, ENTRYPOINT_FILES,
    HOST_INHERITED_ENV, HOST_INHERITED_FIELDS, INHERITED_KIND_DIRECTORY_PATH, INSTALLED_DEFAULTS,
    INSTALLED_RELATIVE_OVERRIDE, INSTALLED_ROOT_PRECEDENCE, InstalledDefault, MODE_CHECKOUT_MARKER,
    MODE_PACKAGE_MANIFEST, MODE_PACKAGE_ROOT_FROM_EXECUTABLE, NAMESPACE_PREFIX, NATIVE, PINNED_ENV,
    PRODUCT_DIRECTORY, PRODUCT_ENV_ALLOWLIST, RESERVED_ENV, ROOT_REFUSAL_CHECKOUT_UNAVAILABLE,
    ROOT_REFUSAL_FILESYSTEM_PATH_REFUSED, ROOT_REFUSAL_HOME_UNAVAILABLE,
    ROOT_REFUSAL_INSTALLED_BASE_UNAVAILABLE, ROOT_REFUSAL_INVALID_PATH_INPUT,
    ROOT_REFUSAL_NON_ABSOLUTE_PIN, ROOT_REFUSAL_RELATIVE_OVERRIDE_INSTALLED, ROOT_REFUSALS,
    ROOT_VARIABLE, STABLE_CHANNEL, STORAGE_NORMALIZE_ABSOLUTE, STORAGE_REFUSE_LINKS,
    STORAGE_UNICODE_REQUIRED, TEMPORARY_CREATE_EXPLICIT, TEMPORARY_DEFAULT, TEMPORARY_ENV,
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

/// Whether an executable runs from an installed package or a source checkout.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    Development,
    Installed,
}

/// Package or checkout evidence for one executable; the working directory is never read.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Evidence {
    pub mode: Mode,
    /// The package root the executable belongs to.
    pub package: PathBuf,
    /// The source checkout in development mode.
    pub checkout: Option<PathBuf>,
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
    /// An operator override; `variable` is the root variable that supplied it.
    Override { variable: &'static str },
    /// The checkout's development default.
    CheckoutDefault,
    /// The per-user, per-channel installed default.
    InstalledDefault,
}

/// One resolved storage root and what selected it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ResolvedRoot {
    pub root: PathBuf,
    pub source: RootSource,
}

/// How much of a received environment a child process keeps.
///
/// `Operator` children keep allowlisted operator overrides; `Strict` children keep none.
/// Both keep host-inherited pins they receive, as the Python declaration does.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Profile {
    Operator,
    Strict,
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

fn filename_matches(left: &str, right: &str) -> bool {
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

/// Installed when the package root holds the package manifest; development when a
/// checkout marker is an ancestor of the executable; otherwise refuse.
pub fn detect_mode(exe: &Path) -> Result<Evidence, String> {
    if !exe.is_absolute() {
        return Err("Mode detection requires an absolute executable path".into());
    }
    let package = package_root(exe)?.join(relative_components(MODE_PACKAGE_ROOT_FROM_EXECUTABLE));
    if package
        .join(relative_components(MODE_PACKAGE_MANIFEST))
        .is_file()
    {
        return Ok(Evidence {
            mode: Mode::Installed,
            package,
            checkout: None,
        });
    }
    let directory = exe.parent().ok_or("Executable has no parent")?;
    if let Some(checkout) = directory
        .ancestors()
        .find(|ancestor| ancestor.join(MODE_CHECKOUT_MARKER).is_file())
    {
        return Ok(Evidence {
            mode: Mode::Development,
            package,
            checkout: Some(checkout.to_path_buf()),
        });
    }
    Err(format!(
        "CADRUMO cannot tell whether {} is installed or a development build: \
         {MODE_PACKAGE_MANIFEST} is not in the package and no ancestor directory holds \
         {MODE_CHECKOUT_MARKER}. Reinstall CADRUMO or run it from a source checkout.",
        exe.display()
    ))
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

/// The contract's root algorithm on explicit inputs, mirroring the Python resolver.
///
/// `known_folder` replaces the environment base the Python resolver reads, because
/// the native host asks the shell for `FOLDERID_LocalAppData` directly.
fn anchored_root(
    mode: Mode,
    lookup: &dyn Fn(&str) -> Option<OsString>,
    checkout: Option<&Path>,
    known_folder: Option<&Path>,
    channel: &str,
) -> Result<ResolvedRoot, Refusal> {
    let checkout_anchor = || {
        let anchor = checkout.map(Path::to_path_buf).ok_or_else(|| {
            refusal(
                ROOT_REFUSAL_CHECKOUT_UNAVAILABLE,
                "A development storage root needs the source checkout that anchors it.".into(),
            )
        })?;
        checked_path_value("Checkout", anchor.as_os_str())?;
        if !anchor.is_absolute() {
            return Err(refusal(
                ROOT_REFUSAL_NON_ABSOLUTE_PIN,
                "The checkout anchor must be absolute".into(),
            ));
        }
        Ok(anchor)
    };
    let precedence = match mode {
        Mode::Development => DEVELOPMENT_ROOT_PRECEDENCE,
        Mode::Installed => INSTALLED_ROOT_PRECEDENCE,
    };
    let mut selected = None;
    for name in precedence {
        if let Some(value) = nonblank(lookup, name)? {
            selected = Some((*name, value));
            break;
        }
    }
    if let Some((variable, raw)) = selected {
        let source = RootSource::Override { variable };
        let candidate = expand_home(&raw, lookup)?;
        if candidate.is_absolute() {
            return Ok(ResolvedRoot {
                root: candidate,
                source,
            });
        }
        let rule = match mode {
            Mode::Development => DEVELOPMENT_RELATIVE_OVERRIDE,
            Mode::Installed => INSTALLED_RELATIVE_OVERRIDE,
        };
        if rule != "anchor_at_checkout" {
            return Err(refusal(
                ROOT_REFUSAL_RELATIVE_OVERRIDE_INSTALLED,
                format!("{ROOT_VARIABLE} must be an absolute directory when CADRUMO is installed."),
            ));
        }
        if candidate.has_root()
            || candidate
                .components()
                .any(|part| matches!(part, Component::Prefix(_)))
        {
            return Err(refusal(
                ROOT_REFUSAL_NON_ABSOLUTE_PIN,
                "A relative override cannot replace its checkout anchor".into(),
            ));
        }
        return Ok(ResolvedRoot {
            root: checkout_anchor()?.join(candidate),
            source,
        });
    }
    if mode == Mode::Development {
        return Ok(ResolvedRoot {
            root: checkout_anchor()?.join(relative_components(DEVELOPMENT_DEFAULT)),
            source: RootSource::CheckoutDefault,
        });
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
    mode: Mode,
    lookup: &dyn Fn(&str) -> Option<OsString>,
    checkout: Option<&Path>,
    known_folder: Option<&Path>,
    channel: &str,
) -> Result<ResolvedRoot, Refusal> {
    let resolved = anchored_root(mode, lookup, checkout, known_folder, channel)?;
    Ok(ResolvedRoot {
        root: validated_absolute_path(&resolved.root)?,
        source: resolved.source,
    })
}

/// Replay the pure declaration independently of synthetic paths on the test host.
/// Filesystem vectors exercise `resolve_root` with actual isolated fixtures.
#[cfg(test)]
pub(crate) fn resolve_root_vector(
    mode: Mode,
    lookup: &dyn Fn(&str) -> Option<OsString>,
    checkout: Option<&Path>,
    known_folder: Option<&Path>,
    channel: &str,
) -> Result<ResolvedRoot, Refusal> {
    let resolved = anchored_root(mode, lookup, checkout, known_folder, channel)?;
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

/// Resolve this process's storage root for `evidence` from its environment and the shell.
///
/// The runtime manager manages a root only when `source` is [`RootSource::InstalledDefault`].
pub fn resolve_storage_root(evidence: &Evidence) -> Result<ResolvedRoot, Refusal> {
    resolve_storage_root_with(evidence, &|name| env::var_os(name))
}

/// Resolve against a captured environment without mutating the current process.
pub fn resolve_storage_root_with(
    evidence: &Evidence,
    lookup: &dyn Fn(&str) -> Option<OsString>,
) -> Result<ResolvedRoot, Refusal> {
    #[cfg(windows)]
    let known_folder = match evidence.mode {
        Mode::Installed => local_app_data(),
        Mode::Development => None,
    };
    #[cfg(unix)]
    let known_folder: Option<PathBuf> = None;
    resolve_root(
        evidence.mode,
        lookup,
        evidence.checkout.as_deref(),
        known_folder.as_deref(),
        BUILD_CHANNEL,
    )
}

/// The temporary-files member beneath `root`, honouring an operator override in `lookup`.
pub(crate) fn temporary_path(
    root: &Path,
    lookup: &dyn Fn(&str) -> Option<OsString>,
) -> Result<PathBuf, Refusal> {
    let explicit = nonblank(lookup, TEMPORARY_ENV)?;
    let path = match &explicit {
        Some(value) => expand_home(&value, lookup)?,
        None => relative_components(TEMPORARY_DEFAULT),
    };
    if !path.is_absolute()
        && (path.has_root()
            || path
                .components()
                .any(|part| matches!(part, Component::Prefix(_))))
    {
        return Err(refusal(
            ROOT_REFUSAL_NON_ABSOLUTE_PIN,
            "A relative member cannot replace its root anchor".into(),
        ));
    }
    let path = validated_absolute_path(&if path.is_absolute() {
        path
    } else {
        root.join(path)
    })?;
    if explicit.is_some() && !TEMPORARY_CREATE_EXPLICIT && !path.is_dir() {
        return Err(refusal(
            ROOT_REFUSAL_FILESYSTEM_PATH_REFUSED,
            "An explicit member must already exist".into(),
        ));
    }
    Ok(path)
}

/// Whether the contract clears `name` from a child built with `profile`.
///
/// `extra_allowed` names package-owned variables a native host keeps for itself.
pub(crate) fn cleared(name: &str, profile: Profile, extra_allowed: &[&str]) -> bool {
    let upper = if cfg!(windows) {
        name.to_uppercase()
    } else {
        name.to_owned()
    };
    let allowed = (profile == Profile::Operator && PRODUCT_ENV_ALLOWLIST.contains(&upper.as_str()))
        || extra_allowed.contains(&upper.as_str())
        || HOST_INHERITED_ENV.contains(&upper.as_str());
    CLEARED_PREFIXES
        .iter()
        .any(|prefix| upper.starts_with(prefix))
        || CLEARED_NAMES.contains(&upper.as_str())
        || ((upper.starts_with(NAMESPACE_PREFIX) || RESERVED_ENV.contains(&upper.as_str()))
            && !allowed)
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

/// Build a child environment that inherits `root` instead of re-resolving it.
///
/// Mirrors the Python `child_environment`: the contract's classes are cleared from
/// `ambient`; an `Operator` child keeps allowlisted overrides, a `Strict` child none;
/// received host-inherited pins pass unchanged; the root variable and the temporary
/// variables are pinned, and both directories are created.
pub fn child_environment<I>(
    profile: Profile,
    ambient: I,
    root: &Path,
) -> std::io::Result<Vec<(OsString, OsString)>>
where
    I: IntoIterator<Item = (OsString, OsString)>,
{
    let root = crate::normalize_absolute_path(root)?;
    let mut environment: Vec<(OsString, OsString)> = ambient
        .into_iter()
        .map(|(name, value)| {
            #[cfg(windows)]
            let name = name
                .to_str()
                .map(|name| OsString::from(name.to_uppercase()))
                .unwrap_or_else(|| name.to_ascii_uppercase());
            (name, value)
        })
        .filter(|(name, _)| !cleared(&name.to_string_lossy(), profile, &[]))
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
    let lookup = |name: &str| lookup_os(name).map(std::ffi::OsStr::to_owned);
    let temporary = temporary_path(&root, &lookup).map_err(std::io::Error::from)?;
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
            let mode = match vector.mode {
                "development" => Mode::Development,
                "installed" => Mode::Installed,
                other => panic!("undeclared mode {other}"),
            };
            let checkout = if vector.invalid_checkout {
                Some(PathBuf::from(crate::conformance_tests::invalid_unicode()))
            } else {
                vector.checkout.map(PathBuf::from)
            };
            let known_folder = if vector.invalid_known_folder {
                Some(PathBuf::from(crate::conformance_tests::invalid_unicode()))
            } else {
                vector.known_folder.map(PathBuf::from)
            };
            let outcome = resolve_root_vector(
                mode,
                &lookup,
                checkout.as_deref(),
                known_folder.as_deref(),
                vector.channel,
            );
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
        let installed =
            resolve_root(Mode::Installed, &none, None, Some(base), STABLE_CHANNEL).unwrap();
        assert_eq!(installed.source, RootSource::InstalledDefault);
        let checkout = Path::new(r"C:\src\checkout");
        let development = resolve_root(
            Mode::Development,
            &none,
            Some(checkout),
            None,
            STABLE_CHANNEL,
        )
        .unwrap();
        assert_eq!(development.source, RootSource::CheckoutDefault);
        let overridden = |name: &str| (name == ROOT_VARIABLE).then(|| OsString::from(r"D:\data"));
        let explicit = resolve_root(
            Mode::Installed,
            &overridden,
            None,
            Some(base),
            STABLE_CHANNEL,
        )
        .unwrap();
        assert_eq!(
            explicit.source,
            RootSource::Override {
                variable: ROOT_VARIABLE
            }
        );
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
        let resolved =
            resolve_root(Mode::Installed, &none, None, Some(&folder), BUILD_CHANNEL).unwrap();
        assert_eq!(resolved.root, folder.join(channel_directory(BUILD_CHANNEL)));
    }

    #[test]
    fn mode_comes_from_package_or_checkout_evidence_never_the_working_directory() {
        let installed = Scratch::new("installed");
        let manifest = installed.0.join(relative_components(MODE_PACKAGE_MANIFEST));
        fs::create_dir_all(manifest.parent().unwrap()).unwrap();
        fs::write(&manifest, b"{}").unwrap();
        let checkout = Scratch::new("checkout");
        fs::write(checkout.0.join(MODE_CHECKOUT_MARKER), b"[project]\n").unwrap();
        let unrelated = Scratch::new("unrelated");
        // A checkout marker in the working directory must not make anything a development build.
        fs::write(unrelated.0.join(MODE_CHECKOUT_MARKER), b"[project]\n").unwrap();
        let previous = env::current_dir().unwrap();
        env::set_current_dir(&unrelated.0).unwrap();

        let packaged = detect_mode(&installed.0.join(EXECUTABLE));
        let entrypoint = ENTRYPOINT_FILES[0];
        let packaged_entrypoint = detect_mode(&installed.0.join(NATIVE).join(entrypoint));
        let built = detect_mode(&checkout.0.join("build").join("bin").join(EXECUTABLE));
        // Mode detection only probes for files, so an absent directory at the drive root
        // stands outside every checkout even when the test runner's TEMP is inside one.
        let drive: PathBuf = env::temp_dir().components().take(2).collect();
        let orphan = drive.join(format!("cadrumo-platform-orphan-{}", std::process::id()));
        assert!(!orphan.exists() && !drive.join(MODE_CHECKOUT_MARKER).exists());
        let refused = detect_mode(&orphan.join(EXECUTABLE));
        env::set_current_dir(previous).unwrap();

        assert_eq!(
            packaged.unwrap(),
            Evidence {
                mode: Mode::Installed,
                package: installed.0.clone(),
                checkout: None,
            }
        );
        assert_eq!(packaged_entrypoint.unwrap().package, installed.0);
        let development = built.unwrap();
        assert_eq!(development.mode, Mode::Development);
        assert_eq!(development.checkout.as_deref(), Some(checkout.0.as_path()));
        assert!(refused.unwrap_err().contains(MODE_CHECKOUT_MARKER));
    }

    fn ambient() -> Vec<(OsString, OsString)> {
        [
            ("PATH", "ambient-path"),
            ("SYSTEMROOT", "ambient-system-root"),
            (ROOT_VARIABLE, r"C:\parent-root"),
            (TEMPORARY_ENV, "worker-temp"),
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
    fn child_environment_pins_the_root_and_follows_the_profile() {
        let scratch = Scratch::new("child");
        let root = scratch.0.join("root");
        let operator = child_environment(Profile::Operator, ambient(), &root).unwrap();
        let strict = child_environment(Profile::Strict, ambient(), &root).unwrap();
        for environment in [&operator, &strict] {
            assert_eq!(value(environment, ROOT_VARIABLE).unwrap(), root.as_os_str());
            assert!(value(environment, "PYTHONPATH").is_none());
            assert!(value(environment, "CADRUMO_SECRET_PASSPHRASE").is_none());
            assert_eq!(value(environment, "PATH").unwrap(), "ambient-path");
            for name in HOST_INHERITED_ENV {
                assert_eq!(value(environment, name).unwrap(), r"C:\authority");
            }
            assert_eq!(
                environment
                    .iter()
                    .filter(|(key, _)| key.to_string_lossy().eq_ignore_ascii_case(ROOT_VARIABLE))
                    .count(),
                1
            );
        }
        // An operator child keeps its temporary override; a strict child uses the declared member.
        assert_eq!(value(&operator, TEMPORARY_ENV).unwrap(), "worker-temp");
        assert_eq!(
            value(&operator, "TEMP").unwrap(),
            root.join("worker-temp").as_os_str()
        );
        assert!(value(&strict, TEMPORARY_ENV).is_none());
        let strict_temporary = root.join(relative_components(TEMPORARY_DEFAULT));
        assert_eq!(
            value(&strict, "TEMP").unwrap(),
            strict_temporary.as_os_str()
        );
        assert!(root.join("worker-temp").is_dir() && strict_temporary.is_dir());
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
