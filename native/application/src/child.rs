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
            if !names.insert(key.to_ascii_uppercase()) {
                return Err(Error::Invalid("ambiguous environment name casing".into()));
            }
        }
        Ok(Self {
            executable,
            working_directory,
            environment,
        })
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
