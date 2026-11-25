//! The test binary placed at a fixture's path as the program the fixture runs.
//!
//! A host that scans each new program spends seconds on every process created from a
//! freshly written copy. One copy of the binary is staged under the system's temporary
//! folder, named by its content digest, and every fixture path is a hard link to it, so
//! that cost is paid once for the file rather than once for each fixture. A path the
//! staged copy cannot be linked to, such as one on another volume, gets a copy.

use crate::value::Sha256Digest;
use std::{
    fs, io,
    path::{Path, PathBuf},
    sync::OnceLock,
    time::{Duration, SystemTime},
};

/// The folder under the system's temporary folder holding one staged copy per binary.
const STAGING: &str = "cadrumo-test-program";
/// How long another binary's staged copy is left before staging removes it.
const STALE: Duration = Duration::from_secs(24 * 60 * 60);

/// Places the test binary at `destination`, replacing any file there.
pub(crate) fn place(destination: &Path) {
    match fs::remove_file(destination) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => panic!("{} could not be replaced: {error}", destination.display()),
    }
    if let Some(staged) = staged()
        && fs::hard_link(staged, destination).is_ok()
    {
        return;
    }
    fs::copy(std::env::current_exe().unwrap(), destination).unwrap();
}

/// The staged copy of this binary, staged on first use; none when it could not be.
fn staged() -> Option<&'static Path> {
    static STAGED: OnceLock<Option<PathBuf>> = OnceLock::new();
    STAGED.get_or_init(|| stage().ok()).as_deref()
}

fn stage() -> io::Result<PathBuf> {
    let current = std::env::current_exe()?;
    let length = fs::metadata(&current)?.len();
    let digest = Sha256Digest::of(fs::read(&current)?).to_string();
    let root = std::env::temp_dir().join(STAGING);
    let folder = root.join(&digest);
    fs::create_dir_all(&folder)?;
    let staged = folder.join(format!("program{}", std::env::consts::EXE_SUFFIX));
    // The name is the content's digest, and a copy appears under it only once complete,
    // so a file of the full length there is this binary, staged by this run or another.
    if !fs::metadata(&staged).is_ok_and(|staged| staged.is_file() && staged.len() == length) {
        let partial = folder.join(format!("program-{}.partial", std::process::id()));
        // A copy keeps the binary's permissions, so the staged file runs on Unix too.
        fs::copy(&current, &partial)?;
        if let Err(error) = fs::rename(&partial, &staged) {
            let _ = fs::remove_file(&partial);
            // Another run may have staged it meanwhile, and a running copy is not replaced.
            if !fs::metadata(&staged).is_ok_and(|staged| staged.len() == length) {
                return Err(error);
            }
        }
    }
    prune(&root, &digest);
    Ok(staged)
}

/// Removes the staged copies of other binaries not changed within [`STALE`]. A copy a
/// running test still uses is not removed; the next staging tries again.
fn prune(root: &Path, current: &str) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    let now = SystemTime::now();
    for entry in entries.flatten() {
        if entry.file_name() == current {
            continue;
        }
        let stale = entry
            .metadata()
            .and_then(|metadata| metadata.modified())
            .is_ok_and(|modified| now.duration_since(modified).is_ok_and(|age| age > STALE));
        if stale {
            let _ = fs::remove_dir_all(entry.path());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_placed_program_is_this_binary_and_replaces_what_was_there() {
        let directory = tempfile::tempdir().unwrap();
        let binary = fs::read(std::env::current_exe().unwrap()).unwrap();
        let first = directory.path().join("first");
        let second = directory.path().join("second");
        fs::write(&second, b"placeholder").unwrap();
        place(&first);
        place(&second);
        // Compared whole without printing either: each is the size of the binary.
        assert!(fs::read(&first).unwrap() == binary);
        assert!(fs::read(&second).unwrap() == binary);
        assert!(staged().is_some(), "the binary was staged");
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            // The staged copy and both placed paths are one file.
            assert!(fs::metadata(&first).unwrap().nlink() >= 3);
        }
    }
}
