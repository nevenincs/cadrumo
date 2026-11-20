//! Cues that a background job of the window's profile changed. The runtime
//! pushes `RecordsChanged` when an operation of the profile settles with an
//! effect, and the host's follow of a long run says when that run moved. Each
//! is only a reason to read: the host reads the jobs' stored revisions through
//! each family's registered list read, at most one read at a time, and sends
//! the window a cue for every job whose revision rose past the last one it
//! read. Nothing is read on a timer.
//!
//! A cue names its family, the profile, the job and the job's stored
//! revision. It carries no private fact and grants nothing: the window reads
//! the job through the family's typed read and gates that read on the
//! revision. `background_tasks_revisions` answers the revisions as they stand
//! now, for a window that has just subscribed or regained focus.
//!
//! `background_tasks.schema.json` beside this module is the schema the
//! window's generated types are written from, and a test here keeps it equal
//! to these types.

use super::relay::{self, Failure, Relayed, Result, lock, protocol};
use super::settle::Serial;
use super::user_profile::{Cues, ProfileHost};
use crate::agent::person::{HeldPerson, PersonEvent};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};
use tauri::{State, ipc::Channel};
use tokio::sync::{
    Notify,
    broadcast::{self, Receiver, error::RecvError, error::TryRecvError},
};

/// How many cues wait for a slow subscriber before it misses some and is
/// sent every revision the host holds instead.
const CUE_BACKLOG: usize = 64;
/// The most jobs one ledger classification list read answers: the list's
/// own bound. A dismissed job is listed too, so its dismissal is cued.
const CLASSIFICATION_JOBS_READ: u64 = 50;

/// The kinds of background job the window is cued about: a closed list,
/// which another background operation joins by adding its family.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema))]
#[serde(rename_all = "snake_case")]
pub enum BackgroundTaskFamily {
    LedgerClassification,
}
impl BackgroundTaskFamily {
    const ALL: [Self; 1] = [Self::LedgerClassification];

    /// The registered read that lists the family's jobs with their revisions.
    fn read_definition(self) -> &'static str {
        match self {
            Self::LedgerClassification => "ledger.classify.job.list",
        }
    }

    /// The read's request for `profile`.
    fn read_payload(self, profile: &str) -> Value {
        match self {
            Self::LedgerClassification => json!({
                "profile_id": profile,
                "limit": CLASSIFICATION_JOBS_READ,
                "include_dismissed": true,
            }),
        }
    }

    /// Each job's identity and stored revision in the read's projection,
    /// which must be `profile`'s.
    fn revisions(self, projection: &Value, profile: &str) -> Result<Vec<BackgroundTaskRevision>> {
        if projection["profile_id"] != profile {
            return Err(protocol());
        }
        match self {
            Self::LedgerClassification => projection["jobs"]
                .as_array()
                .ok_or_else(protocol)?
                .iter()
                .map(|job| {
                    let job_id = job["job_id"]
                        .as_str()
                        .filter(|id| super::setup::wire::is_hex64(id))
                        .ok_or_else(protocol)?;
                    let revision = job["revision"]
                        .as_u64()
                        .filter(|revision| *revision >= 1)
                        .ok_or_else(protocol)?;
                    Ok(BackgroundTaskRevision {
                        family: self,
                        job_id: Some(job_id.to_owned()),
                        revision,
                    })
                })
                .collect(),
        }
    }
}

/// A background job of the profile changed: read it again if the revision
/// is newer than the one read last.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema))]
pub struct BackgroundTaskCue {
    pub family: BackgroundTaskFamily,
    pub profile_id: String,
    /// The job, where the family has one per record.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub job_id: Option<String>,
    /// The job's stored revision, which rises with every change to it.
    pub revision: u64,
}

/// One background job's stored revision.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema))]
pub struct BackgroundTaskRevision {
    pub family: BackgroundTaskFamily,
    /// The job, where the family has one per record.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub job_id: Option<String>,
    pub revision: u64,
}

/// The background jobs of the signed-in profile, each at its stored
/// revision, as one read found them.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema))]
pub struct BackgroundTaskRevisions {
    pub profile_id: String,
    pub tasks: Vec<BackgroundTaskRevision>,
}

