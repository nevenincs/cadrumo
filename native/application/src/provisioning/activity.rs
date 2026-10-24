//! The per-item writer lock and the activity record that survives a crash.
//!
//! One writer changes an item at a time. It holds the operating system's lock on
//! `<item>.lock` for as long as it works, never waits for it (a held lock means someone is
//! changing the item now), and keeps the lock file in place, because unlinking it would
//! let two writers lock two files. Beside the lock it keeps `<item>.activity.json`, the
//! step it has reached, replaced atomically at each step and removed when it finishes.
//! The lock dies with its process; the record does not. So a record with a live lock is
//! a running setup, and a record whose lock nobody holds is a setup that was interrupted:
//! the item reads `failed interrupted` and offers Resume. A finished setup that did not
//! end ready leaves `<item>.failure.json` with its category instead.
//!
//! A status read takes the lock shared for an instant to learn whether a writer holds
//! it, and reads the record only after: a record read while the shared lock is held was
//! left by a writer that is gone, because no writer can begin or finish meanwhile. A
//! writer starting in that instant is refused as busy rather than queued.

use super::{
    failure::FailureCategory,
    items::ItemId,
    state::{Activity, SetupStep},
};
use crate::{component::WriterLock, error::Error, filesystem};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, File},
    path::PathBuf,
};

const RECORD_BYTES_LIMIT: u64 = 64 * 1024;

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ActivityRecord {
    schema: u32,
    item: ItemId,
    step: SetupStep,
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct FailureRecord {
    schema: u32,
    item: ItemId,
    category: FailureCategory,
}

/// The lock files and records of every item, under one folder.
pub struct ActivityStore {
    root: PathBuf,
}

impl ActivityStore {
    pub fn new(root: PathBuf) -> Result<Self, Error> {
        filesystem::absolute_root(&root)?;
        Ok(Self { root })
    }

    fn path(&self, item: ItemId, kind: &str) -> PathBuf {
        self.root.join(format!("{item}.{kind}"))
    }

    /// The item's lock file when it exists; a status read never creates one.
    fn existing_lock_file(&self, item: ItemId) -> Result<Option<File>, Error> {
        filesystem::refuse_links(&self.root)?;
        let path = self.path(item, "lock");
        filesystem::refuse_links(&path)?;
        match File::options().read(true).write(true).open(path) {
            Ok(file) => Ok(Some(file)),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(error.into()),
        }
    }

    /// The item's activity record: `None` when there is none, `Some(None)` when one is
    /// there but cannot be read as this item's.
    fn record(&self, item: ItemId) -> Result<Option<Option<ActivityRecord>>, Error> {
        match filesystem::bounded_bytes(&self.path(item, "activity.json"), RECORD_BYTES_LIMIT) {
            Ok(bytes) => Ok(Some(
                serde_json::from_slice::<ActivityRecord>(&bytes)
                    .ok()
                    .filter(|record| record.schema == 1 && record.item == item),
            )),
            Err(Error::Io(error)) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(error),
        }
    }

    fn lock_file(&self, item: ItemId) -> Result<File, Error> {
        filesystem::refuse_links(&self.root)?;
        fs::create_dir_all(&self.root)?;
        let path = self.path(item, "lock");
        filesystem::refuse_links(&path)?;
        Ok(File::options()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path)?)
    }

    /// Takes the item's writer lock without waiting and records the first step. `Busy`
    /// when another writer holds the lock.
    pub fn begin(&self, item: ItemId, step: SetupStep) -> Result<ItemWriter<'_>, Error> {
        let lock = self.lock_file(item)?;
        lock.try_lock().map_err(|error| match error {
            fs::TryLockError::WouldBlock => Error::Busy,
            fs::TryLockError::Error(error) => Error::Io(error),
        })?;
        let writer = ItemWriter {
            store: self,
            item,
            _lock: WriterLock(lock),
        };
        writer.step(step)?;
        Ok(writer)
    }

    /// What a setup is doing to the item right now, judged by its lock and then its record.
    pub fn activity(&self, item: ItemId) -> Result<Activity, Error> {
        self.observe(item, &mut || {})
    }

    /// [`Self::activity`], running `between` after the lock is judged and before the record
    /// is read, which is where a writer may finish concurrently.
    fn observe(&self, item: ItemId, between: &mut dyn FnMut()) -> Result<Activity, Error> {
        let lock = match self.existing_lock_file(item)? {
            Some(lock) => lock,
            // No writer has begun here unless one is beginning now, and its record says so.
            None if self.record(item)?.is_none() => return Ok(Activity::Idle),
            None => self.lock_file(item)?,
        };
        match lock.try_lock_shared() {
            Ok(()) => {
                between();
                let record = self.record(item);
                lock.unlock()?;
                Ok(match record? {
                    Some(_) => Activity::Interrupted,
                    None => Activity::Idle,
                })
            }
            Err(fs::TryLockError::WouldBlock) => {
                between();
                Ok(Activity::Running(
                    self.record(item)?
                        .flatten()
                        .map_or(SetupStep::Plan, |record| record.step),
                ))
            }
            Err(fs::TryLockError::Error(error)) => Err(Error::Io(error)),
        }
    }

    /// The category the item's last finished setup recorded when it did not end ready.
    pub fn last_failure(&self, item: ItemId) -> Option<FailureCategory> {
        let bytes =
            filesystem::bounded_bytes(&self.path(item, "failure.json"), RECORD_BYTES_LIMIT).ok()?;
        serde_json::from_slice::<FailureRecord>(&bytes)
            .ok()
            .filter(|record| record.schema == 1 && record.item == item)
            .map(|record| record.category)
    }

    fn remove(&self, item: ItemId, kind: &str) -> Result<(), Error> {
        match fs::remove_file(self.path(item, kind)) {
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error.into()),
            _ => Ok(()),
        }
    }
}

