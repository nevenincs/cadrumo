//! Resolution of the platform's interactive system shell and of the package
//! directory that leads its search path.
//!
//! The shell is always an absolute path derived from fixed system locations,
//! never a program name looked up through `PATH` or the working directory.
use cadrumo_application::{
    error::application::{ErrorCode, Result},
    value::RelativePath,
};
use serde::Deserialize;
use std::{
    collections::BTreeMap,
    ffi::{OsStr, OsString},
    path::{Path, PathBuf},
};

use super::session::failure;

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
}
#[derive(Deserialize)]
struct Layout {
    paths: Paths,
}
#[derive(Deserialize)]
struct Paths {
    executable: String,
    native: String,
}

/// The package directory holding console entrypoints, derived from the
/// verified interpreter path and the generated layout contract.
pub fn package_bin(interpreter: &Path) -> Result<PathBuf> {
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))?;
    bin_beside(
        interpreter,
        &contract.layout.paths.executable,
        &contract.layout.paths.native,
    )
}

fn bin_beside(interpreter: &Path, executable: &str, native: &str) -> Result<PathBuf> {
    let invalid = || failure(ErrorCode::EnvironmentFailed);
    let executable = RelativePath::new(executable).map_err(|e| invalid().caused_by(e))?;
    let native = RelativePath::new(native).map_err(|e| invalid().caused_by(e))?;
    if !interpreter.is_absolute() || !interpreter.ends_with(executable.as_str()) {
        return Err(invalid());
    }
    let mut root = interpreter;
    for _ in executable.as_str().split('/') {
        root = root.parent().ok_or_else(invalid)?;
    }
    Ok(native.under(root))
}

#[cfg(any(windows, test))]
fn variable<'a>(environment: &'a BTreeMap<OsString, OsString>, name: &str) -> Option<&'a OsStr> {
    environment
        .iter()
        .find(|(key, _)| {
            if cfg!(windows) {
                key.eq_ignore_ascii_case(name)
            } else {
                key.as_os_str() == name
            }
        })
        .map(|(_, value)| value.as_os_str())
}

/// Prefer both native commands and the bundled Python interpreter.
pub fn with_package_first(
    environment: BTreeMap<OsString, OsString>,
    interpreter: &Path,
) -> Result<BTreeMap<OsString, OsString>> {
    let bin = package_bin(interpreter)?;
    let python = interpreter
        .parent()
        .ok_or_else(|| failure(ErrorCode::EnvironmentFailed))?;
    with_bin_first(with_bin_first(environment, python)?, &bin)
}

/// Refuse a moved, missing or linked workspace before opening another terminal.
pub fn validate_workspace(workspace: &Path, storage: &Path) -> Result<()> {
    let invalid = || failure(ErrorCode::EnvironmentFailed);
    if !workspace.is_absolute()
        || workspace == storage
        || !workspace.starts_with(storage)
        || !workspace.is_dir()
    {
        return Err(invalid());
    }
    #[cfg(windows)]
    cadrumo_platform::storage::validated_absolute_path(workspace)
        .map_err(|e| invalid().caused_by(e))?;
    #[cfg(not(windows))]
    for ancestor in workspace.ancestors() {
        let metadata = std::fs::symlink_metadata(ancestor).map_err(|e| invalid().caused_by(e))?;
        if metadata.is_symlink() {
            return Err(invalid());
        }
    }
    Ok(())
}

/// Returns `environment` with `bin` ahead of every other search directory.
pub fn with_bin_first(
    mut environment: BTreeMap<OsString, OsString>,
    bin: &Path,
) -> Result<BTreeMap<OsString, OsString>> {
    let key = environment
        .keys()
        .find(|key| {
            if cfg!(windows) {
                key.eq_ignore_ascii_case("PATH")
            } else {
                key.as_os_str() == "PATH"
            }
        })
        .cloned()
        .unwrap_or_else(|| "PATH".into());
    let existing = environment.get(&key).cloned().unwrap_or_default();
    let joined = std::env::join_paths(
        std::iter::once(bin.to_path_buf()).chain(
            // An empty value holds no directory; splitting it would add one.
            (!existing.is_empty())
                .then(|| std::env::split_paths(&existing))
                .into_iter()
                .flatten()
                .filter(|path| {
                    if cfg!(windows) {
                        !path.as_os_str().eq_ignore_ascii_case(bin.as_os_str())
                    } else {
                        path != bin
                    }
                }),
        ),
    )
    .map_err(|e| failure(ErrorCode::EnvironmentFailed).caused_by(e))?;
    environment.retain(|name, _| {
        if cfg!(windows) {
            !name.eq_ignore_ascii_case("PATH")
        } else {
            name.as_os_str() != "PATH"
        }
    });
    environment.insert(key, joined);
    Ok(environment)
}