/// The revision of each job the host last read, for one profile: a read
/// cues only the jobs whose revision rose past it.
#[derive(Debug, Default)]
struct Gate {
    profile: Option<String>,
    seen: BTreeMap<(BackgroundTaskFamily, Option<String>), u64>,
}
impl Gate {
    fn reset(&mut self) {
        *self = Self::default();
    }
    /// The cues for `read`: one for each job new to the gate or whose
    /// revision rose, none for an equal or older one. A read of another
    /// profile starts the gate again.
    fn advanced(&mut self, read: &BackgroundTaskRevisions) -> Vec<BackgroundTaskCue> {
        if self.profile.as_deref() != Some(read.profile_id.as_str()) {
            self.reset();
            self.profile = Some(read.profile_id.clone());
        }
        let mut cues = Vec::new();
        for task in &read.tasks {
            let key = (task.family, task.job_id.clone());
            if self
                .seen
                .get(&key)
                .is_some_and(|seen| task.revision <= *seen)
            {
                continue;
            }
            self.seen.insert(key, task.revision);
            cues.push(BackgroundTaskCue {
                family: task.family,
                profile_id: read.profile_id.clone(),
                job_id: task.job_id.clone(),
                revision: task.revision,
            });
        }
        cues
    }
    /// A cue for every job the gate holds, for a subscriber that missed some.
    fn current(&self) -> Vec<BackgroundTaskCue> {
        let Some(profile) = &self.profile else {
            return Vec::new();
        };
        self.seen
            .iter()
            .map(|((family, job_id), revision)| BackgroundTaskCue {
                family: *family,
                profile_id: profile.clone(),
                job_id: job_id.clone(),
                revision: *revision,
            })
            .collect()
    }
}

/// What a runtime event asks of the watcher.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Wake {
    /// Records of the profile may have changed, or events were missed.
    Read,
    /// The session ended: no revision read before it holds.
    Reset,
    /// No further event will come.
    End,
}
fn wake_of(event: std::result::Result<PersonEvent, RecvError>) -> Option<Wake> {
    match event {
        Ok(PersonEvent::RecordsChanged) | Err(RecvError::Lagged(_)) => Some(Wake::Read),
        Ok(PersonEvent::Retired) => Some(Wake::Reset),
        Err(RecvError::Closed) => Some(Wake::End),
        Ok(_) => None,
    }
}
/// What one wake of the watcher does, with every event already waiting
/// folded in, so a burst of changes is one read.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct Wakes {
    reset: bool,
    read: bool,
    end: bool,
}
fn coalesced(first: Wake, events: &mut Receiver<PersonEvent>) -> Wakes {
    let mut wakes = Wakes::default();
    let mut next = Some(first);
    loop {
        match next {
            Some(Wake::Read) => wakes.read = true,
            Some(Wake::Reset) => wakes.reset = true,
            Some(Wake::End) => wakes.end = true,
            None => {}
        }
        next = match events.try_recv() {
            Ok(event) => wake_of(Ok(event)),
            Err(TryRecvError::Lagged(_)) => Some(Wake::Read),
            Err(TryRecvError::Closed) => {
                wakes.end = true;
                return wakes;
            }
            Err(TryRecvError::Empty) => return wakes,
        };
    }
}

/// Reads one family's job revisions for `profile` through its registered
/// list read. The serial lock is held only while the read is submitted.
/// `events` must be subscribed before this is called.
async fn read_on(
    serial: &impl Serial,
    person: &HeldPerson,
    profile: &str,
    family: BackgroundTaskFamily,
    mut events: Receiver<PersonEvent>,
) -> Result<Vec<BackgroundTaskRevision>> {
    let definition = family.read_definition();
    let subject = relay::subject(profile);
    let operation = {
        let _serial = serial.serial().await;
        relay::submit(
            person,
            definition,
            &subject,
            family.read_payload(profile),
            false,
        )
        .await?
    };
    let relayed = Relayed {
        person,
        operation,
        definition,
        subject,
    };
    let p = tokio::time::timeout(
        relay::SETTLE_LIMIT,
        relay::follow(&mut events, &relayed, |_| false),
    )
    .await
    .map_err(|_| protocol())??;
    if p["terminal_condition"] != "succeeded" {
        return Err(Failure::new("refused"));
    }
    let document = relay::result(&relayed).await?;
    family.revisions(&document["projection"], profile)
}