/// The one writer of an item. Dropping it without finishing leaves the activity record
/// behind, which is how a crash reads: the item is then interrupted.
pub struct ItemWriter<'a> {
    store: &'a ActivityStore,
    item: ItemId,
    _lock: WriterLock,
}

impl ItemWriter<'_> {
    pub fn item(&self) -> ItemId {
        self.item
    }

    /// Records the step the setup has reached.
    pub fn step(&self, step: SetupStep) -> Result<(), Error> {
        filesystem::replace_json(
            &self.store.path(self.item, "activity.json"),
            &ActivityRecord {
                schema: 1,
                item: self.item,
                step,
            },
        )
    }

    /// The setup left the item ready: no failure and no activity remain.
    pub fn finished(self) -> Result<(), Error> {
        self.store.remove(self.item, "failure.json")?;
        self.store.remove(self.item, "activity.json")
    }

    /// The setup ended without the item ready, for `category`.
    pub fn failed(self, category: FailureCategory) -> Result<(), Error> {
        filesystem::replace_json(
            &self.store.path(self.item, "failure.json"),
            &FailureRecord {
                schema: 1,
                item: self.item,
                category,
            },
        )?;
        self.store.remove(self.item, "activity.json")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader};

    fn store() -> (tempfile::TempDir, ActivityStore) {
        let directory = tempfile::tempdir().unwrap();
        let store = ActivityStore::new(directory.path().join("activity")).unwrap();
        (directory, store)
    }

    #[test]
    fn one_writer_at_a_time_and_its_steps_read_as_running() {
        let (_directory, store) = store();
        assert_eq!(store.activity(ItemId::Browser).unwrap(), Activity::Idle);
        let writer = store.begin(ItemId::Browser, SetupStep::Plan).unwrap();
        assert!(matches!(
            store.begin(ItemId::Browser, SetupStep::Plan),
            Err(Error::Busy)
        ));
        let other = store.begin(ItemId::LocalAi, SetupStep::Preflight).unwrap();
        writer.step(SetupStep::Download).unwrap();
        assert_eq!(
            store.activity(ItemId::Browser).unwrap(),
            Activity::Running(SetupStep::Download)
        );
        writer.step(SetupStep::Verify).unwrap();
        assert_eq!(
            store.activity(ItemId::Browser).unwrap(),
            Activity::Running(SetupStep::Verify)
        );
        assert!(
            matches!(
                store.begin(ItemId::Browser, SetupStep::Plan),
                Err(Error::Busy)
            ),
            "a status read does not release the writer's lock"
        );
        writer.finished().unwrap();
        assert_eq!(store.activity(ItemId::Browser).unwrap(), Activity::Idle);
        assert_eq!(store.last_failure(ItemId::Browser), None);
        other.failed(FailureCategory::DiskFull).unwrap();
        assert_eq!(store.activity(ItemId::LocalAi).unwrap(), Activity::Idle);
        assert_eq!(
            store.last_failure(ItemId::LocalAi),
            Some(FailureCategory::DiskFull)
        );
        store
            .begin(ItemId::LocalAi, SetupStep::Plan)
            .unwrap()
            .finished()
            .unwrap();
        assert_eq!(
            store.last_failure(ItemId::LocalAi),
            None,
            "a ready setup clears the failure"
        );
    }

    #[test]
    fn a_writer_finishing_during_a_status_read_never_reads_as_interrupted() {
        let (_directory, store) = store();
        let mut writer = Some(store.begin(ItemId::Browser, SetupStep::Verify).unwrap());
        let read = store
            .observe(ItemId::Browser, &mut || {
                writer.take().unwrap().finished().unwrap();
            })
            .unwrap();
        assert!(writer.is_none());
        assert_ne!(read, Activity::Interrupted);
        assert_eq!(store.activity(ItemId::Browser).unwrap(), Activity::Idle);

        let mut writer = Some(store.begin(ItemId::LocalAi, SetupStep::Download).unwrap());
        let read = store
            .observe(ItemId::LocalAi, &mut || {
                writer
                    .take()
                    .unwrap()
                    .failed(FailureCategory::Offline)
                    .unwrap();
            })
            .unwrap();
        assert_ne!(read, Activity::Interrupted);
        assert_eq!(store.activity(ItemId::LocalAi).unwrap(), Activity::Idle);
    }

    #[test]
    fn a_status_read_on_a_clean_root_creates_nothing() {
        let (directory, store) = store();
        assert_eq!(store.activity(ItemId::Browser).unwrap(), Activity::Idle);
        assert!(!directory.path().join("activity").exists());
    }

    #[test]
    fn an_unfinished_record_without_a_live_lock_is_interrupted() {
        let (_directory, store) = store();
        let writer = store.begin(ItemId::LocalAi, SetupStep::Download).unwrap();
        drop(writer);
        assert_eq!(
            store.activity(ItemId::LocalAi).unwrap(),
            Activity::Interrupted
        );
        let resumed = store.begin(ItemId::LocalAi, SetupStep::Download).unwrap();
        assert_eq!(
            store.activity(ItemId::LocalAi).unwrap(),
            Activity::Running(SetupStep::Download)
        );
        resumed.finished().unwrap();
        assert_eq!(store.activity(ItemId::LocalAi).unwrap(), Activity::Idle);
    }

    const CHILD_ROOT: &str = "CADRUMO_ACTIVITY_CHILD_ROOT";
    const READY: &str = "activity-writer-ready";

    #[test]
    fn a_killed_writer_reads_as_interrupted_and_its_item_can_be_resumed() {
        if let Some(root) = std::env::var_os(CHILD_ROOT) {
            let store = ActivityStore::new(PathBuf::from(root)).unwrap();
            let _writer = store.begin(ItemId::Browser, SetupStep::Download).unwrap();
            // The harness prefixes the test name on the current line; start a fresh one.
            println!(
                "
{READY}"
            );
            loop {
                std::thread::park();
            }
        }
        let (directory, store) = store();
        let mut command = std::process::Command::new(std::env::current_exe().unwrap());
        command
            .args([
                "--exact",
                "provisioning::activity::tests::a_killed_writer_reads_as_interrupted_and_its_item_can_be_resumed",
                "--nocapture",
                "--test-threads=1",
            ])
            .env(CHILD_ROOT, directory.path().join("activity"))
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            // CREATE_NO_WINDOW: the child never opens a console of its own.
            command.creation_flags(0x0800_0000);
        }
        let mut child = command.spawn().unwrap();
        let stdout = child.stdout.take().unwrap();
        let ready = BufReader::new(stdout)
            .lines()
            .map_while(Result::ok)
            .any(|line| line.trim_end().ends_with(READY));
        let held = store.activity(ItemId::Browser);
        child.kill().unwrap();
        child.wait().unwrap();
        assert!(ready, "the child never took the writer lock");
        assert_eq!(held.unwrap(), Activity::Running(SetupStep::Download));
        assert_eq!(
            store.activity(ItemId::Browser).unwrap(),
            Activity::Interrupted
        );
        store
            .begin(ItemId::Browser, SetupStep::Download)
            .unwrap()
            .finished()
            .unwrap();
        assert_eq!(store.activity(ItemId::Browser).unwrap(), Activity::Idle);
    }
}