/// PowerShell 7 from the 64-bit program directory when installed, otherwise
/// Windows PowerShell 5.1 from the system directory.
#[cfg(any(windows, test))]
fn windows_shell(
    environment: &BTreeMap<OsString, OsString>,
    is_file: impl Fn(&Path) -> bool,
) -> Option<PathBuf> {
    let absolute = |name| {
        variable(environment, name)
            .map(PathBuf::from)
            .filter(|path| path.is_absolute())
    };
    let core = ["ProgramW6432", "ProgramFiles"]
        .into_iter()
        .filter_map(absolute)
        .map(|base| base.join("PowerShell").join("7").join("pwsh.exe"));
    let desktop = absolute("SystemRoot").map(|root| {
        root.join("System32")
            .join("WindowsPowerShell")
            .join("v1.0")
            .join("powershell.exe")
    });
    core.chain(desktop).find(|candidate| is_file(candidate))
}

/// The login shell field of the passwd entry for `uid`.
#[cfg(any(target_os = "linux", test))]
fn passwd_shell(passwd: &str, uid: u32) -> Option<PathBuf> {
    passwd.lines().find_map(|line| {
        let fields: Vec<&str> = line.split(':').collect();
        let [_, _, entry, _, _, _, shell] = fields.as_slice() else {
            return None;
        };
        // passwd paths are POSIX paths whatever the host platform.
        (entry.parse() == Ok(uid) && shell.starts_with('/')).then(|| PathBuf::from(shell))
    })
}

