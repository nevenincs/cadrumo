//! Each packaged image's process environment, defined from its compiled launch profile.
//!
//! An image passes nothing it does not declare: the profile names the operating-system
//! base it takes from its caller, the operator settings and pass-through names it admits,
//! the launch parameters a parent may supply, the package facts it sets, and its `PATH`.

use crate::{
    EXECUTABLE, LAUNCH_AUTHORITY_PATH, LAUNCH_AUTHORITY_PIN, LAUNCH_IMAGES, LAUNCH_INVOCATIONS,
    LAUNCH_PATH_ENTRIES, LAUNCH_POSIX_SYSTEM_PATH, LAUNCH_PROFILES, LAUNCH_REFUSALS,
    LAUNCH_TEMPORARY_PINS, LAUNCH_WINDOWS_SYSTEM_SUBPATHS, LAUNCH_WINDOWS_SYSTEM_VARIABLE,
    LaunchInvocation, LaunchProfile, NATIVE, ROOT_VARIABLE, TEMPORARY_ENV, storage,
};
use std::{
    collections::BTreeMap,
    env,
    ffi::{OsStr, OsString},
    path::{Path, PathBuf},
};

/// A launch the image's profile refuses before Python starts; it carries no value.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LaunchRefusal {
    /// A required launch parameter is absent; the subject is its name.
    Missing(&'static str),
    /// A launch parameter fails its declared kind; the subject is its name.
    Malformed(&'static str),
    /// The image declares no profile for this invocation; the subject is the image.
    Undeclared(&'static str),
}

impl LaunchRefusal {
    /// The closed refusal code.
    pub fn code(&self) -> &'static str {
        let code = match self {
            Self::Missing(_) => "launch_value_missing",
            Self::Malformed(_) => "launch_value_malformed",
            Self::Undeclared(_) => "invocation_undeclared",
        };
        debug_assert!(LAUNCH_REFUSALS.contains(&code), "undeclared refusal {code}");
        code
    }

    /// The declared variable name or image the refusal concerns.
    pub fn subject(&self) -> &'static str {
        match self {
            Self::Missing(subject) | Self::Malformed(subject) | Self::Undeclared(subject) => {
                subject
            }
        }
    }

    /// The one machine-readable line a host writes as its last standard-error line.
    pub fn line(&self) -> String {
        // Codes and subjects are declared tokens and names, so they need no JSON escaping.
        format!(
            "{{\"native_refusal\":\"{}\",\"subject\":\"{}\"}}",
            self.code(),
            self.subject()
        )
    }
}

/// Why an environment could not be defined.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DefineError {
    /// The launch profile refuses the launch.
    Refused(LaunchRefusal),
    /// A platform or storage failure, described for the operator.
    Failed(String),
}

impl From<LaunchRefusal> for DefineError {
    fn from(refusal: LaunchRefusal) -> Self {
        Self::Refused(refusal)
    }
}

/// A lookup over a caller's environment.
pub type Lookup<'a> = dyn Fn(&str) -> Option<OsString> + 'a;

/// The package's root rule applied to a lookup over the caller's environment.
pub type ResolveRoot<'a> = dyn Fn(&Lookup<'_>) -> Result<PathBuf, storage::Refusal> + 'a;

/// A defined environment and the private directories it pins, which exist before launch.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Defined {
    pub environment: Vec<(OsString, OsString)>,
    pub directories: Vec<PathBuf>,
}

fn name_matches(key: &OsStr, name: &str) -> bool {
    if cfg!(windows) {
        key.to_str()
            .is_some_and(|key| key.to_uppercase() == name.to_uppercase())
    } else {
        key == name
    }
}

/// The last value `ambient` holds for `name`, matched as the platform compares names.
pub fn lookup(ambient: &[(OsString, OsString)], name: &str) -> Option<OsString> {
    ambient
        .iter()
        .rev()
        .find(|(key, _)| name_matches(key, name))
        .map(|(_, value)| value.clone())
}

/// The compiled profile named `name`.
pub fn profile(name: &str) -> Option<&'static LaunchProfile> {
    LAUNCH_PROFILES.iter().find(|profile| profile.name == name)
}

