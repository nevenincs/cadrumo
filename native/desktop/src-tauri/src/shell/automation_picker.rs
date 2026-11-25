//! One-shot OS chooser answers for the isolated WebDriver host only.
//! The actual window command still checks identity and issues ordinary file
//! tokens. No application operation, authentication or token check is bypassed.
use super::relay::{Failure, Result};
use serde::Deserialize;
use std::{
    fs,
    io::Read,
    path::{Component, Path, PathBuf},
    sync::Mutex,
};

const QUEUE: &str = "native-picker-selection.json";
const LIMIT: u64 = 8192;
static CONSUMING: Mutex<()> = Mutex::new(());

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(super) enum Kind {
    Open,
    Save,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Selection {
    kind: Kind,
    path: Option<PathBuf>,
}

fn invalid() -> Failure {
    Failure::new("invalid")
}

fn directory(path: &Path, parent: &Path) -> Result<PathBuf> {
    let metadata = fs::symlink_metadata(path).map_err(|_| invalid())?;
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        return Err(invalid());
    }
    let path = path.canonicalize().map_err(|_| invalid())?;
    if path.parent() != Some(parent) {
        return Err(invalid());
    }
    Ok(path)
}

/// `None` means no queued answer: use the real OS chooser. `Some(None)` is
/// explicit cancellation. Invalid queued answers fail closed and are consumed.
#[cfg(feature = "native-automation")]
pub(super) fn take(kind: Kind) -> Result<Option<Option<PathBuf>>> {
    let enabled = std::env::var("TAURI_WEBDRIVER_PORT")
        .ok()
        .and_then(|port| port.parse::<u16>().ok())
        .is_some_and(|port| port != 0);
    if !enabled {
        return Ok(None);
    }
    let storage = PathBuf::from(std::env::var_os("CADRUMO_STORAGE_ROOT").ok_or_else(invalid)?);
    if !storage.is_absolute() || storage.file_name().and_then(|v| v.to_str()) != Some("storage") {
        return Err(invalid());
    }
    let run = storage
        .parent()
        .ok_or_else(invalid)?
        .canonicalize()
        .map_err(|_| invalid())?;
    directory(&storage, &run)?;
    take_in(&run, kind)
}

