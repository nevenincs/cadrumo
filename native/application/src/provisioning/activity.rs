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
//!
//! A setup also publishes what another engine needs to follow it. Its record names the
//! setup (a run id and the digest of the plan the person approved) and carries every step
//! reached so far, the latest byte figure, the retry being waited out and whether the
//! setup waits for the local AI server. Before it removes the record it writes
//! `<item>.ended.json`: how the setup ended for this item, which is the run's own result
//! once the run stopped at this item or before it. A follower reads the record whenever the
//! folder changes and learns that the writer is gone by taking the lock shared once it is
//! released ([`wait_released`]); a writer that dies writes nothing, and its item then
//! reads interrupted.

use super::{
    failure::FailureCategory,
    items::ItemId,
    state::{Activity, SetupStep},
};
use crate::{component::WriterLock, error::Error, filesystem, value::Sha256Digest};
use serde::{Deserialize, Serialize};
use std::{
    cell::RefCell,
    fs::{self, File},
    path::{Path, PathBuf},
    time::Duration,
};

const RECORD_BYTES_LIMIT: u64 = 64 * 1024;

/// One setup run: its id, unique to the run, and the digest of the plan it was approved
/// under.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct RunMark {
    pub id: String,
    pub plan_digest: Sha256Digest,
}

/// Bytes an item holds out of its whole known download.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Bytes {
    pub completed: u64,
    pub total: u64,
}

/// A transient failure the setup waits out before its next attempt.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Retry {
    pub attempt: u32,
    pub delay_ms: u64,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ActivityRecord {
    schema: u32,
    item: ItemId,
    step: SetupStep,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    run: Option<RunMark>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    steps: Vec<SetupStep>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    progress: Option<Bytes>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    retry: Option<Retry>,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    waiting_for_server: bool,
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct FailureRecord {
    schema: u32,
    item: ItemId,
    category: FailureCategory,
}

/// How a setup run ended for one of its items.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EndedOutcome {
    /// The item was set up.
    Completed,
    /// The run stopped at `stopped_at` for its failure.
    Failed,
    /// The run was asked to stop and stopped at `stopped_at`.
    Cancelled,
    /// A part of the item was held by another writer, so the run stopped at `stopped_at`.
    Busy,
}

/// The record a run leaves for an item when it is done with it.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Ended {
    schema: u32,
    item: ItemId,
    pub run: String,
    pub outcome: EndedOutcome,
    /// The item the run stopped at, when it did not complete this one.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub stopped_at: Option<ItemId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub failure: Option<FailureCategory>,
}

/// Why a run stopped, as every item it had not reached records it.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RunStop {
    pub outcome: EndedOutcome,
    pub item: ItemId,
    pub failure: Option<FailureCategory>,
}

/// What a running setup has published about one item.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Published {
    pub run: RunMark,
    /// Every step reached so far, in order, a repeated step once per arrival.
    pub steps: Vec<SetupStep>,
    pub progress: Option<Bytes>,
    pub retry: Option<Retry>,
    pub waiting_for_server: bool,
}

/// What a follower finds when it looks at an item.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Watched {
    /// A live writer holds the item; `None` when it publishes no run, as a removal.
    Running(Option<Published>),
    Interrupted,
    Idle,
}

