use crate::error::Error;
use std::{
    collections::BTreeMap,
    ffi::OsString,
    path::{Path, PathBuf},
    process::Command,
};

/// Complete environment projected by the platform owner, never merged with ambient state.
#[derive(Clone, Debug)]
pub struct ChildConfiguration {
    executable: PathBuf,
    working_directory: PathBuf,
    environment: BTreeMap<OsString, OsString>,
}

impl ChildConfiguration {
    pub fn new(
        executable: PathBuf,
        working_directory: PathBuf,
        environment: BTreeMap<OsString, OsString>,
    ) -> Result<Self, Error> {
        if !executable.is_absolute() || !working_directory.is_absolute() {
            return Err(Error::Invalid("child paths must be absolute".into()));
        }
        let mut names = std::collections::BTreeSet::new();
        for (key, value) in &environment {
            let key = key
                .to_str()
                .ok_or_else(|| Error::Invalid("non-UTF8 environment name".into()))?;
            if key.is_empty() || key.contains(['=', '\0']) || value.as_encoded_bytes().contains(&0)
            {
                return Err(Error::Invalid("invalid child environment".into()));
            }
            let identity = if cfg!(windows) {
                key.to_uppercase()
            } else {
                key.to_owned()
            };
            if !names.insert(identity) {
                return Err(Error::Invalid("ambiguous environment name casing".into()));
            }
        }
        Ok(Self {
            executable,
            working_directory,
            environment,
        })
    }
    /// Explicit preparation through the canonical platform owner. It can create the
    /// resolved root and temporary directory; it is not a capability inspection.
    #[cfg(feature = "platform")]
    pub fn from_platform(
        executable: PathBuf,
        working_directory: PathBuf,
        root: &Path,
        profile: cadrumo_platform::storage::Profile,
        ambient: impl IntoIterator<Item = (OsString, OsString)>,
    ) -> Result<Self, Error> {
        // Reject invalid command inputs before the owner prepares any directories.
        Self::new(
            executable.clone(),
            working_directory.clone(),
            BTreeMap::new(),
        )?;
        crate::filesystem::absolute_root(root)?;
        let environment = cadrumo_platform::storage::child_environment(profile, ambient, root)?;
        Self::new(
            executable,
            working_directory,
            environment.into_iter().collect(),
        )
    }
    pub fn executable(&self) -> &Path {
        &self.executable
    }
    pub fn environment(&self) -> &BTreeMap<OsString, OsString> {
        &self.environment
    }
    pub fn command(&self) -> Command {
        let mut command = Command::new(&self.executable);
        command
            .current_dir(&self.working_directory)
            .env_clear()
            .envs(&self.environment);
        command
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manual_environment_name_collisions_follow_native_case_identity() {
        let executable = std::env::current_exe().unwrap();
        let directory = std::env::temp_dir();
        for (first, second) in [("VALUE", "value"), ("ID", "ıd"), ("SS", "ß")] {
            let environment = BTreeMap::from([
                (OsString::from(first), OsString::from("first")),
                (OsString::from(second), OsString::from("second")),
            ]);
            let result =
                ChildConfiguration::new(executable.clone(), directory.clone(), environment.clone());
            if cfg!(windows) {
                assert!(matches!(result, Err(Error::Invalid(_))), "{first}/{second}");
            } else {
                assert_eq!(result.unwrap().environment(), &environment);
            }
        }
    }
}