fn decimal(text: &str) -> Option<u64> {
    let first = text.bytes().next()?;
    if !text.bytes().all(|byte| byte.is_ascii_digit()) || (first == b'0' && text.len() > 1) {
        return None;
    }
    text.parse().ok()
}

fn argument_value(kind: &str, minimum: u64, text: &OsStr) -> Option<u64> {
    let value = decimal(text.to_str()?)?;
    let maximum = match kind {
        // A Windows HANDLE serialized by its supervisor; the all-ones value is invalid.
        "handle" => usize::MAX as u64 - 1,
        // A POSIX descriptor number.
        "descriptor" => i32::MAX as u64,
        _ => return None,
    };
    (value >= minimum.max(1) && value <= maximum).then_some(value)
}

fn invocation_matches(invocation: &LaunchInvocation, arguments: &[OsString]) -> bool {
    if invocation.arguments.len() != arguments.len() {
        return false;
    }
    let mut values = BTreeMap::new();
    for (declared, actual) in invocation.arguments.iter().zip(arguments) {
        match (declared.literal, declared.slot, declared.kind) {
            (Some(literal), _, _) if actual.as_os_str() == literal => {}
            (None, Some(slot), Some(kind)) => {
                match argument_value(kind, declared.minimum, actual) {
                    Some(value) => {
                        values.insert(slot, value);
                    }
                    None => return false,
                }
            }
            _ => return false,
        }
    }
    invocation
        .distinct
        .iter()
        .all(|(left, right)| values[left] != values[right])
        && invocation
            .greater
            .iter()
            .all(|(larger, smaller)| values[larger] > values[smaller])
}

/// Select the profile `image` applies to `arguments` (the arguments after the image's path).
///
/// A declared invocation selects its profile; otherwise the image's default profile
/// applies, and an image without one refuses the invocation.
pub fn select(image: &str, arguments: &[OsString]) -> Result<&'static LaunchProfile, DefineError> {
    let image = *LAUNCH_IMAGES
        .iter()
        .find(|declared| **declared == image)
        .ok_or_else(|| DefineError::Failed(format!("Image {image} has no launch profile")))?;
    if let Some(invocation) = LAUNCH_INVOCATIONS
        .iter()
        .find(|invocation| invocation.image == image && invocation_matches(invocation, arguments))
    {
        return profile(invocation.profile).ok_or_else(|| {
            DefineError::Failed(format!("Undeclared profile {}", invocation.profile))
        });
    }
    LAUNCH_PROFILES
        .iter()
        .find(|profile| profile.image == image && !profile.invoked)
        .ok_or(DefineError::Refused(LaunchRefusal::Undeclared(image)))
}

fn batch_file(path: &Path) -> bool {
    path.extension()
        .and_then(OsStr::to_str)
        .is_some_and(|extension| {
            extension.eq_ignore_ascii_case("bat") || extension.eq_ignore_ascii_case("cmd")
        })
}

/// Whether a launch parameter's value satisfies its declared kind.
pub fn slot_value_valid(kind: &str, value: &OsStr) -> bool {
    let Some(text) = value.to_str() else {
        return false;
    };
    let path = Path::new(text);
    match kind {
        "directory" => path.is_absolute() && path.is_dir(),
        "port" => decimal(text).is_some_and(|port| port <= u64::from(u16::MAX)),
        "executable" => path.is_absolute() && path.is_file() && !batch_file(path),
        "descriptor" => decimal(text).is_some_and(|value| value >= 1 && value <= i32::MAX as u64),
        _ => !text.is_empty(),
    }
}

/// The absolute path of a declared image inside `package`.
pub fn image_path(package: &Path, image: &str) -> Option<PathBuf> {
    if image == "python" {
        return Some(package.join(EXECUTABLE));
    }
    let suffix = Path::new(EXECUTABLE)
        .extension()
        .map(|extension| format!(".{}", extension.to_string_lossy()))
        .unwrap_or_default();
    LAUNCH_IMAGES
        .contains(&image)
        .then(|| package.join(NATIVE).join(format!("{image}{suffix}")))
}