/// Blocks until no writer holds the lock at `lock`, which a writer that ends or dies
/// releases; returns at once when there is no lock file or it cannot be opened.
pub fn wait_released(lock: &Path) {
    if filesystem::refuse_links(lock).is_err() {
        return;
    }
    if let Ok(file) = File::options().read(true).write(true).open(lock) {
        // The shared lock is taken only to learn that the writer let go; it is released
        // when the file closes.
        let _ = file.lock_shared();
    }
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

    /// The folder every item's lock and records live in, which a follower watches.
    pub fn root(&self) -> &Path {
        &self.root
    }

    /// The item's lock file, which [`wait_released`] waits on.
    pub fn lock_path(&self, item: ItemId) -> PathBuf {
        self.path(item, "lock")
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

    fn take(&self, item: ItemId) -> Result<WriterLock, Error> {
        let lock = self.lock_file(item)?;
        lock.try_lock().map_err(|error| match error {
            fs::TryLockError::WouldBlock => Error::Busy,
            fs::TryLockError::Error(error) => Error::Io(error),
        })?;
        Ok(WriterLock(lock))
    }

    /// Takes the item's writer lock without waiting and records the first step. `Busy`
    /// when another writer holds the lock.
    pub fn begin(&self, item: ItemId, step: SetupStep) -> Result<ItemWriter<'_>, Error> {
        self.begin_observed(item, step, &unobserved)
    }

    /// [`Self::begin`], telling `observer` each step once it is recorded, the first included.
    pub fn begin_observed<'a>(
        &'a self,
        item: ItemId,
        step: SetupStep,
        observer: &'a dyn Fn(SetupStep),
    ) -> Result<ItemWriter<'a>, Error> {
        let writer = ItemWriter::new(self, item, self.take(item)?, None, observer);
        writer.step(step)?;
        Ok(writer)
    }

    /// Takes the item's writer lock for `run` without waiting, before the run reaches the
    /// item, and records it as planned without telling `observer`; the run's first step
    /// for the item is the first the observer hears. `Busy` when another writer holds it.
    pub fn queue<'a>(
        &'a self,
        item: ItemId,
        run: &RunMark,
        observer: &'a dyn Fn(SetupStep),
    ) -> Result<ItemWriter<'a>, Error> {
        let writer = ItemWriter::new(self, item, self.take(item)?, Some(run.clone()), observer);
        writer.publish()?;
        Ok(writer)
    }

    /// What a setup is doing to the item right now, judged by its lock and then its record.
    pub fn activity(&self, item: ItemId) -> Result<Activity, Error> {
        self.observe(item, &mut || {}).map(|(activity, _)| activity)
    }

    /// What a follower of the item can read: the record the live writer published.
    pub fn watch(&self, item: ItemId) -> Result<Watched, Error> {
        Ok(match self.observe(item, &mut || {})? {
            (Activity::Running(_), record) => {
                Watched::Running(record.and_then(ActivityRecord::published))
            }
            (Activity::Interrupted, _) => Watched::Interrupted,
            (Activity::Idle, _) => Watched::Idle,
        })
    }

    /// What a setup is doing to the item, judged by its lock and then its record, with a
    /// live writer's record when it can be read. Runs `between` after the lock is judged
    /// and before the record is read, which is where a writer may finish concurrently.
    fn observe(
        &self,
        item: ItemId,
        between: &mut dyn FnMut(),
    ) -> Result<(Activity, Option<ActivityRecord>), Error> {
        let lock = match self.existing_lock_file(item)? {
            Some(lock) => lock,
            // No writer has begun here unless one is beginning now, and its record says so.
            None if self.record(item)?.is_none() => return Ok((Activity::Idle, None)),
            None => self.lock_file(item)?,
        };
        match lock.try_lock_shared() {
            Ok(()) => {
                between();
                let record = self.record(item);
                lock.unlock()?;
                Ok(match record? {
                    Some(_) => (Activity::Interrupted, None),
                    None => (Activity::Idle, None),
                })
            }
            Err(fs::TryLockError::WouldBlock) => {
                between();
                let record = self.record(item)?.flatten();
                let step = record
                    .as_ref()
                    .map_or(SetupStep::Plan, |record| record.step);
                Ok((Activity::Running(step), record))
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

    /// How the last setup run that was done with the item ended for it.
    pub fn ended(&self, item: ItemId) -> Option<Ended> {
        let bytes =
            filesystem::bounded_bytes(&self.path(item, "ended.json"), RECORD_BYTES_LIMIT).ok()?;
        serde_json::from_slice::<Ended>(&bytes)
            .ok()
            .filter(|record| record.schema == 1 && record.item == item)
    }

    fn remove(&self, item: ItemId, kind: &str) -> Result<(), Error> {
        match fs::remove_file(self.path(item, kind)) {
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error.into()),
            _ => Ok(()),
        }
    }
}

impl ActivityRecord {
    fn published(self) -> Option<Published> {
        Some(Published {
            run: self.run?,
            steps: self.steps,
            progress: self.progress,
            retry: self.retry,
            waiting_for_server: self.waiting_for_server,
        })
    }
}

fn unobserved(_: SetupStep) {}

/// The one writer of an item. Dropping it without finishing leaves the activity record
/// behind, which is how a crash reads: the item is then interrupted.
pub struct ItemWriter<'a> {
    store: &'a ActivityStore,
    item: ItemId,
    _lock: WriterLock,
    observer: &'a dyn Fn(SetupStep),
    record: RefCell<ActivityRecord>,
}

impl<'a> ItemWriter<'a> {
    fn new(
        store: &'a ActivityStore,
        item: ItemId,
        lock: WriterLock,
        run: Option<RunMark>,
        observer: &'a dyn Fn(SetupStep),
    ) -> Self {
        Self {
            store,
            item,
            _lock: lock,
            observer,
            record: RefCell::new(ActivityRecord {
                schema: 1,
                item,
                step: SetupStep::Plan,
                run,
                steps: Vec::new(),
                progress: None,
                retry: None,
                waiting_for_server: false,
            }),
        }
    }
}