fn take_in(run: &Path, kind: Kind) -> Result<Option<Option<PathBuf>>> {
    let _guard = CONSUMING.lock().unwrap_or_else(|error| error.into_inner());
    let temporary = directory(&run.join("temporary"), run)?;
    let queue = temporary.join(QUEUE);
    let metadata = match fs::symlink_metadata(&queue) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err(invalid()),
    };
    if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() > LIMIT {
        if !metadata.is_dir() {
            // Unlinking a bad queue entry never follows a symlink. A directory
            // is not an answer and is deliberately left untouched.
            fs::remove_file(&queue).map_err(|_| invalid())?;
        }
        return Err(invalid());
    }
    let file = fs::File::open(&queue).map_err(|_| invalid())?;
    // The harness publishes with an atomic, no-replacement hard link. Once
    // opened, remove the queue name before using its bounded contents.
    fs::remove_file(&queue).map_err(|_| invalid())?;
    let mut bytes = Vec::new();
    file.take(LIMIT + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| invalid())?;
    if bytes.len() as u64 > LIMIT {
        return Err(invalid());
    }
    let selection: Selection = serde_json::from_slice(&bytes).map_err(|_| invalid())?;
    if selection.kind != kind {
        return Err(invalid());
    }
    let Some(path) = selection.path else {
        return Ok(Some(None));
    };
    if !path.is_absolute()
        || path
            .components()
            .any(|part| matches!(part, Component::ParentDir))
    {
        return Err(invalid());
    }
    let root = directory(
        &run.join(match kind {
            Kind::Open => "fixtures",
            Kind::Save => "exports",
        }),
        run,
    )?;
    let chosen = match kind {
        Kind::Open => {
            let chosen = path.canonicalize().map_err(|_| invalid())?;
            if !chosen.starts_with(&root) || !chosen.is_file() {
                return Err(invalid());
            }
            chosen
        }
        Kind::Save => {
            // The adapter cannot replace a file: that would skip the real
            // save panel's overwrite confirmation.
            match fs::symlink_metadata(&path) {
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                _ => return Err(invalid()),
            }
            let parent = path
                .parent()
                .ok_or_else(invalid)?
                .canonicalize()
                .map_err(|_| invalid())?;
            if !parent.starts_with(&root) {
                return Err(invalid());
            }
            parent.join(path.file_name().ok_or_else(invalid)?)
        }
    };
    Ok(Some(Some(chosen)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static NEXT: AtomicUsize = AtomicUsize::new(0);

    struct Run(PathBuf);
    impl Run {
        fn new() -> Self {
            // The CMake host-test runner sets TMPDIR inside the enrolled build.
            let build = PathBuf::from(std::env::var_os("CADRUMO_CMAKE_BINARY_DIR").unwrap())
                .canonicalize()
                .unwrap();
            let temporary = PathBuf::from(std::env::var_os("TMPDIR").unwrap())
                .canonicalize()
                .unwrap();
            assert!(temporary.starts_with(build));
            let root = temporary.join(format!(
                "picker-test-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&root).unwrap();
            for name in ["temporary", "fixtures", "exports"] {
                fs::create_dir(root.join(name)).unwrap();
            }
            Self(root.canonicalize().unwrap())
        }
        fn queue(&self, value: serde_json::Value) {
            fs::write(
                self.0.join("temporary").join(QUEUE),
                serde_json::to_vec(&value).unwrap(),
            )
            .unwrap();
        }
        fn queue_path(&self) -> PathBuf {
            self.0.join("temporary").join(QUEUE)
        }
    }
    impl Drop for Run {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }

    #[test]
    fn open_selection_is_confined_and_consumed_once() {
        let run = Run::new();
        let file = run.0.join("fixtures/document.txt");
        fs::write(&file, b"synthetic").unwrap();
        run.queue(serde_json::json!({"kind": "open", "path": file}));
        assert_eq!(take_in(&run.0, Kind::Open).unwrap(), Some(Some(file)));
        assert_eq!(take_in(&run.0, Kind::Open).unwrap(), None);
    }

    #[test]
    fn save_requires_a_nonexistent_destination_within_exports() {
        let run = Run::new();
        let path = run.0.join("exports/result.pdf");
        run.queue(serde_json::json!({"kind": "save", "path": path}));
        assert_eq!(
            take_in(&run.0, Kind::Save).unwrap(),
            Some(Some(path.clone()))
        );
        assert!(!path.exists());
        fs::write(&path, b"keep").unwrap();
        run.queue(serde_json::json!({"kind": "save", "path": path}));
        assert!(take_in(&run.0, Kind::Save).is_err());
        assert_eq!(fs::read(path).unwrap(), b"keep");
        assert!(!run.queue_path().exists());
    }

    #[test]
    fn mismatched_kind_and_invalid_json_are_consumed() {
        let run = Run::new();
        run.queue(serde_json::json!({"kind": "save", "path": null}));
        assert!(take_in(&run.0, Kind::Open).is_err());
        assert_eq!(take_in(&run.0, Kind::Open).unwrap(), None);
        fs::write(run.queue_path(), b"not json").unwrap();
        assert!(take_in(&run.0, Kind::Open).is_err());
        assert_eq!(take_in(&run.0, Kind::Open).unwrap(), None);
    }

    #[test]
    fn cancellation_is_explicit_and_large_input_is_refused() {
        let run = Run::new();
        for (kind, label) in [(Kind::Open, "open"), (Kind::Save, "save")] {
            run.queue(serde_json::json!({"kind": label, "path": null}));
            assert_eq!(take_in(&run.0, kind).unwrap(), Some(None));
            assert_eq!(take_in(&run.0, kind).unwrap(), None);
        }
        fs::write(run.queue_path(), vec![b'x'; LIMIT as usize + 1]).unwrap();
        assert!(take_in(&run.0, Kind::Open).is_err());
        assert!(!run.queue_path().exists());
    }

    #[test]
    fn directory_queue_is_refused_without_recursive_removal() {
        let run = Run::new();
        fs::create_dir(run.queue_path()).unwrap();
        fs::write(run.queue_path().join("keep"), b"untouched").unwrap();
        assert!(take_in(&run.0, Kind::Open).is_err());
        assert_eq!(
            fs::read(run.queue_path().join("keep")).unwrap(),
            b"untouched"
        );
    }

    #[test]
    fn selections_outside_the_correct_root_and_relative_paths_fail_closed() {
        let run = Run::new();
        let outside = run.0.join("outside.txt");
        fs::write(&outside, b"synthetic").unwrap();
        for (kind, label, path) in [
            (Kind::Open, "open", outside.clone()),
            (Kind::Save, "save", run.0.join("outside-save.txt")),
            (Kind::Open, "open", PathBuf::from("relative.txt")),
        ] {
            run.queue(serde_json::json!({"kind": label, "path": path}));
            assert!(take_in(&run.0, kind).is_err());
            assert!(!run.queue_path().exists());
        }
    }

    #[cfg(unix)]
    #[test]
    fn symlink_escape_and_dangling_save_are_rejected() {
        use std::os::unix::fs::symlink;
        let run = Run::new();
        let outside = run.0.join("outside.txt");
        fs::write(&outside, b"synthetic").unwrap();
        let link = run.0.join("fixtures/link");
        symlink(&outside, &link).unwrap();
        run.queue(serde_json::json!({"kind": "open", "path": link}));
        assert!(take_in(&run.0, Kind::Open).is_err());
        let linked_dir = run.0.join("exports/linkdir");
        symlink(&run.0, &linked_dir).unwrap();
        run.queue(serde_json::json!({"kind": "save", "path": linked_dir.join("outside.pdf")}));
        assert!(take_in(&run.0, Kind::Save).is_err());
        let dangling = run.0.join("exports/dangling");
        symlink(run.0.join("missing"), &dangling).unwrap();
        run.queue(serde_json::json!({"kind": "save", "path": dangling}));
        assert!(take_in(&run.0, Kind::Save).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn symlink_queue_is_removed_without_reading_or_removing_its_target() {
        use std::os::unix::fs::symlink;
        let run = Run::new();
        let outside = run.0.join("untouched.txt");
        fs::write(&outside, b"untouched").unwrap();
        symlink(&outside, run.queue_path()).unwrap();
        assert!(take_in(&run.0, Kind::Open).is_err());
        assert!(fs::symlink_metadata(run.queue_path()).is_err());
        assert_eq!(fs::read(outside).unwrap(), b"untouched");
    }
}