fn admits(profile: &LaunchProfile, name: &str) -> bool {
    profile.operator.contains(&name) || profile.pass.contains(&name)
}

fn search_path(
    profile: &LaunchProfile,
    package: &Path,
    ambient: &[(OsString, OsString)],
) -> Result<OsString, DefineError> {
    let mut search = Vec::new();
    for entry in LAUNCH_PATH_ENTRIES {
        match entry.kind {
            "package" => search.push(if entry.value == "." {
                package.to_path_buf()
            } else {
                package.join(storage::relative_components(entry.value))
            }),
            "external" => {
                if !admits(profile, entry.value) {
                    continue;
                }
                if let Some(directories) = lookup(ambient, entry.value) {
                    for directory in env::split_paths(&directories) {
                        if !directory.is_absolute() || !directory.is_dir() {
                            return Err(DefineError::Failed(format!(
                                "{} requires existing absolute directories",
                                entry.value
                            )));
                        }
                        search.push(directory);
                    }
                }
            }
            "system" => {
                if cfg!(windows) {
                    let system =
                        lookup(ambient, LAUNCH_WINDOWS_SYSTEM_VARIABLE).ok_or_else(|| {
                            DefineError::Failed(format!(
                                "{LAUNCH_WINDOWS_SYSTEM_VARIABLE} is missing"
                            ))
                        })?;
                    let mut directory = PathBuf::from(system);
                    directory.extend(LAUNCH_WINDOWS_SYSTEM_SUBPATHS);
                    search.push(directory);
                } else {
                    search.extend(LAUNCH_POSIX_SYSTEM_PATH.iter().map(PathBuf::from));
                }
            }
            other => {
                return Err(DefineError::Failed(format!(
                    "Undeclared PATH entry {other}"
                )));
            }
        }
    }
    env::join_paths(search).map_err(|error| DefineError::Failed(error.to_string()))
}

/// Define `profile`'s environment from `ambient`, its caller's environment.
///
/// `package` is the image's package root. `resolve_root` applies the package's root rule
/// to a lookup over the caller's environment. Nothing is created or changed here; the
/// returned directories must exist before the environment is used.
pub fn define_environment(
    profile: &LaunchProfile,
    ambient: &[(OsString, OsString)],
    package: &Path,
    resolve_root: &ResolveRoot<'_>,
) -> Result<Defined, DefineError> {
    if profile.inherit {
        return Ok(Defined {
            environment: ambient.to_vec(),
            directories: Vec::new(),
        });
    }
    // Launch parameters are checked first: a refused launch defines nothing.
    let mut parameters = Vec::new();
    for slot in profile.slots {
        match lookup(ambient, slot.name) {
            Some(value) if slot_value_valid(slot.kind, &value) => {
                parameters.push((slot.name, value))
            }
            Some(_) => return Err(LaunchRefusal::Malformed(slot.name).into()),
            None if slot.required => return Err(LaunchRefusal::Missing(slot.name).into()),
            None => {}
        }
    }
    // Later entries win: base, operator settings, pass-through names, host pins,
    // package fixed values, then launch parameters.
    let mut defined: Vec<(&str, OsString)> = Vec::new();
    for name in profile
        .base
        .iter()
        .chain(profile.operator)
        .chain(profile.pass)
    {
        if let Some(value) = lookup(ambient, name) {
            defined.push((name, value));
        }
    }
    let mut directories = Vec::new();
    if profile.pins {
        let full = |name: &str| lookup(ambient, name);
        let root =
            resolve_root(&full).map_err(|refused| DefineError::Failed(refused.to_string()))?;
        let root = crate::normalize_absolute_path(&root)
            .map_err(|error| DefineError::Failed(error.to_string()))?;
        let member = |name: &str| {
            if name == TEMPORARY_ENV && !admits(profile, TEMPORARY_ENV) {
                None
            } else {
                lookup(ambient, name)
            }
        };
        let temporary = storage::temporary_path(&root, &member)
            .map_err(|refused| DefineError::Failed(refused.to_string()))?;
        let temporary = crate::normalize_absolute_path(&temporary)
            .map_err(|error| DefineError::Failed(error.to_string()))?;
        defined.push((ROOT_VARIABLE, root.clone().into_os_string()));
        for name in LAUNCH_TEMPORARY_PINS {
            defined.push((name, temporary.clone().into_os_string()));
        }
        defined.push((
            LAUNCH_AUTHORITY_PIN,
            package
                .join(storage::relative_components(LAUNCH_AUTHORITY_PATH))
                .into_os_string(),
        ));
        directories.extend([root, temporary]);
    }
    for fixed in profile.fixed {
        let value = match fixed.source {
            "value" => OsString::from(fixed.value),
            "package" => package
                .join(storage::relative_components(fixed.value))
                .into_os_string(),
            "image" => image_path(package, fixed.value)
                .ok_or_else(|| DefineError::Failed(format!("Undeclared image {}", fixed.value)))?
                .into_os_string(),
            other => {
                return Err(DefineError::Failed(format!(
                    "Undeclared fixed source {other}"
                )));
            }
        };
        defined.push((fixed.name, value));
    }
    defined.extend(parameters);
    if profile.package_path {
        defined.push(("PATH", search_path(profile, package, ambient)?));
    }
    let mut environment: Vec<(OsString, OsString)> = Vec::new();
    for (name, value) in defined {
        environment.retain(|(key, _)| !name_matches(key, name));
        environment.push((OsString::from(name), value));
    }
    Ok(Defined {
        environment,
        directories,
    })
}