impl ItemWriter<'_> {
    pub fn item(&self) -> ItemId {
        self.item
    }

    fn publish(&self) -> Result<(), Error> {
        filesystem::replace_json(
            &self.store.path(self.item, "activity.json"),
            &*self.record.borrow(),
        )
    }

    /// Records the step the setup has reached.
    pub fn step(&self, step: SetupStep) -> Result<(), Error> {
        {
            let mut record = self.record.borrow_mut();
            record.step = step;
            if record.steps.last() != Some(&step) {
                record.steps.push(step);
            }
            record.retry = None;
            record.waiting_for_server = false;
        }
        self.publish()?;
        (self.observer)(step);
        Ok(())
    }

    /// Publishes the bytes the item holds so far.
    pub fn progress(&self, completed: u64, total: u64) -> Result<(), Error> {
        {
            let mut record = self.record.borrow_mut();
            record.progress = Some(Bytes { completed, total });
            record.retry = None;
        }
        self.publish()
    }

    /// Publishes the retry the setup is about to wait out.
    pub fn retrying(&self, attempt: u32, delay: Duration) -> Result<(), Error> {
        self.record.borrow_mut().retry = Some(Retry {
            attempt,
            delay_ms: u64::try_from(delay.as_millis()).unwrap_or(u64::MAX),
        });
        self.publish()
    }

    /// Publishes that the setup waits for the local AI server.
    pub fn waiting_for_server(&self) -> Result<(), Error> {
        self.record.borrow_mut().waiting_for_server = true;
        self.publish()
    }

    /// Leaves the run's end for the item before its record goes, so a follower that finds
    /// the record gone finds the end.
    fn leave_ended(&self, stop: Option<RunStop>) -> Result<(), Error> {
        let Some(run) = self.record.borrow().run.as_ref().map(|run| run.id.clone()) else {
            // A writer of no run, as a removal, leaves no end; an earlier run's end no
            // longer says how the item was last changed.
            return self.store.remove(self.item, "ended.json");
        };
        filesystem::replace_json(
            &self.store.path(self.item, "ended.json"),
            &Ended {
                schema: 1,
                item: self.item,
                run,
                outcome: stop.map_or(EndedOutcome::Completed, |stop| stop.outcome),
                stopped_at: stop.map(|stop| stop.item),
                failure: stop.and_then(|stop| stop.failure),
            },
        )
    }

    /// The setup left the item ready: no failure and no activity remain.
    pub fn finished(self) -> Result<(), Error> {
        self.leave_ended(None)?;
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
        let outcome = if category == FailureCategory::Cancelled {
            EndedOutcome::Cancelled
        } else {
            EndedOutcome::Failed
        };
        self.leave_ended(Some(RunStop {
            outcome,
            item: self.item,
            failure: Some(category),
        }))?;
        self.store.remove(self.item, "activity.json")
    }

    /// A part of the item was held by another writer: nothing failed, and no activity
    /// remains.
    pub fn held(self) -> Result<(), Error> {
        self.leave_ended(Some(RunStop {
            outcome: EndedOutcome::Busy,
            item: self.item,
            failure: None,
        }))?;
        self.store.remove(self.item, "failure.json")?;
        self.store.remove(self.item, "activity.json")
    }

    /// The run stopped before it reached this item: the item is left as it was, and its
    /// end names where the run stopped.
    pub fn not_reached(self, stop: RunStop) -> Result<(), Error> {
        self.leave_ended(Some(stop))?;
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
    fn an_observed_writer_reports_each_step_once_it_is_recorded() {
        let (_directory, store) = store();
        let seen = std::cell::RefCell::new(Vec::new());
        let observer = |step| {
            assert_eq!(
                store.activity(ItemId::Browser).unwrap(),
                Activity::Running(step),
                "a step is reported after its record"
            );
            seen.borrow_mut().push(step);
        };
        let writer = store
            .begin_observed(ItemId::Browser, SetupStep::Download, &observer)
            .unwrap();
        writer.step(SetupStep::Install).unwrap();
        writer.finished().unwrap();
        assert_eq!(*seen.borrow(), [SetupStep::Download, SetupStep::Install]);
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
            .unwrap()
            .0;
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
            .unwrap()
            .0;
        assert_ne!(read, Activity::Interrupted);
        assert_eq!(store.activity(ItemId::LocalAi).unwrap(), Activity::Idle);
    }

    #[test]
    fn a_status_read_on_a_clean_root_creates_nothing() {
        let (directory, store) = store();
        assert_eq!(store.activity(ItemId::Browser).unwrap(), Activity::Idle);
        assert!(!directory.path().join("activity").exists());
    }

    fn run(id: &str) -> RunMark {
        RunMark {
            id: id.into(),
            plan_digest: Sha256Digest::of(id.as_bytes()),
        }
    }

    #[test]
    fn a_queued_run_publishes_what_a_follower_reads_and_leaves_its_end() {
        let (_directory, store) = store();
        let heard = RefCell::new(Vec::new());
        let observer = |step| heard.borrow_mut().push(step);
        let browser = store
            .queue(ItemId::Browser, &run("one"), &observer)
            .unwrap();
        let local_ai = store
            .queue(ItemId::LocalAi, &run("one"), &observer)
            .unwrap();
        assert!(matches!(
            store.queue(ItemId::Browser, &run("two"), &observer),
            Err(Error::Busy)
        ));
        let queued = |item| match store.watch(item).unwrap() {
            Watched::Running(Some(published)) => published,
            other => panic!("{other:?}"),
        };
        assert_eq!(
            store.activity(ItemId::LocalAi).unwrap(),
            Activity::Running(SetupStep::Plan),
            "a queued item reads as running from the run's start"
        );
        assert_eq!(queued(ItemId::LocalAi).steps, []);
        assert!(heard.borrow().is_empty(), "queueing reports no step");

        browser.step(SetupStep::Download).unwrap();
        browser.progress(10, 100).unwrap();
        browser.retrying(2, Duration::from_millis(1500)).unwrap();
        let published = queued(ItemId::Browser);
        assert_eq!(published.run, run("one"));
        assert_eq!(published.steps, [SetupStep::Download]);
        assert_eq!(
            published.progress,
            Some(Bytes {
                completed: 10,
                total: 100
            })
        );
        assert_eq!(
            published.retry,
            Some(Retry {
                attempt: 2,
                delay_ms: 1500
            })
        );
        browser.step(SetupStep::Install).unwrap();
        browser.step(SetupStep::Download).unwrap();
        let published = queued(ItemId::Browser);
        assert_eq!(
            published.steps,
            [SetupStep::Download, SetupStep::Install, SetupStep::Download]
        );
        assert_eq!(published.retry, None, "a new step ends the retry");
        assert_eq!(*heard.borrow(), published.steps);

        browser.failed(FailureCategory::Offline).unwrap();
        assert_eq!(store.watch(ItemId::Browser).unwrap(), Watched::Idle);
        let ended = store.ended(ItemId::Browser).unwrap();
        assert_eq!(
            (
                ended.run.as_str(),
                ended.outcome,
                ended.stopped_at,
                ended.failure
            ),
            (
                "one",
                EndedOutcome::Failed,
                Some(ItemId::Browser),
                Some(FailureCategory::Offline)
            )
        );
        local_ai
            .not_reached(RunStop {
                outcome: EndedOutcome::Failed,
                item: ItemId::Browser,
                failure: Some(FailureCategory::Offline),
            })
            .unwrap();
        assert_eq!(store.activity(ItemId::LocalAi).unwrap(), Activity::Idle);
        assert_eq!(
            store.last_failure(ItemId::LocalAi),
            None,
            "an item the run never reached keeps its own state"
        );
        let ended = store.ended(ItemId::LocalAi).unwrap();
        assert_eq!(
            (ended.outcome, ended.stopped_at),
            (EndedOutcome::Failed, Some(ItemId::Browser))
        );

        let removal = store.begin(ItemId::Browser, SetupStep::Cleanup).unwrap();
        assert_eq!(
            store.watch(ItemId::Browser).unwrap(),
            Watched::Running(None),
            "a removal publishes no run to follow"
        );
        removal.finished().unwrap();
        assert_eq!(
            store.ended(ItemId::Browser),
            None,
            "a removal leaves no earlier run's end behind"
        );
    }

    #[test]
    fn a_release_wait_returns_once_the_writer_lets_go() {
        let (_directory, store) = store();
        wait_released(&store.lock_path(ItemId::Browser));
        let writer = store.begin(ItemId::Browser, SetupStep::Download).unwrap();
        let (released, heard) = std::sync::mpsc::channel();
        let lock = store.lock_path(ItemId::Browser);
        let waiting = std::thread::spawn(move || {
            wait_released(&lock);
            released.send(()).unwrap();
        });
        assert!(
            heard.try_recv().is_err(),
            "the wait holds while the writer does"
        );
        writer.finished().unwrap();
        heard.recv().unwrap();
        waiting.join().unwrap();
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
