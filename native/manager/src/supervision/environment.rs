//! Canonical installed locations and strict child environments for the manager.
//!
//! The platform owner resolves the root. Only its installed default is managed;
//! developer roots and authority overrides never become managed by clearing variables.

use crate::contract::{AUTHORITY, HOST_INHERITED_ENV};
use cadrumo_platform::storage::{self, Evidence, Mode, Profile, ResolvedRoot, RootSource};
use std::ffi::OsString;
use std::io;
use std::path::{Path, PathBuf};

/// The resolved, pinned locations of one installed manager.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ManagedLocations {
    package: PathBuf,
    storage: PathBuf,
}

impl ManagedLocations {
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
        let resolved = storage::resolve_storage_root(&evidence)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error.message))?;
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
        })
    }

    pub fn package_root(&self) -> &Path {
        &self.package
    }
    pub fn storage_root(&self) -> &Path {
        &self.storage
    }
}

/// Prepare the platform's strict environment against an already pinned root.
/// Package authority comes only from the selected package, never the ambient environment.
pub fn runtime_environment(
    root: &Path,
    package: Option<&Path>,
    inherited: impl IntoIterator<Item = (OsString, OsString)>,
) -> io::Result<Vec<(OsString, OsString)>> {
    if package.is_some_and(|package| !package.is_absolute()) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "the package root must be absolute",
        ));
    }
    let inherited = inherited.into_iter().filter(|(name, _)| {
        !HOST_INHERITED_ENV.iter().any(|pin| {
            if cfg!(windows) {
                name.to_string_lossy().eq_ignore_ascii_case(pin)
            } else {
                name == pin
            }
        })
    });
    let mut environment = storage::child_environment(Profile::Strict, inherited, root)?;
    if let Some(package) = package {
        let authority = package.join(AUTHORITY);
        environment.extend(
            HOST_INHERITED_ENV
                .iter()
                .map(|name| (OsString::from(name), authority.clone().into_os_string())),
        );
    }
    Ok(environment)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract::ROOT_VARIABLE;

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