/// Replace this process's environment with `defined` after creating its directories.
///
/// # Safety
/// The caller must exclude every concurrent environment access: no other thread may
/// read or write the environment while this runs.
pub unsafe fn apply(defined: &Defined) -> Result<(), DefineError> {
    for directory in &defined.directories {
        crate::create_private_directory(directory)
            .map_err(|error| DefineError::Failed(error.to_string()))?;
    }
    let names: Vec<OsString> = env::vars_os()
        .map(|(name, _)| name)
        // Windows keeps per-drive working directories under names that start with '='.
        .filter(|name| !name.to_string_lossy().starts_with('='))
        .collect();
    for name in names {
        unsafe { env::remove_var(name) };
    }
    for (name, value) in &defined.environment {
        unsafe { env::set_var(name, value) };
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::conformance_tests::Scratch;

    fn os(pairs: &[(&str, &str)]) -> Vec<(OsString, OsString)> {
        pairs
            .iter()
            .map(|(name, value)| (OsString::from(name), OsString::from(value)))
            .collect()
    }

    fn get<'a>(environment: &'a [(OsString, OsString)], name: &str) -> Option<&'a OsString> {
        environment
            .iter()
            .find(|(key, _)| name_matches(key, name))
            .map(|(_, value)| value)
    }

    fn system_name() -> &'static str {
        if cfg!(windows) { "SYSTEMROOT" } else { "HOME" }
    }

    fn fixed_root(root: PathBuf) -> impl Fn(&Lookup<'_>) -> Result<PathBuf, storage::Refusal> {
        move |_| Ok(root.clone())
    }

    #[test]
    fn python_defines_a_closed_environment_from_its_profile() {
        let scratch = Scratch::new("define-python");
        let package = scratch.0.join("package");
        let root = scratch.0.join("root");
        let profile = select("python", &[]).unwrap();
        assert_eq!(profile.name, "python");
        let ambient = os(&[
            (system_name(), "C:\\Windows"),
            ("CADRUMO_LOG_LEVEL", "DEBUG"),
            ("CADRUMO_SECRET_PASSPHRASE", "must-not-cross"),
            ("CADRUMO_AGENT_PORT", "0"),
            ("AEAT_BASE_URL", "https://example.invalid"),
            ("PYTHONPATH", "must-not-cross"),
            ("UNDECLARED_TOOL_TOKEN", "must-not-cross"),
            ("PATH", "ambient-path"),
            (LAUNCH_AUTHORITY_PIN, "C:\\elsewhere"),
        ]);
        let defined =
            define_environment(profile, &ambient, &package, &fixed_root(root.clone())).unwrap();
        let environment = &defined.environment;
        assert_eq!(get(environment, "CADRUMO_LOG_LEVEL").unwrap(), "DEBUG");
        assert!(get(environment, system_name()).is_some());
        for refused in [
            "CADRUMO_SECRET_PASSPHRASE",
            "CADRUMO_AGENT_PORT",
            "AEAT_BASE_URL",
            "PYTHONPATH",
            "UNDECLARED_TOOL_TOKEN",
        ] {
            assert!(get(environment, refused).is_none(), "{refused}");
        }
        assert_eq!(get(environment, ROOT_VARIABLE).unwrap(), root.as_os_str());
        let temporary = root.join(storage::relative_components(crate::TEMPORARY_DEFAULT));
        for name in LAUNCH_TEMPORARY_PINS {
            assert_eq!(get(environment, name).unwrap(), temporary.as_os_str());
        }
        assert_eq!(
            get(environment, LAUNCH_AUTHORITY_PIN).unwrap(),
            package
                .join(storage::relative_components(LAUNCH_AUTHORITY_PATH))
                .as_os_str()
        );
        let path: Vec<PathBuf> = env::split_paths(get(environment, "PATH").unwrap()).collect();
        assert_eq!(path[0], package);
        assert!(path.contains(&package.join(NATIVE)));
        assert!(!path.contains(&PathBuf::from("ambient-path")));
        assert_eq!(defined.directories, vec![root.clone(), temporary]);
        assert!(!root.exists(), "defining creates nothing");
    }

    #[test]
    fn the_runtime_keeps_no_operator_setting_or_temporary_override() {
        let scratch = Scratch::new("define-runtime");
        let root = scratch.0.join("root");
        let profile = select("cadrumo-runtime", &[]).unwrap();
        let ambient = os(&[
            (system_name(), "C:\\Windows"),
            ("CADRUMO_LOG_LEVEL", "DEBUG"),
            (TEMPORARY_ENV, "elsewhere"),
            ("CADRUMO_EXTERNAL_BIN_DIRS", "not-a-directory"),
        ]);
        let defined =
            define_environment(profile, &ambient, &scratch.0, &fixed_root(root.clone())).unwrap();
        assert!(get(&defined.environment, "CADRUMO_LOG_LEVEL").is_none());
        assert!(get(&defined.environment, TEMPORARY_ENV).is_none());
        assert_eq!(
            get(&defined.environment, LAUNCH_TEMPORARY_PINS[0]).unwrap(),
            root.join(storage::relative_components(crate::TEMPORARY_DEFAULT))
                .as_os_str()
        );
    }

    #[test]
    fn an_operator_image_honours_its_admitted_temporary_and_external_directories() {
        let scratch = Scratch::new("define-operator");
        let root = scratch.0.join("root");
        let external = scratch.0.join("tools");
        std::fs::create_dir(&external).unwrap();
        let profile = select("aeat", &[]).unwrap();
        let ambient = vec![
            (OsString::from(system_name()), OsString::from("C:\\Windows")),
            (OsString::from(TEMPORARY_ENV), OsString::from("scratch")),
            (
                OsString::from("CADRUMO_EXTERNAL_BIN_DIRS"),
                external.clone().into_os_string(),
            ),
        ];
        let defined =
            define_environment(profile, &ambient, &scratch.0, &fixed_root(root.clone())).unwrap();
        assert_eq!(
            get(&defined.environment, LAUNCH_TEMPORARY_PINS[0]).unwrap(),
            root.join("scratch").as_os_str()
        );
        let path: Vec<PathBuf> =
            env::split_paths(get(&defined.environment, "PATH").unwrap()).collect();
        assert_eq!(path[1], external);
        let invalid = os(&[
            (system_name(), "C:\\Windows"),
            ("CADRUMO_EXTERNAL_BIN_DIRS", "relative"),
        ]);
        assert!(matches!(
            define_environment(profile, &invalid, &scratch.0, &fixed_root(root)),
            Err(DefineError::Failed(_))
        ));
    }

    fn kdf_arguments() -> Vec<OsString> {
        let invocation = LAUNCH_INVOCATIONS
            .iter()
            .find(|invocation| invocation.profile == "kdf-child")
            .unwrap();
        let mut next = 3;
        invocation
            .arguments
            .iter()
            .map(|argument| match (argument.literal, argument.slot) {
                (Some(literal), _) => OsString::from(literal),
                (None, Some("bound")) => OsString::from("1024"),
                (None, _) => {
                    next += 1;
                    OsString::from(next.to_string())
                }
            })
            .collect()
    }

    fn numeric_positions(arguments: &[OsString]) -> Vec<usize> {
        (0..arguments.len())
            .filter(|index| {
                arguments[*index]
                    .to_str()
                    .is_some_and(|text| text.bytes().all(|byte| byte.is_ascii_digit()))
            })
            .collect()
    }

    #[test]
    fn the_kdf_invocation_selects_the_parent_defined_environment_unchanged() {
        let arguments = kdf_arguments();
        let profile = select("python", &arguments).unwrap();
        assert_eq!(profile.name, "kdf-child");
        let ambient = os(&[("NEUTRAL", "kept"), ("CADRUMO_ANY", "kept")]);
        let defined = define_environment(
            profile,
            &ambient,
            Path::new("/"),
            &fixed_root(PathBuf::from("/")),
        )
        .unwrap();
        assert_eq!(defined.environment, ambient);
        assert!(defined.directories.is_empty());
        // A near miss is not the declared invocation: the image's default profile applies.
        let slots = numeric_positions(&arguments);
        let mut repeated = arguments.clone();
        repeated[slots[1]] = repeated[slots[0]].clone();
        assert_eq!(select("python", &repeated).unwrap().name, "python");
        let mut padded = arguments.clone();
        padded[slots[0]] = OsString::from(format!("0{}", arguments[slots[0]].to_string_lossy()));
        assert_eq!(select("python", &padded).unwrap().name, "python");
        assert_eq!(select("python", &arguments[1..]).unwrap().name, "python");
    }

    #[test]
    fn an_undeclared_image_fails_and_refusal_lines_carry_no_value() {
        assert!(matches!(
            select("unknown", &[]),
            Err(DefineError::Failed(_))
        ));
        assert_eq!(
            LaunchRefusal::Malformed("CADRUMO_EXAMPLE").line(),
            "{\"native_refusal\":\"launch_value_malformed\",\"subject\":\"CADRUMO_EXAMPLE\"}"
        );
        assert_eq!(LaunchRefusal::Missing("X").code(), "launch_value_missing");
        assert_eq!(
            LaunchRefusal::Undeclared("image").code(),
            "invocation_undeclared"
        );
    }

    #[test]
    fn launch_parameter_kinds_validate_values() {
        let scratch = Scratch::new("slot-kinds");
        let file = scratch.0.join("relay.exe");
        let batch = scratch.0.join("relay.cmd");
        std::fs::write(&file, b"").unwrap();
        std::fs::write(&batch, b"").unwrap();
        assert!(slot_value_valid("directory", scratch.0.as_os_str()));
        assert!(!slot_value_valid("directory", OsStr::new("relative")));
        assert!(!slot_value_valid("directory", file.as_os_str()));
        for port in ["0", "8080", "65535"] {
            assert!(slot_value_valid("port", OsStr::new(port)), "{port}");
        }
        for port in ["65536", "-1", "08080", "", "80 "] {
            assert!(!slot_value_valid("port", OsStr::new(port)), "{port}");
        }
        assert!(slot_value_valid("executable", file.as_os_str()));
        assert!(!slot_value_valid("executable", batch.as_os_str()));
        assert!(!slot_value_valid("executable", scratch.0.as_os_str()));
        assert!(slot_value_valid("descriptor", OsStr::new("7")));
        assert!(!slot_value_valid("descriptor", OsStr::new("0")));
        assert!(!slot_value_valid(
            "port",
            &crate::conformance_tests::invalid_unicode()
        ));
    }
}
