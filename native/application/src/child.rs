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
            // Windows inherits hidden entries such as =C: from cmd.exe. The
            // first '=' belongs to the name; any later '=' is still invalid.
            let name = if cfg!(windows) {
                key.strip_prefix('=').unwrap_or(key)
            } else {
                key
            };
            if name.is_empty()
                || name.contains(['=', '\0'])
                || value.as_encoded_bytes().contains(&0)
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
        ambient: impl IntoIterator<Item = (OsString, OsString)>,
    ) -> Result<Self, Error> {
        // Reject invalid command inputs before the owner prepares any directories.
        Self::new(
            executable.clone(),
            working_directory.clone(),
            BTreeMap::new(),
        )?;
        crate::filesystem::absolute_root(root)?;
        let environment = cadrumo_platform::storage::child_environment(ambient, root)?;
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
    fn hidden_environment_names_follow_the_platform_boundary() {
        for key in ["=C:", "=ExitCode"] {
            let environment = BTreeMap::from([(OsString::from(key), OsString::from("value"))]);
            let result = ChildConfiguration::new(
                std::env::current_exe().unwrap(),
                std::env::temp_dir(),
                environment.clone(),
            );
            if cfg!(windows) {
                assert_eq!(result.unwrap().environment(), &environment);
            } else {
                assert!(matches!(result, Err(Error::Invalid(_))));
            }
        }
        for (key, value) in [
            ("", "value"),
            ("=", "value"),
            ("A=B", "value"),
            ("=C:=bad", "value"),
            ("A\0B", "value"),
            ("VALID", "bad\0value"),
        ] {
            assert!(
                ChildConfiguration::new(
                    std::env::current_exe().unwrap(),
                    std::env::temp_dir(),
                    BTreeMap::from([(OsString::from(key), OsString::from(value))]),
                )
                .is_err()
            );
        }
    }

    #[cfg(windows)]
    #[test]
    fn hidden_environment_child() {
        if std::env::var_os("CADRUMO_TEST_HIDDEN_ENV").is_none() {
            return;
        }
        assert!(std::env::vars_os().any(|(key, value)| key == "=C:" && value == r"C:\"));
    }

    #[cfg(windows)]
    #[test]
    fn hidden_drive_environment_survives_real_child_creation() {
        use std::os::windows::process::CommandExt;

        let directory = std::env::current_dir().unwrap();
        let command = std::env::current_exe().unwrap();
        let mut environment: BTreeMap<_, _> = std::env::vars_os().collect();
        environment.insert(OsString::from("=C:"), OsString::from(r"C:\"));
        environment.insert(
            OsString::from("CADRUMO_TEST_HIDDEN_ENV"),
            OsString::from("1"),
        );
        let child = ChildConfiguration::new(command, directory, environment).unwrap();
        let output = child
            .command()
            .args([
                "--exact",
                "child::tests::hidden_environment_child",
                "--nocapture",
            ])
            .creation_flags(0x08000000)
            .output()
            .unwrap();
        assert!(output.status.success(), "{output:?}");
    }

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