/// The interactive shell program and its arguments.
pub fn shell(environment: &BTreeMap<OsString, OsString>) -> Result<(PathBuf, Vec<OsString>)> {
    #[cfg(windows)]
    {
        windows_shell(environment, Path::is_file)
            .map(|shell| (shell, vec!["-NoLogo".into()]))
            .ok_or_else(|| failure(ErrorCode::SpawnFailed))
    }
    #[cfg(target_os = "linux")]
    {
        use std::os::unix::fs::MetadataExt;
        let _ = environment;
        let uid = std::fs::metadata("/proc/self")
            .map_err(|e| failure(ErrorCode::SpawnFailed).caused_by(e))?
            .uid();
        let passwd = std::fs::read_to_string("/etc/passwd")
            .map_err(|e| failure(ErrorCode::SpawnFailed).caused_by(e))?;
        passwd_shell(&passwd, uid)
            .filter(|shell| shell.is_file())
            .map(|shell| (shell, Vec::new()))
            .ok_or_else(|| failure(ErrorCode::SpawnFailed))
    }
    #[cfg(not(any(windows, target_os = "linux")))]
    {
        let _ = environment;
        Err(failure(ErrorCode::UnsupportedPlatform))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn environment(pairs: &[(&str, &str)]) -> BTreeMap<OsString, OsString> {
        pairs
            .iter()
            .map(|(key, value)| ((*key).into(), (*value).into()))
            .collect()
    }

    #[cfg(windows)]
    #[test]
    fn powershell_7_is_preferred_and_5_1_is_the_fallback() {
        let environment = environment(&[
            ("ProgramW6432", r"C:\Program Files"),
            ("SystemRoot", r"C:\WINDOWS"),
            ("PATH", r".;C:\elsewhere"),
        ]);
        let core = PathBuf::from(r"C:\Program Files\PowerShell\7\pwsh.exe");
        let desktop = PathBuf::from(r"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe");
        assert_eq!(windows_shell(&environment, |_| true), Some(core.clone()));
        assert_eq!(
            windows_shell(&environment, |path| path == desktop),
            Some(desktop.clone())
        );
        assert_eq!(windows_shell(&environment, |_| false), None);
    }

    #[cfg(windows)]
    #[test]
    fn relative_or_missing_system_locations_are_never_searched() {
        let relative = environment(&[
            ("ProgramFiles", r"Program Files"),
            ("SystemRoot", r"WINDOWS"),
        ]);
        assert_eq!(windows_shell(&relative, |_| true), None);
        let lowercase = environment(&[("systemroot", r"D:\Win")]);
        assert_eq!(
            windows_shell(&lowercase, |_| true),
            Some(PathBuf::from(
                r"D:\Win\System32\WindowsPowerShell\v1.0\powershell.exe"
            ))
        );
        assert_eq!(windows_shell(&BTreeMap::new(), |_| true), None);
    }

    #[test]
    fn the_login_shell_comes_from_the_matching_passwd_entry() {
        let passwd = "root:x:0:0:root:/root:/bin/bash\n\
                      broken line\n\
                      alice:x:1000:1000:Alice,,,:/home/alice:/usr/bin/zsh\n\
                      bob:x:1001:1001::/home/bob:bin/sh\n";
        assert_eq!(passwd_shell(passwd, 1000), Some("/usr/bin/zsh".into()));
        assert_eq!(passwd_shell(passwd, 0), Some("/bin/bash".into()));
        assert_eq!(passwd_shell(passwd, 1001), None);
        assert_eq!(passwd_shell(passwd, 4242), None);
    }

    #[test]
    fn package_bin_goes_first_on_the_search_path() {
        let bin = std::env::temp_dir().join("package").join("bin");
        let other = std::env::temp_dir().join("other");
        let joined = std::env::join_paths([&other]).unwrap();
        let mut existing = BTreeMap::new();
        existing.insert(
            OsString::from(if cfg!(windows) { "Path" } else { "PATH" }),
            joined,
        );
        let updated = with_bin_first(existing, &bin).unwrap();
        assert_eq!(updated.len(), 1);
        let (_, value) = updated.iter().next().unwrap();
        assert_eq!(
            std::env::split_paths(value).collect::<Vec<_>>(),
            [bin.clone(), other]
        );
        let created = with_bin_first(BTreeMap::new(), &bin).unwrap();
        assert_eq!(
            created.get(OsStr::new("PATH")),
            Some(&bin.clone().into_os_string())
        );
    }

    #[test]
    fn workspace_must_be_an_existing_directory_below_storage() {
        let workspace = std::fs::canonicalize(std::env::temp_dir()).unwrap();
        let storage = workspace.parent().unwrap();
        assert!(validate_workspace(&workspace, storage).is_ok());
        assert!(validate_workspace(&workspace, &workspace).is_err());
        assert!(validate_workspace(&workspace.join("cadrumo-workspace-absent"), storage).is_err());
        assert!(validate_workspace(Path::new("workspace"), storage).is_err());
        assert!(validate_workspace(&workspace, &workspace.join("other")).is_err());
    }

    #[cfg(windows)]
    #[test]
    fn search_path_has_only_one_case_insensitive_name() {
        let bin = std::env::temp_dir().join("package").join("bin");
        let updated =
            with_bin_first(environment(&[("PATH", "C:/one"), ("Path", "C:/two")]), &bin).unwrap();
        assert_eq!(
            updated
                .keys()
                .filter(|name| name.eq_ignore_ascii_case("PATH"))
                .count(),
            1
        );
        let paths: Vec<_> = std::env::split_paths(updated.values().next().unwrap()).collect();
        assert_eq!(paths[0], bin);
    }

    #[test]
    fn repeated_search_path_preparation_keeps_one_package_directory() {
        let bin = std::env::temp_dir().join("package").join("bin");
        let once = with_bin_first(BTreeMap::new(), &bin).unwrap();
        assert_eq!(with_bin_first(once.clone(), &bin).unwrap(), once);
    }

    #[test]
    fn package_bin_is_derived_from_the_interpreter_and_layout() {
        let root = std::env::temp_dir().join("package");
        assert_eq!(
            bin_beside(&root.join("python.exe"), "python.exe", "bin").unwrap(),
            root.join("bin")
        );
        assert_eq!(
            bin_beside(&root.join("bin").join("python3"), "bin/python3", "lib/bin").unwrap(),
            root.join("lib").join("bin")
        );
        assert!(bin_beside(&root.join("other.exe"), "python.exe", "bin").is_err());
        assert!(bin_beside(Path::new("python.exe"), "python.exe", "bin").is_err());
        assert!(bin_beside(&root.join("python.exe"), "python.exe", "../bin").is_err());
    }
}
