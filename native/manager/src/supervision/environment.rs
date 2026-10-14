//! Canonical installed locations and strict child environments for the manager.
//!
//! The platform owner resolves the root. Only its installed default is managed;
//! developer roots and authority overrides never become managed by clearing variables.

use crate::contract::{HOST_INHERITED_ENV, LAUNCH_AUTHORITY_PIN, ROOT_VARIABLE};
use cadrumo_platform::launch::{self, DefineError};
use cadrumo_platform::storage::{self, Evidence, Mode, ResolvedRoot, RootSource};
use std::ffi::OsString;
use std::io;
use std::path::{Path, PathBuf};

/// The resolved, pinned locations of one installed manager.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ManagedLocations {
    package: PathBuf,
    storage: PathBuf,
    default_root: bool,
}

impl ManagedLocations {
    /// Admit a packaged desktop host's actual canonical root, including an
    /// explicit operator-selected root. This does not manufacture installation
    /// evidence or convert an authority override into trusted package authority.
    pub fn for_host(executable: &Path, package: &Path, root: &Path) -> io::Result<Self> {
        if !executable.is_absolute() || !package.is_absolute() || !root.is_absolute() {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        if storage::authority_override_present(std::env::vars_os()) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "host authority override is unsupported",
            ));
        }
        let evidence = storage::detect_mode(executable).map_err(io::Error::other)?;
        let resolved = storage::resolve_storage_root(&evidence).map_err(io::Error::from)?;
        if evidence.mode != Mode::Installed
            || std::fs::canonicalize(&evidence.package)? != std::fs::canonicalize(package)?
            || std::fs::canonicalize(&resolved.root)? != std::fs::canonicalize(root)?
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(Self {
            package: evidence.package,
            storage: resolved.root,
            default_root: resolved.source == RootSource::InstalledDefault,
        })
    }
    /// Resolve once from executable package evidence and canonical OS defaults.
    /// This does not create directories or launch an interpreter.
    pub fn resolve(executable: &Path) -> io::Result<Self> {
        if storage::authority_override_present(std::env::vars_os()) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "an authority override is unmanaged",
            ));
        }
        let evidence = storage::detect_mode(executable).map_err(io::Error::other)?;
        let resolved = storage::resolve_storage_root(&evidence).map_err(io::Error::from)?;
        Self::from_resolved(evidence, resolved)
    }

    fn from_resolved(evidence: Evidence, resolved: ResolvedRoot) -> io::Result<Self> {
        if evidence.mode != Mode::Installed || resolved.source != RootSource::InstalledDefault {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "only the installed default root is managed",
            ));
        }
        if !evidence.package.is_absolute() || !resolved.root.is_absolute() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "manager locations must be absolute",
            ));
        }
        Ok(Self {
            package: evidence.package,
            storage: resolved.root,
            default_root: true,
        })
    }

    #[cfg(all(windows, any(test, feature = "fixture-test-mode")))]
    pub fn fixture(package: PathBuf, storage: PathBuf) -> io::Result<Self> {
        Self::from_resolved(
            Evidence {
                mode: Mode::Installed,
                package,
                checkout: None,
            },
            ResolvedRoot {
                root: storage,
                source: RootSource::InstalledDefault,
            },
        )
    }

    pub fn package_root(&self) -> &Path {
        &self.package
    }
    pub fn storage_root(&self) -> &Path {
        &self.storage
    }
    pub fn is_default_root(&self) -> bool {
        self.default_root
    }
}

/// The packaged runtime image whose launch profile defines the runtime's environment.
const RUNTIME_IMAGE: &str = "cadrumo-runtime";

fn same_name(name: &std::ffi::OsStr, declared: &str) -> bool {
    if cfg!(windows) {
        name.to_str()
            .is_some_and(|name| name.to_uppercase() == declared.to_uppercase())
    } else {
        name == declared
    }
}

/// Define the runtime image's environment from its launch profile against an already
/// pinned root, and create the root and temporary directories it pins.
///
/// The runtime host defines the same environment again from what it receives. Package
/// authority comes only from the selected package, never the ambient environment. A
/// fixture image has no package: it receives no authority pin and no fixed value that
/// locates a package file, and it keeps its caller's `PATH`.
pub fn runtime_environment(
    root: &Path,
    package: Option<&Path>,
    inherited: impl IntoIterator<Item = (OsString, OsString)>,
) -> io::Result<Vec<(OsString, OsString)>> {
    if package.is_some_and(|package| !package.is_absolute()) || !root.is_absolute() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "the package and storage roots must be absolute",
        ));
    }
    let mut ambient: Vec<(OsString, OsString)> = inherited
        .into_iter()
        .filter(|(name, _)| {
            !same_name(name, ROOT_VARIABLE)
                && !HOST_INHERITED_ENV.iter().any(|pin| same_name(name, pin))
        })
        .collect();
    let caller_path = ambient
        .iter()
        .rev()
        .find(|(name, _)| same_name(name, "PATH"))
        .map(|(_, value)| value.clone());
    ambient.push((OsString::from(ROOT_VARIABLE), root.as_os_str().to_owned()));
    let failed = |error: DefineError| match error {
        DefineError::Refused(refusal) => {
            io::Error::new(io::ErrorKind::InvalidInput, refusal.line())
        }
        DefineError::Failed(message) => io::Error::new(io::ErrorKind::InvalidInput, message),
    };
    let profile = launch::select(RUNTIME_IMAGE, &[]).map_err(failed)?;
    let defined = launch::define_environment(profile, &ambient, package.unwrap_or(root), &|_| {
        Ok(root.to_path_buf())
    })
    .map_err(failed)?;
    launch::create_directories(&defined).map_err(failed)?;
    let mut environment = defined.environment;
    if package.is_none() {
        let located = |name: &OsString| {
            profile.fixed.iter().any(|fixed| {
                matches!(fixed.source, "package" | "image") && same_name(name, fixed.name)
            })
        };
        environment.retain(|(name, _)| {
            !same_name(name, LAUNCH_AUTHORITY_PIN) && !same_name(name, "PATH") && !located(name)
        });
        environment.extend(caller_path.map(|path| (OsString::from("PATH"), path)));
    }
    Ok(environment)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract::ROOT_VARIABLE;

    #[test]
    fn host_cannot_turn_relative_paths_into_package_or_storage_authority() {
        let absolute = std::env::temp_dir();
        for (executable, package, root) in [
            (
                Path::new("python.exe"),
                absolute.as_path(),
                absolute.as_path(),
            ),
            (absolute.as_path(), Path::new("package"), absolute.as_path()),
            (absolute.as_path(), absolute.as_path(), Path::new("storage")),
        ] {
            assert_eq!(
                ManagedLocations::for_host(executable, package, root)
                    .unwrap_err()
                    .kind(),
                io::ErrorKind::InvalidInput
            );
        }
    }

    #[test]
    fn only_an_installed_default_is_managed() {
        let path = std::env::temp_dir();
        for (mode, source, accepted) in [
            (Mode::Installed, RootSource::InstalledDefault, true),
            (
                Mode::Installed,
                RootSource::Override {
                    variable: ROOT_VARIABLE,
                },
                false,
            ),
            (Mode::Development, RootSource::CheckoutDefault, false),
        ] {
            let result = ManagedLocations::from_resolved(
                Evidence {
                    mode,
                    package: path.clone(),
                    checkout: None,
                },
                ResolvedRoot {
                    root: path.clone(),
                    source,
                },
            );
            assert_eq!(result.is_ok(), accepted);
        }
    }
}