/// The background-task cue channel of the window: one watcher that reads on
/// a change, and the window's subscriptions to the cues it sends.
pub struct BackgroundTasks {
    profile: Arc<ProfileHost>,
    gate: Mutex<Gate>,
    cues: broadcast::Sender<BackgroundTaskCue>,
    wake: Arc<Notify>,
    observers: Cues,
    watcher: Mutex<Option<tauri::async_runtime::JoinHandle<()>>>,
}
impl BackgroundTasks {
    pub fn new(profile: Arc<ProfileHost>) -> Self {
        Self {
            profile,
            gate: Mutex::default(),
            cues: broadcast::channel(CUE_BACKLOG).0,
            wake: Arc::new(Notify::new()),
            observers: Cues::default(),
            watcher: Mutex::new(None),
        }
    }
    pub fn close(&self) {
        self.observers.end();
        if let Some(watcher) = lock(&self.watcher).take() {
            watcher.abort();
        }
        lock(&self.gate).reset();
    }
    /// A background job of the window's profile may have changed: the
    /// watcher reads once, however often this is called meanwhile.
    pub(super) fn changed(&self) {
        self.wake.notify_one();
    }
    /// Every family's job revisions for the signed-in profile, read now.
    async fn read(&self) -> Result<BackgroundTaskRevisions> {
        let person = self.profile.person(None).await?;
        let profile = relay::profile_of(&person).await?;
        let mut tasks = Vec::new();
        for family in BackgroundTaskFamily::ALL {
            let events = self.profile.sign_in().person_events();
            tasks.extend(read_on(self.profile.as_ref(), &person, &profile, family, events).await?);
        }
        Ok(BackgroundTaskRevisions {
            profile_id: profile,
            tasks,
        })
    }
    /// Cues every subscriber about each job of `read` whose revision rose.
    fn publish(&self, read: &BackgroundTaskRevisions) {
        let cues = lock(&self.gate).advanced(read);
        for cue in cues {
            // No subscriber now: the next one reads the revisions on subscribing.
            let _ = self.cues.send(cue);
        }
    }
    /// A cue for every job whose revision the host read.
    fn held(&self) -> Vec<BackgroundTaskCue> {
        lock(&self.gate).current()
    }
    /// Starts the one watcher, once, unless the host has closed.
    fn watch(self: &Arc<Self>) {
        let mut watcher = lock(&self.watcher);
        if watcher.is_some() || self.profile.is_closed() {
            return;
        }
        let tasks = Arc::downgrade(self);
        let wake = self.wake.clone();
        let mut events = self.profile.sign_in().person_events();
        *watcher = Some(tauri::async_runtime::spawn(async move {
            loop {
                let woken = tokio::select! {
                    () = wake.notified() => Wake::Read,
                    event = events.recv() => match wake_of(event) {
                        Some(woken) => woken,
                        None => continue,
                    },
                };
                let Some(tasks) = tasks.upgrade() else {
                    return;
                };
                let wakes = coalesced(woken, &mut events);
                if wakes.end {
                    return;
                }
                if wakes.reset {
                    lock(&tasks.gate).reset();
                }
                // Nobody listens: a window reads the revisions when it subscribes.
                // A read the session cannot answer now waits for the next change.
                if wakes.read
                    && tasks.cues.receiver_count() > 0
                    && let Ok(read) = tasks.read().await
                {
                    tasks.publish(&read);
                }
            }
        }));
    }
}

/// Sends the window a typed cue each time a background job of its profile
/// changes, until it unobserves. Read the revisions on subscribing: a change
/// before this call is not cued.
#[tauri::command]
fn background_tasks_observe(
    tasks: State<'_, Arc<BackgroundTasks>>,
    updates: Channel<BackgroundTaskCue>,
) -> u32 {
    let host = tasks.inner().clone();
    host.watch();
    let mut cues = host.cues.subscribe();
    let gate = Arc::downgrade(&host);
    host.observers
        .observe(host.profile.is_closed(), updates, |updates| async move {
            loop {
                let sent = match cues.recv().await {
                    Ok(cue) => vec![cue],
                    // Missed cues are made good with every revision held.
                    Err(RecvError::Lagged(_)) => match gate.upgrade() {
                        Some(host) => host.held(),
                        None => break,
                    },
                    Err(RecvError::Closed) => break,
                };
                if sent.into_iter().any(|cue| updates.send(cue).is_err()) {
                    break;
                }
            }
        })
}

/// Ends the cue `subscription`.
#[tauri::command]
fn background_tasks_unobserve(tasks: State<'_, Arc<BackgroundTasks>>, subscription: u32) {
    tasks.observers.unobserve(subscription);
}

/// The stored revision of every background job of the signed-in profile,
/// read now. Every subscriber is cued about a job this read finds newer.
#[tauri::command]
async fn background_tasks_revisions(
    tasks: State<'_, Arc<BackgroundTasks>>,
) -> Result<BackgroundTaskRevisions> {
    let read = tasks.read().await?;
    tasks.publish(&read);
    Ok(read)
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        background_tasks_observe,
        background_tasks_unobserve,
        background_tasks_revisions
    ]
}

#[cfg(test)]
mod tests;
