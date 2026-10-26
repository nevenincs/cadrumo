//! The component engine: status, plan, setup, verify, cancel and remove for every setup
//! item, composed from the item modules. The `components` role runs it for the command
//! line, the TUI and the MCP service, and the desktop links it in process; both see the
//! same rows, plans and digests.
//!
//! A setup reads every item's quick state, plans the items the request names, or by
//! default every item whose row offers the person an action, and checks the planned
//! items' hosts and the storage volume's free space before it asks for anything. The
//! person's approval binds the plan's digest: a request that already carries a digest
//! proceeds only while the plan still has it, and an approval given in answer to a review
//! is checked against a plan computed again after the answer, so a plan that changed in
//! between refuses as `plan_changed` and is never set up on an old approval. A Resume
//! after an interruption therefore needs no second review while its plan is unchanged.
//!
//! The items then run one at a time, in setup order, each under its writer lock, and the
//! setup stops at the first item that does not finish. Each step is recorded before it is
//! reported as a phase. Progress is throttled to one report per item every 500 ms and
//! only on a change of at least 1 %, with the first and the last always reported.
//!
//! A setup stops between transfer chunks when its cancellation is set, by its owner or by
//! a cancel request another process leaves beside the item's lock: the request is looked
//! for at every chunk, so no timer runs.
//!
//! A setup of an item another engine is already setting up follows that setup instead of
//! starting its own: it plans nothing, asks for no review and downloads nothing. It
//! reports a `Following` event with the digest of the plan the other setup was approved
//! under, then the other setup's steps, byte progress, retries and server wait as that
//! setup publishes them in the item's activity record, and ends with the result that setup
//! reached for the item, read from the end it leaves beside the record. When the follower
//! is cancelled it stops following and ends `Busy`; the setup it followed goes on. A run
//! takes the writer locks of all its items before the first one starts, so a follower sees
//! the whole run as running, follows each of its items in turn, and learns where the run
//! stopped from the items it never reached.
//!
//! The engine never runs the local AI server: the runtime manager runs the one server of
//! the installation on its fixed address while the program is set up. A local AI setup
//! installs the program, which waits for the manager to stop any server it runs from the
//! old version, records the program with the fixed address, and then waits, within
//! [`SERVER_WAIT`], for the manager to start the server before it pulls and checks each
//! selected model through it. Without a manager the server never comes, and the models
//! fail as `program_not_running`.
//!
//! Only an owner that admits the local AI with [`Engine::admit_local_ai`] may plan, set up
//! or remove it; the desktop host alone does, handing over the person's selection: role,
//! model name and download size, as the selected catalogue entries state them. The engine
//! names no model itself, so with an empty selection the local AI is its program alone.
//! An engine that was never admitted serves the local AI read-only: it reports and fully
//! checks the program, offers [`RecoveryAction::SetUpInDesktop`] where a set-up, update,
//! retry or resume would be offered, leaves the item out of a setup that names none, and
//! refuses a plan, setup or removal that names it.

use super::{
    activity::{
        ActivityStore, Bytes, EndedOutcome, ItemWriter, Published, Retry, RunMark, RunStop, Watched,
    },
    browser::{self, BrowserLayout, DriverManifest, LaunchContext},
    connection::Network,
    failure::FailureCategory,
    follow::{self, Changes},
    items::{Destination, ItemId, Locations, PROGRAM_PART},
    local_ai::{
        self, LocalAiError,
        hardware::Hardware,
        models::{LocalModels, ModelName, Models, Pull},
        program::{Program, START_BUDGET, Server},
    },
    network::{self, HOST_TIMEOUT, Reachability},
    pins::{ComponentPins, Platform},
    plan::{PlanEntry, SetupPlan},
    receipts::{ReceiptReading, ReceiptStore},
    state::{
        self, Activity, BlockedReason, CheckMode, ItemState, Observation, Reading, RecoveryAction,
        SetupStep, StatusRow,
    },
    transfer::{Pacing, RetryPolicy, SystemPacing, Transfer, TransferEvent},
};
use crate::{
    component::Cancellation,
    error::Error,
    filesystem,
    value::{HostName, Sha256Digest},
};
use serde::Serialize;
use std::{
    cell::RefCell,
    collections::{BTreeMap, BTreeSet},
    ffi::OsString,
    fs,
    hash::{BuildHasher, Hasher},
    net::SocketAddr,
    path::{Path, PathBuf},
    time::{Duration, Instant, SystemTime},
};

/// The shortest interval between two progress reports of one item.
pub const PROGRESS_INTERVAL: Duration = Duration::from_millis(500);

/// The longest a local AI setup waits for the manager to start the server: the manager
/// looks every second, and a start may take [`START_BUDGET`].
pub const SERVER_WAIT: Duration = START_BUDGET.saturating_add(Duration::from_secs(5));

/// The first and the longest interval between two looks for the server while waiting.
const SERVER_LOOK_FIRST: Duration = Duration::from_millis(250);
const SERVER_LOOK_LONGEST: Duration = Duration::from_secs(2);

/// What the engine reports while it works.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Event {
    /// The setup follows another engine's setup of `item`, approved under `plan_digest`,
    /// instead of setting the item up itself; reported once per item, before its steps.
    Following {
        item: ItemId,
        plan_digest: Sha256Digest,
    },
    /// `item` reached `step`; its phase code is [`SetupStep::phase_code`].
    Phase { item: ItemId, step: SetupStep },
    /// Bytes held so far out of the item's whole known download.
    Progress {
        item: ItemId,
        completed: u64,
        total: u64,
    },
    /// A transient failure is retried as `attempt` after `delay`; reported before waiting.
    Retrying {
        item: ItemId,
        attempt: u32,
        delay: Duration,
    },
    /// The local AI program is set up and the setup waits for the manager to start its
    /// server; reported once, before the first wait.
    WaitingForServer { item: ItemId },
}

/// How a command ended, as one closed code.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    /// A status, plan or verify answered.
    Ok,
    /// Every requested item is already set up, or none can be.
    NothingToDo,
    /// Every planned item was set up.
    Completed,
    /// The person did not approve the plan.
    NeedsApproval,
    /// The plan is not the one approved; it is reported for a new approval.
    PlanChanged,
    /// Another setup or removal is changing the item, and this command did not follow it
    /// to its end.
    Busy,
    /// The setup was refused before anything changed, for `failure`.
    Refused,
    /// An item's setup or removal did not finish, for `failure`.
    Failed,
    /// The setup stopped because it was asked to.
    Cancelled,
    /// A stop was asked of the setups running in other processes.
    CancelRequested,
    /// No setup was running to stop.
    NothingRunning,
    /// The requested items were removed.
    Removed,
}

impl Outcome {
    /// Whether the command did what was asked.
    pub fn succeeded(self) -> bool {
        matches!(
            self,
            Self::Ok
                | Self::NothingToDo
                | Self::Completed
                | Self::CancelRequested
                | Self::NothingRunning
                | Self::Removed
        )
    }
}

/// What one command found and did. `rows` is every item's state after the command;
/// `plan` is the plan a setup or plan reports; `item` and `failure` name the item and
/// the category a refusal or failure is for; `items` are the items a cancel asked to
/// stop or a removal removed.
#[derive(Clone, Debug)]
pub struct Report {
    pub outcome: Outcome,
    pub mode: CheckMode,
    pub rows: Vec<StatusRow>,
    pub plan: Option<SetupPlan>,
    pub item: Option<ItemId>,
    pub failure: Option<FailureCategory>,
    pub items: Vec<ItemId>,
}

impl Report {
    fn new(outcome: Outcome, rows: Vec<StatusRow>) -> Self {
        Self {
            outcome,
            mode: CheckMode::Quick,
            rows,
            plan: None,
            item: None,
            failure: None,
            items: Vec::new(),
        }
    }

    fn for_item(mut self, item: ItemId, failure: Option<FailureCategory>) -> Self {
        self.item = Some(item);
        self.failure = failure;
        self
    }

    fn with_plan(mut self, plan: SetupPlan) -> Self {
        self.plan = Some(plan);
        self
    }

    /// The digest an approval of the reported plan binds.
    pub fn plan_digest(&self) -> Option<Sha256Digest> {
        self.plan.as_ref().map(SetupPlan::digest)
    }
}

/// What a setup is asked to do.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct SetupRequest {
    /// The items to set up; `None` is every item whose row offers an action.
    pub items: Option<Vec<ItemId>>,
    /// The digest of a plan the person already approved, such as the one a Resume
    /// repeats. A setup that carries one asks for no review.
    pub approved: Option<Sha256Digest>,
}

/// The person's answer to a plan's review.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Answer {
    /// Approves the plan with this digest.
    Approve(Sha256Digest),
    Decline,
}

/// Reads one setting of the engine's own environment.
pub type Ambient = dyn Fn(&str) -> Option<OsString> + Send + Sync;

/// The bytes free on the volume holding a path, or `None` when it cannot be read.
pub type FreeSpace = dyn Fn(&Path) -> Option<u64> + Send + Sync;

/// Everything the owner resolves for the engine: where components live, which pins and
/// driver this build carries, how to reach publishers, and the host facts the engine
/// does not measure itself.
pub struct EngineConfig {
    /// The installation's storage root, whose volume the free-space rule measures.
    pub storage_root: PathBuf,
    pub locations: Locations,
    pub pins: ComponentPins,
    /// The bundled browser driver's manifest; `None` when this build carries no driver.
    pub driver: Option<DriverManifest>,
    /// This computer's platform; `None` when no pin can name it.
    pub platform: Option<Platform>,
    pub network: Network,
    /// The engine's own environment, for the operating system settings its children
    /// need.
    pub ambient: Box<Ambient>,
    /// The fixed loopback address the manager's local AI server answers on, recorded for
    /// the programs that use it.
    pub local_ai_address: SocketAddr,
    /// The complete environment a browser check launches the browser with.
    pub browser_environment: BTreeMap<OsString, OsString>,
    /// The owner's temporary folder; a browser check's throwaway profile lives inside it.
    pub scratch: PathBuf,
    /// The bytes free on the volume holding a path, or `None` when it cannot be read.
    pub free_space: Box<FreeSpace>,
    /// This computer's memory when the owner measured it; full checks and setup
    /// measure it otherwise. Quick status uses only an existing measurement.
    pub hardware: Option<Hardware>,
    pub policy: RetryPolicy,
}

/// The component engine of one installation.
pub struct Engine {
    config: EngineConfig,
    activity: ActivityStore,
    receipts: ReceiptStore,
    /// The person's local model selection when the owner admitted the local AI's
    /// provisioning; `None` serves the local AI read-only.
    local_ai: Option<LocalModels>,
    /// Arguments a test's stand-in browser is launched with.
    #[cfg(test)]
    pub(crate) browser_leading: Vec<OsString>,
}

/// What one quick look at an item found, with what a setup of it would plan.
struct Survey {
    reading: Reading,
    entry: Option<PlanEntry>,
}

/// Why one item's setup or removal did not finish.
enum Stop {
    Busy,
    Failed(FailureCategory),
}

/// How following another engine's setup of one item ended.
enum Followed {
    /// The item was set up.
    Completed,
    /// The followed run did not set the item up: it stopped at `item` for `outcome`.
    Stopped(RunStop),
    /// The follower's own cancellation stopped it following; the followed setup goes on.
    Abandoned,
    /// What changes the item publishes no setup to follow, as a removal.
    Unfollowable,
}

/// One planned item of a run: its writer lock is this run's, another engine's setup holds
/// it, or taking it failed.
enum Slot<'a> {
    Own(ItemWriter<'a>),
    Follow,
    Failed(FailureCategory),
}

impl From<Error> for Stop {
    fn from(error: Error) -> Self {
        match error {
            Error::Busy => Self::Busy,
            error => Self::Failed(browser::failure_category(&error)),
        }
    }
}

impl From<LocalAiError> for Stop {
    fn from(error: LocalAiError) -> Self {
        match error {
            LocalAiError::Engine(Error::Busy) => Self::Busy,
            error => Self::Failed(error.category()),
        }
    }
}

/// The engine's event sink, shared by the steps and the transfers of one command. A phase
/// is reported when an item's step changes, so a step recorded again is not repeated.
struct Sink<'e> {
    events: RefCell<&'e mut dyn FnMut(Event)>,
    steps: RefCell<BTreeMap<ItemId, SetupStep>>,
}

impl<'e> Sink<'e> {
    fn new(events: &'e mut dyn FnMut(Event)) -> Self {
        Self {
            events: RefCell::new(events),
            steps: RefCell::default(),
        }
    }

    fn emit(&self, event: Event) {
        if let Event::Phase { item, step } = event
            && self.steps.borrow_mut().insert(item, step) == Some(step)
        {
            return;
        }
        (self.events.borrow_mut())(event);
    }
}

/// Turns one item's transfer events into the engine's: progress over the whole item,
/// throttled, and retry notices; and looks for a cancel request at every chunk.
struct Reporter<'s, 'e> {
    sink: &'s Sink<'e>,
    writer: &'s ItemWriter<'s>,
    item: ItemId,
    cancel_request: PathBuf,
    cancellation: &'s Cancellation,
    /// Bytes of the item's earlier parts, counted before this part's.
    offset: u64,
    /// The item's whole known download, when it is more than one part's.
    total: Option<u64>,
    last: Option<(Instant, u64)>,
}

impl Reporter<'_, '_> {
    fn transfer(&mut self, event: TransferEvent) {
        match event {
            TransferEvent::Progress { completed, total } => {
                if fs::symlink_metadata(&self.cancel_request).is_ok() {
                    self.cancellation.cancel();
                }
                let completed = self.offset.saturating_add(completed);
                let total = self.total.unwrap_or(total).max(completed);
                if self.due(completed, total) {
                    self.last = Some((Instant::now(), completed));
                    // Published for followers on a best effort: a record that cannot be
                    // replaced leaves them the previous figure, and the setup goes on.
                    let _ = self.writer.progress(completed, total);
                    self.sink.emit(Event::Progress {
                        item: self.item,
                        completed,
                        total,
                    });
                }
            }
            TransferEvent::Retrying { attempt, delay } => {
                // Best effort, as the progress figure.
                let _ = self.writer.retrying(attempt, delay);
                self.sink.emit(Event::Retrying {
                    item: self.item,
                    attempt,
                    delay,
                });
            }
        }
    }

    /// The first report, the last, and otherwise one at most every interval that moved
    /// at least 1 % of the total.
    fn due(&self, completed: u64, total: u64) -> bool {
        let Some((at, reported)) = self.last else {
            return true;
        };
        if completed == reported {
            return false;
        }
        completed == total
            || (at.elapsed() >= PROGRESS_INTERVAL
                && u128::from(completed.abs_diff(reported)) * 100 >= u128::from(total))
    }
}

/// The category a reading that is not usable reports for a setup that ends with it.
fn failure_of(observation: Observation) -> FailureCategory {
    match observation {
        Observation::Failed(category) => category,
        Observation::Blocked(BlockedReason::Offline) => FailureCategory::Offline,
        Observation::Blocked(BlockedReason::Hardware) => FailureCategory::NotEnoughMemory,
        Observation::Blocked(BlockedReason::NotInThisBuild) => FailureCategory::NotInThisBuild,
        Observation::Absent => FailureCategory::DamagedDownload,
        _ => FailureCategory::Unexpected,
    }
}

/// An id no other run of this installation has: two independently keyed hashes of this
/// moment and process.
fn run_id() -> String {
    let state = std::collections::hash_map::RandomState::new();
    let moment = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |since| since.as_nanos());
    (0u8..2)
        .map(|part| {
            let mut hasher = state.build_hasher();
            hasher.write_u8(part);
            hasher.write_u128(moment);
            hasher.write_u32(std::process::id());
            format!("{:016x}", hasher.finish())
        })
        .collect()
}

fn ended_outcome(outcome: EndedOutcome) -> Outcome {
    match outcome {
        EndedOutcome::Completed => Outcome::Completed,
        EndedOutcome::Failed => Outcome::Failed,
        EndedOutcome::Cancelled => Outcome::Cancelled,
        EndedOutcome::Busy => Outcome::Busy,
    }
}

/// What a follower has already relayed of one item's published record.
#[derive(Default)]
struct Relayed {
    steps: usize,
    progress: Option<Bytes>,
    retry: Option<Retry>,
    waiting_for_server: bool,
}

impl Relayed {
    /// Reports what `published` holds that was not reported yet: each step reached since,
    /// then a changed byte figure, a new retry and the start of a server wait.
    fn relay(&mut self, item: ItemId, published: &Published, sink: &Sink<'_>) {
        for step in published.steps.iter().skip(self.steps) {
            sink.emit(Event::Phase { item, step: *step });
        }
        self.steps = self.steps.max(published.steps.len());
        if published.progress != self.progress {
            self.progress = published.progress;
            if let Some(Bytes { completed, total }) = published.progress
                && total > 0
            {
                sink.emit(Event::Progress {
                    item,
                    completed: completed.min(total),
                    total,
                });
            }
        }
        if published.retry != self.retry {
            self.retry = published.retry;
            if let Some(Retry { attempt, delay_ms }) = published.retry {
                sink.emit(Event::Retrying {
                    item,
                    attempt,
                    delay: Duration::from_millis(delay_ms),
                });
            }
        }
        if published.waiting_for_server && !self.waiting_for_server {
            sink.emit(Event::WaitingForServer { item });
        }
        self.waiting_for_server = published.waiting_for_server;
    }
}

/// The nearest folder of `path` that exists, whose volume holds `path` once it is made.
fn existing_ancestor(path: &Path) -> &Path {
    path.ancestors()
        .find(|ancestor| ancestor.is_dir())
        .unwrap_or(path)
}

impl Engine {
    pub fn new(config: EngineConfig) -> Result<Self, Error> {
        Ok(Self {
            activity: ActivityStore::new(config.locations.activity.clone())?,
            receipts: ReceiptStore::new(config.locations.receipts.clone())?,
            local_ai: None,
            config,
            #[cfg(test)]
            browser_leading: Vec::new(),
        })
    }

    pub fn locations(&self) -> &Locations {
        &self.config.locations
    }

    /// Admits the local AI's provisioning with the local models every later command plans,
    /// pulls, checks and removes: the person's selection, as the desktop read it. It
    /// replaces any earlier selection. No other owner calls it.
    pub fn admit_local_ai(&mut self, models: LocalModels) {
        self.local_ai = Some(models);
    }

    /// The selection the local AI is admitted with; none for a read-only engine.
    fn local_models(&self) -> LocalModels {
        self.local_ai.clone().unwrap_or_default()
    }

    /// Whether this engine may plan, set up or remove `item`.
    fn provisions(&self, item: ItemId) -> bool {
        item != ItemId::LocalAi || self.local_ai.is_some()
    }

    /// The refusal of a plan, setup or removal naming an item this engine serves read-only.
    fn read_only_refusal(&mut self, items: &[ItemId]) -> Option<Report> {
        let item = items.iter().copied().find(|item| !self.provisions(*item))?;
        Some(Report::new(Outcome::Refused, self.quick_rows(&ItemId::ALL)).for_item(item, None))
    }

    /// Every item's state. A quick check reads local facts only; a full check also runs
    /// each item's network preflight and exercises it: one headless browser launch, and
    /// one generated token for each selected model.
    pub fn status(
        &mut self,
        mode: CheckMode,
        items: &[ItemId],
        events: &mut dyn FnMut(Event),
        cancellation: &Cancellation,
    ) -> Report {
        let rows = match mode {
            CheckMode::Quick => self.quick_rows(items),
            CheckMode::Full => self.full_rows(items, &Sink::new(events), cancellation),
        };
        Report {
            mode,
            ..Report::new(Outcome::Ok, rows)
        }
    }

    /// A full check of `items`, every item when empty.
    pub fn verify(
        &mut self,
        items: &[ItemId],
        events: &mut dyn FnMut(Event),
        cancellation: &Cancellation,
    ) -> Report {
        let items = if items.is_empty() {
            &ItemId::ALL[..]
        } else {
            items
        };
        self.status(CheckMode::Full, items, events, cancellation)
    }

    /// The plan a setup of `items` would ask the person to approve, without asking.
    pub fn plan(&mut self, items: Option<&[ItemId]>) -> Report {
        match self.planned(items) {
            Ok((rows, Some(plan))) => Report::new(Outcome::Ok, rows).with_plan(plan),
            Ok((rows, None)) => Report::new(Outcome::NothingToDo, rows),
            Err(report) => report,
        }
    }

    /// Sets up the requested items under an approval of their plan's digest. Without an
    /// approved digest in `request`, `review` is asked once, with the plan.
    pub fn setup(
        &mut self,
        request: &SetupRequest,
        review: &mut dyn FnMut(&SetupPlan) -> Answer,
        events: &mut dyn FnMut(Event),
        cancellation: &Cancellation,
    ) -> Report {
        let sink = Sink::new(events);
        let items = request.items.as_deref();
        let (rows, plan) = match self.planned(items) {
            Ok((rows, Some(plan))) => (rows, plan),
            Ok((rows, None)) => return Report::new(Outcome::NothingToDo, rows),
            Err(report) if report.outcome == Outcome::Busy => {
                return self.follow_only(&report.items, &sink, cancellation);
            }
            Err(report) => return report,
        };
        for entry in &plan.entries {
            sink.emit(Event::Phase {
                item: entry.item,
                step: SetupStep::Plan,
            });
        }
        if let Some(refusal) = self.preflight(&plan, &sink) {
            return Report::new(Outcome::Refused, rows)
                .for_item(refusal.0, Some(refusal.1))
                .with_plan(plan);
        }
        if !plan.space.sufficient() {
            return Report::new(Outcome::Refused, rows)
                .with_plan(plan)
                .disk_full();
        }
        let digest = plan.digest();
        let mut plan = match &request.approved {
            Some(approved) if *approved == digest => plan,
            Some(_) => return Report::new(Outcome::PlanChanged, rows).with_plan(plan),
            None => match review(&plan) {
                Answer::Decline => {
                    return Report::new(Outcome::NeedsApproval, rows).with_plan(plan);
                }
                Answer::Approve(approved) => match self.planned(items) {
                    Ok((_, Some(again))) if again.digest() == approved => again,
                    Ok((rows, Some(again))) => {
                        return Report::new(Outcome::PlanChanged, rows).with_plan(again);
                    }
                    Ok((rows, None)) => return Report::new(Outcome::NothingToDo, rows),
                    Err(report) if report.outcome == Outcome::Busy => {
                        return self.follow_only(&report.items, &sink, cancellation);
                    }
                    Err(report) => return report,
                },
            },
        };
        plan.remeasure(self.free_bytes());
        if !plan.space.sufficient() {
            let rows = self.quick_rows(&ItemId::ALL);
            return Report::new(Outcome::Refused, rows)
                .with_plan(plan)
                .disk_full();
        }
        let stopped = self.run_plan(&plan, &sink, cancellation);
        let rows = self.quick_rows(&ItemId::ALL);
        let report = stopped.unwrap_or_else(|| Report::new(Outcome::Completed, Vec::new()));
        Report { rows, ..report }.with_plan(plan)
    }

    /// Asks every setup running in another process of this installation to stop at its
    /// next transfer chunk.
    pub fn request_cancel(&mut self) -> Report {
        self.request_cancel_of(&ItemId::ALL)
    }

    /// [`Self::request_cancel`] for the setups of `items` alone.
    pub fn request_cancel_of(&mut self, items: &[ItemId]) -> Report {
        let asked = self.ask_to_stop(items);
        let outcome = if asked.is_empty() {
            Outcome::NothingRunning
        } else {
            Outcome::CancelRequested
        };
        Report {
            items: asked,
            ..Report::new(outcome, self.quick_rows(&ItemId::ALL))
        }
    }

    /// Removes `items`, each under its writer lock: the browser's builds and receipt, and
    /// the local AI's program and selected models.
    pub fn remove(&mut self, items: &[ItemId], events: &mut dyn FnMut(Event)) -> Report {
        if let Some(refusal) = self.read_only_refusal(items) {
            return refusal;
        }
        let sink = Sink::new(events);
        let mut removed = Vec::new();
        for item in ItemId::ALL.into_iter().filter(|item| items.contains(item)) {
            let report =
                |outcome, failure| Report::new(outcome, Vec::new()).for_item(item, failure);
            let stopped = match self.remove_item(item, &sink) {
                Ok(()) => {
                    removed.push(item);
                    continue;
                }
                Err(Stop::Busy) => report(Outcome::Busy, None),
                Err(Stop::Failed(category)) => report(Outcome::Failed, Some(category)),
            };
            return Report {
                rows: self.quick_rows(&ItemId::ALL),
                items: removed,
                ..stopped
            };
        }
        Report {
            items: removed,
            ..Report::new(Outcome::Removed, self.quick_rows(&ItemId::ALL))
        }
    }

    /// Removes the local model `name` alone, under the local AI's writer lock: its
    /// manifest and each layer no other stored model uses, keeping the program, its
    /// receipt and every other model. The desktop clears the roles that selected it
    /// first, so the local AI's row then reads from the remaining selection. Only an
    /// engine admitted to provision the local AI removes one; any other is refused.
    pub fn remove_model(&mut self, name: &ModelName, events: &mut dyn FnMut(Event)) -> Report {
        let item = ItemId::LocalAi;
        if let Some(refusal) = self.read_only_refusal(&[item]) {
            return refusal;
        }
        let sink = Sink::new(events);
        let observer = |step| sink.emit(Event::Phase { item, step });
        let removed = self
            .activity
            .begin_observed(item, SetupStep::Cleanup, &observer)
            .map_err(Stop::from)
            .and_then(|writer| {
                let models =
                    Models::new(LocalModels::default(), self.config.locations.models.clone());
                let outcome = models.remove_named(name).map_err(Stop::from);
                finish(writer, outcome)
            });
        let rows = self.quick_rows(&ItemId::ALL);
        match removed {
            Ok(()) => Report {
                items: vec![item],
                ..Report::new(Outcome::Removed, rows)
            },
            Err(Stop::Busy) => Report::new(Outcome::Busy, rows).for_item(item, None),
            Err(Stop::Failed(category)) => {
                Report::new(Outcome::Failed, rows).for_item(item, Some(category))
            }
        }
    }

    /// Leaves a cancel request beside each of `items` a setup is running, reading nothing
    /// else, and returns the items asked. The setup stops at its next transfer chunk.
    pub fn ask_to_stop(&self, items: &[ItemId]) -> Vec<ItemId> {
        let mut asked = Vec::new();
        for item in ItemId::ALL.into_iter().filter(|item| items.contains(item)) {
            if !matches!(self.activity.activity(item), Ok(Activity::Running(_))) {
                continue;
            }
            let written = filesystem::refuse_links(&self.config.locations.activity)
                .and_then(|()| Ok(fs::write(self.cancel_request(item), b"")?));
            if written.is_ok() {
                asked.push(item);
            }
        }
        asked
    }

    fn cancel_request(&self, item: ItemId) -> PathBuf {
        self.config
            .locations
            .activity
            .join(format!("{item}.cancel"))
    }

    /// Withdraws a cancel request meant for an earlier setup of `item`; called once the
    /// item's writer lock is held, so only a request made from now on stops this setup.
    fn clear_cancel_request(&self, item: ItemId) -> Result<(), Error> {
        match fs::remove_file(self.cancel_request(item)) {
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error.into()),
            _ => Ok(()),
        }
    }

    fn free_bytes(&self) -> Option<u64> {
        (self.config.free_space)(existing_ancestor(&self.config.storage_root))
    }

    fn hardware(&mut self) -> Hardware {
        match self.config.hardware {
            Some(hardware) => hardware,
            None => {
                let hardware = Hardware::measure(&*self.config.ambient);
                self.config.hardware = Some(hardware);
                hardware
            }
        }
    }

    fn browser_layout(&self) -> Option<Result<BrowserLayout, Error>> {
        let driver = self.config.driver.as_ref()?;
        let platform = self.config.platform?;
        Some(BrowserLayout::new(
            self.config.locations.browsers.clone(),
            driver,
            self.config.pins.browser.as_ref(),
            platform,
        ))
    }

    /// The local AI's program and the selected models, when this build pins the program
    /// for this platform.
    fn local_ai_parts(&self) -> Option<Result<(Program, Models), Error>> {
        let platform = self.config.platform?;
        let pins = self.config.pins.program.as_ref()?;
        match Program::new(pins, platform, self.config.locations.clone()) {
            Ok(Some(program)) => Some(Ok((
                program,
                Models::new(self.local_models(), self.config.locations.models.clone()),
            ))),
            Ok(None) => None,
            Err(error) => Some(Err(error)),
        }
    }

    fn survey(&mut self, item: ItemId) -> Survey {
        match item {
            ItemId::Browser => self.survey_browser(),
            ItemId::LocalAi => self.survey_local_ai(),
        }
    }

    fn survey_browser(&self) -> Survey {
        let layout = match self.browser_layout() {
            None => return Survey::not_in_this_build(),
            Some(Err(_)) => return Survey::unreadable(),
            Some(Ok(layout)) => layout,
        };
        let receipt = self.receipts.read(ItemId::Browser);
        let reading = layout.quick_check(&receipt);
        let entry = self.config.pins.browser.as_ref().and_then(|pins| {
            PlanEntry::whole(
                ItemId::Browser,
                layout.pending_download_bytes(&receipt),
                pins.hosts.iter().cloned().collect(),
                Destination::PlaywrightBrowsers,
                Some(layout.version().to_owned()),
            )
            .ok()
            .filter(|_| layout.pinned())
        });
        Survey { reading, entry }
    }

    fn survey_local_ai(&mut self) -> Survey {
        // Quick status reads local facts only. Hardware discovery can launch slow
        // driver queries; full checks and setup own that work and retain its result.
        // An unmeasured capacity must not invent a hardware shortfall.
        let hardware = self.config.hardware.unwrap_or_default();
        let (program, models) = match self.local_ai_parts() {
            None => return Survey::not_in_this_build(),
            Some(Err(_)) => return Survey::unreadable(),
            Some(Ok(parts)) => parts,
        };
        let program_observation = program.observe_quick();
        let model_observations: Vec<Observation> = models
            .selection()
            .as_slice()
            .iter()
            .map(|model| models.observe_quick(model, &hardware))
            .collect();
        let reading = local_ai::reading(
            CheckMode::Quick,
            program_observation,
            Some(program.version().to_owned()),
            &model_observations,
        );
        let present = Observation::Present { note: None };
        let mut parts = Vec::new();
        if program_observation != present {
            parts.push(program.plan_part());
        }
        parts.extend(
            models
                .plan_parts()
                .into_iter()
                .zip(&model_observations)
                .filter(|(_, observation)| **observation != present)
                .map(|(part, _)| part),
        );
        let entry = PlanEntry::of_parts(ItemId::LocalAi, parts, Destination::OllamaModels).ok();
        Survey { reading, entry }
    }

    /// The row a reading gives `item`, with its running or interrupted setup and the
    /// category its last setup recorded. An activity record that cannot be read leaves
    /// the item unknown.
    fn row(&self, item: ItemId, survey: &Survey) -> StatusRow {
        let declaration = item.declaration();
        let mut row = match self.activity.activity(item) {
            Ok(activity) => state::derive_row(
                declaration,
                &survey.reading,
                activity,
                self.activity.last_failure(item),
            ),
            Err(_) => state::derive_row(
                declaration,
                &Reading {
                    observation: Observation::Unreadable,
                    ..survey.reading.clone()
                },
                Activity::Idle,
                None,
            ),
        };
        if row.state != ItemState::Ready {
            row.size_estimate_bytes = survey.entry.as_ref().and_then(|entry| entry.download_bytes);
        }
        if !self.provisions(item)
            && matches!(
                row.recovery,
                Some(
                    RecoveryAction::SetUp
                        | RecoveryAction::Update
                        | RecoveryAction::TryAgain
                        | RecoveryAction::Resume
                )
            )
        {
            row.recovery = Some(RecoveryAction::SetUpInDesktop);
        }
        row
    }

    fn quick_rows(&mut self, items: &[ItemId]) -> Vec<StatusRow> {
        ItemId::ALL
            .into_iter()
            .filter(|item| items.contains(item))
            .map(|item| {
                let survey = self.survey(item);
                self.row(item, &survey)
            })
            .collect()
    }

    fn full_rows(
        &mut self,
        items: &[ItemId],
        sink: &Sink<'_>,
        cancellation: &Cancellation,
    ) -> Vec<StatusRow> {
        ItemId::ALL
            .into_iter()
            .filter(|item| items.contains(item))
            .map(|item| {
                sink.emit(Event::Phase {
                    item,
                    step: SetupStep::Verify,
                });
                let mut survey = self.survey(item);
                survey.reading = match item {
                    ItemId::Browser => self.full_browser(cancellation),
                    ItemId::LocalAi => self.full_local_ai(),
                }
                .unwrap_or(Reading {
                    mode: CheckMode::Full,
                    ..survey.reading.clone()
                });
                if let Some(mut hosts) = network::item_hosts(&self.config.pins, item.as_str()) {
                    if item == ItemId::LocalAi {
                        hosts.extend(self.local_models().hosts());
                    }
                    let hosts: Vec<HostName> = hosts.into_iter().collect();
                    let report = network::preflight(&self.config.network, &hosts, HOST_TIMEOUT);
                    survey.reading = survey.reading.held_by_network(&report);
                }
                self.row(item, &survey)
            })
            .collect()
    }

    #[cfg(not(test))]
    fn launch_context(&self) -> LaunchContext<'_> {
        LaunchContext::new(&self.config.browser_environment, &self.config.scratch)
    }

    /// The production context, launching the test's stand-in browser.
    #[cfg(test)]
    fn launch_context(&self) -> LaunchContext<'_> {
        let mut context =
            LaunchContext::new(&self.config.browser_environment, &self.config.scratch);
        context.leading = self.browser_leading.clone();
        context
    }

    /// The browser's full check, or `None` when this build cannot read its layout.
    fn full_browser(&self, cancellation: &Cancellation) -> Option<Reading> {
        let layout = self.browser_layout()?.ok()?;
        let receipt = self.receipts.read(ItemId::Browser);
        Some(
            layout
                .full_check(&receipt, &self.launch_context(), cancellation)
                .reading,
        )
    }

    /// The local AI's full check: the program's files and the manager's server answering
    /// for it, then one generated token for each selected model on that server. Without a
    /// running server the program reads `program_not_running` and each model only as its
    /// files say.
    fn full_local_ai(&mut self) -> Option<Reading> {
        let hardware = self.hardware();
        let (program, models) = self.local_ai_parts()?.ok()?;
        let program_observation = program.observe_full();
        let present = Observation::Present { note: None };
        let selected = models.selection().as_slice();
        let models_observed: Vec<Observation> = match program.running_server() {
            Some(server) if program_observation == present => selected
                .iter()
                .map(|model| models.observe_full(&server, model, &hardware))
                .collect(),
            _ => selected
                .iter()
                .map(|model| models.observe_quick(model, &hardware))
                .collect(),
        };
        Some(local_ai::reading(
            CheckMode::Full,
            program_observation,
            Some(program.version().to_owned()),
            &models_observed,
        ))
    }

    /// Every item's quick row, and the plan for the requested items, or by default for
    /// every item whose row offers an action. When any requested item, or by default any
    /// item, is being set up or removed elsewhere, the answer is busy with those items, for a
    /// setup to follow. A requested item this computer or build cannot hold refuses; one
    /// already set up is left out.
    fn planned(
        &mut self,
        items: Option<&[ItemId]>,
    ) -> Result<(Vec<StatusRow>, Option<SetupPlan>), Report> {
        if let Some(refusal) = items.and_then(|requested| self.read_only_refusal(requested)) {
            return Err(refusal);
        }
        let mut surveys: Vec<(ItemId, Survey)> = ItemId::ALL
            .into_iter()
            .map(|item| (item, self.survey(item)))
            .collect();
        let rows: Vec<StatusRow> = surveys
            .iter()
            .map(|(item, survey)| self.row(*item, survey))
            .collect();
        let running: Vec<ItemId> = rows
            .iter()
            .filter(|row| match items {
                None => self.provisions(row.item),
                Some(requested) => requested.contains(&row.item),
            })
            .filter(|row| matches!(row.state, ItemState::Provisioning | ItemState::Verifying))
            .map(|row| row.item)
            .collect();
        if let Some(first) = running.first() {
            return Err(Report {
                items: running.clone(),
                ..Report::new(Outcome::Busy, rows.clone()).for_item(*first, None)
            });
        }
        let chosen: Vec<ItemId> = match items {
            None => state::items_to_set_up(&rows),
            Some(requested) => {
                let mut chosen = Vec::new();
                for row in rows.iter().filter(|row| requested.contains(&row.item)) {
                    let refusal = match row.state {
                        ItemState::Ready => continue,
                        ItemState::Blocked(BlockedReason::NotInThisBuild)
                        | ItemState::Failed(FailureCategory::NotInThisBuild) => {
                            Some(FailureCategory::NotInThisBuild)
                        }
                        ItemState::Blocked(BlockedReason::Hardware)
                        | ItemState::Failed(FailureCategory::NotEnoughMemory) => {
                            Some(FailureCategory::NotEnoughMemory)
                        }
                        _ => None,
                    };
                    if let Some(category) = refusal {
                        return Err(Report::new(Outcome::Refused, rows.clone())
                            .for_item(row.item, Some(category)));
                    }
                    chosen.push(row.item);
                }
                chosen
            }
        };
        let entries: Vec<PlanEntry> = surveys
            .iter_mut()
            .filter(|(item, _)| chosen.contains(item))
            .filter_map(|(_, survey)| survey.entry.take())
            .collect();
        if entries.is_empty() {
            return Ok((rows, None));
        }
        let plan = SetupPlan::new(entries, self.free_bytes()).map_err(|_| Report {
            failure: Some(FailureCategory::Unexpected),
            ..Report::new(Outcome::Failed, rows.clone())
        })?;
        Ok((rows, Some(plan)))
    }

    /// Checks the hosts of every planned item that downloads anything; the first item
    /// whose hosts cannot be reached refuses the setup with its category.
    fn preflight(&self, plan: &SetupPlan, sink: &Sink<'_>) -> Option<(ItemId, FailureCategory)> {
        for entry in &plan.entries {
            if entry.download_bytes == Some(0) {
                continue;
            }
            sink.emit(Event::Phase {
                item: entry.item,
                step: SetupStep::Preflight,
            });
            let report =
                network::preflight(&self.config.network, &entry.source_hosts, HOST_TIMEOUT);
            if report.outcome() != Reachability::Reachable {
                return Some((
                    entry.item,
                    report
                        .failure_category()
                        .unwrap_or(FailureCategory::Unexpected),
                ));
            }
        }
        None
    }

    /// Runs the approved plan's items in setup order under one run. Every item's writer
    /// lock is taken first, so the whole run reads as running from its start; an item
    /// another engine holds is followed in its turn instead. The first item that does not
    /// finish stops the run, and the items after it are released as they were, each naming
    /// where the run stopped.
    fn run_plan(
        &mut self,
        plan: &SetupPlan,
        sink: &Sink<'_>,
        cancellation: &Cancellation,
    ) -> Option<Report> {
        let hardware = self.hardware();
        let run = RunMark {
            id: run_id(),
            plan_digest: plan.digest(),
        };
        let observers: Vec<Box<dyn Fn(SetupStep) + '_>> = plan
            .entries
            .iter()
            .map(|entry| {
                let item = entry.item;
                Box::new(move |step| sink.emit(Event::Phase { item, step }))
                    as Box<dyn Fn(SetupStep) + '_>
            })
            .collect();
        let slots: Vec<Slot<'_>> = plan
            .entries
            .iter()
            .zip(&observers)
            .map(|(entry, observer)| {
                match self.activity.queue(entry.item, &run, observer.as_ref()) {
                    Ok(writer) => match self.clear_cancel_request(entry.item) {
                        Ok(()) => Slot::Own(writer),
                        Err(error) => {
                            let category = browser::failure_category(&error);
                            match writer.failed(category) {
                                Ok(()) => Slot::Failed(category),
                                Err(error) => Slot::Failed(browser::failure_category(&error)),
                            }
                        }
                    },
                    Err(Error::Busy) => Slot::Follow,
                    Err(error) => Slot::Failed(browser::failure_category(&error)),
                }
            })
            .collect();
        let mut slots = slots.into_iter();
        let mut stopped = None;
        for (entry, slot) in plan.entries.iter().zip(&mut slots) {
            let item = entry.item;
            let done = match slot {
                Slot::Own(writer) => match item {
                    ItemId::Browser => self.set_up_browser(entry, writer, sink, cancellation),
                    ItemId::LocalAi => {
                        self.set_up_local_ai(entry, writer, hardware, sink, cancellation)
                    }
                },
                Slot::Follow => match self.follow_item(item, sink, cancellation) {
                    Followed::Completed => Ok(()),
                    Followed::Stopped(RunStop {
                        outcome: EndedOutcome::Busy,
                        ..
                    })
                    | Followed::Unfollowable => Err(Stop::Busy),
                    Followed::Stopped(stop) => Err(Stop::Failed(
                        stop.failure.unwrap_or(FailureCategory::Unexpected),
                    )),
                    Followed::Abandoned => Err(Stop::Failed(FailureCategory::Cancelled)),
                },
                Slot::Failed(category) => Err(Stop::Failed(category)),
            };
            let (outcome, failure) = match done {
                Ok(()) => continue,
                Err(Stop::Busy) => (Outcome::Busy, None),
                Err(Stop::Failed(FailureCategory::Cancelled)) => {
                    (Outcome::Cancelled, Some(FailureCategory::Cancelled))
                }
                Err(Stop::Failed(category)) => (Outcome::Failed, Some(category)),
            };
            stopped = Some(RunStop {
                outcome: match outcome {
                    Outcome::Busy => EndedOutcome::Busy,
                    Outcome::Cancelled => EndedOutcome::Cancelled,
                    _ => EndedOutcome::Failed,
                },
                item,
                failure,
            });
            break;
        }
        let stop = stopped?;
        for slot in slots {
            if let Slot::Own(writer) = slot {
                // The item is left as it was; a record that cannot be removed reads as an
                // interrupted setup, which offers the person Resume.
                let _ = writer.not_reached(stop);
            }
        }
        Some(Report::new(ended_outcome(stop.outcome), Vec::new()).for_item(stop.item, stop.failure))
    }

    /// A setup that found `items` being set up by other engines follows each of them in
    /// setup order and reports the result they reached: completed when every one was set
    /// up, otherwise how and where the first that was not set up stopped.
    fn follow_only(
        &mut self,
        items: &[ItemId],
        sink: &Sink<'_>,
        cancellation: &Cancellation,
    ) -> Report {
        let mut report = None;
        for item in ItemId::ALL.into_iter().filter(|item| items.contains(item)) {
            let stopped = match self.follow_item(item, sink, cancellation) {
                Followed::Completed => continue,
                Followed::Stopped(stop) => Report::new(ended_outcome(stop.outcome), Vec::new())
                    .for_item(stop.item, stop.failure),
                Followed::Abandoned | Followed::Unfollowable => {
                    Report::new(Outcome::Busy, Vec::new()).for_item(item, None)
                }
            };
            report = Some(stopped);
            break;
        }
        let rows = self.quick_rows(&ItemId::ALL);
        let report = report.unwrap_or_else(|| Report::new(Outcome::Completed, Vec::new()));
        Report { rows, ..report }
    }

    /// Follows another engine's setup of `item` until it is done with the item: relays what
    /// it publishes and returns how it ended. The wait between two looks ends on a change
    /// in the activity folder, on the writer letting go of the item's lock, or on this
    /// setup's cancellation.
    fn follow_item(&self, item: ItemId, sink: &Sink<'_>, cancellation: &Cancellation) -> Followed {
        let mut changes = Changes::new(self.activity.root().to_path_buf());
        let wake = changes.waker();
        let _hook = cancellation.on_cancel(wake.clone());
        let bound = (!follow::wake_on_release(self.activity.lock_path(item), wake))
            .then_some(follow::OBSERVATION);
        let mut followed: Option<RunMark> = None;
        let mut relayed = Relayed::default();
        loop {
            if cancellation.is_cancelled() {
                return Followed::Abandoned;
            }
            match self.activity.watch(item) {
                Ok(Watched::Running(Some(published))) => {
                    match &followed {
                        None => {
                            sink.emit(Event::Following {
                                item,
                                plan_digest: published.run.plan_digest.clone(),
                            });
                            followed = Some(published.run.clone());
                        }
                        // Another run holds the item now, so the one followed is done with it.
                        Some(run) if run.id != published.run.id => break,
                        Some(_) => {}
                    }
                    relayed.relay(item, &published, sink);
                }
                Ok(Watched::Running(None)) if followed.is_none() => return Followed::Unfollowable,
                Ok(Watched::Running(None) | Watched::Idle) => break,
                Ok(Watched::Interrupted) => {
                    return Followed::Stopped(RunStop {
                        outcome: EndedOutcome::Failed,
                        item,
                        failure: Some(FailureCategory::Interrupted),
                    });
                }
                Err(_) => return Followed::Unfollowable,
            }
            changes.wait(bound);
        }
        match self.activity.ended(item) {
            Some(ended) if followed.as_ref().is_none_or(|run| run.id == ended.run) => {
                match (ended.outcome, ended.stopped_at) {
                    (EndedOutcome::Completed, _) => Followed::Completed,
                    (outcome, stopped_at) => Followed::Stopped(RunStop {
                        outcome,
                        item: stopped_at.unwrap_or(item),
                        failure: ended.failure,
                    }),
                }
            }
            _ => Followed::Unfollowable,
        }
    }

    fn set_up_browser(
        &self,
        entry: &PlanEntry,
        writer: ItemWriter<'_>,
        sink: &Sink<'_>,
        cancellation: &Cancellation,
    ) -> Result<(), Stop> {
        let item = ItemId::Browser;
        // Builds already in place with nothing to fetch are adopted: the full check below
        // launches them, and only a passing check records them, so no download is announced.
        let first = if entry.download_bytes == Some(0) {
            SetupStep::Verify
        } else {
            SetupStep::Download
        };
        let hosts: BTreeSet<HostName> = entry.source_hosts.iter().cloned().collect();
        let outcome = (|| -> Result<(), Stop> {
            let layout = match self.browser_layout() {
                Some(Ok(layout)) => layout,
                Some(Err(error)) => return Err(error.into()),
                None => return Err(Stop::Failed(FailureCategory::NotInThisBuild)),
            };
            writer.step(first)?;
            let receipt = self.receipts.read(item);
            let mut reporter = Reporter {
                sink,
                writer: &writer,
                item,
                cancel_request: self.cancel_request(item),
                cancellation,
                offset: 0,
                total: None,
                last: None,
            };
            let mut pacing = SystemPacing::default();
            let mut on_event = |event| reporter.transfer(event);
            let mut transfer = Transfer {
                network: &self.config.network,
                hosts: &hosts,
                policy: self.config.policy,
                pacing: &mut pacing,
                events: &mut on_event,
                cancellation,
            };
            layout.install(&mut transfer, &writer, &receipt)?;
            writer.step(SetupStep::Verify)?;
            let receipt = self.receipts.read(item);
            let check = layout.full_check(&receipt, &self.launch_context(), cancellation);
            let Some(verified) = check.verified else {
                return Err(Stop::Failed(failure_of(check.reading.observation)));
            };
            writer.step(SetupStep::Cleanup)?;
            layout.settle(
                verified,
                &self.receipts,
                entry.source_hosts.clone(),
                SystemTime::now(),
            )?;
            Ok(())
        })();
        finish(writer, outcome)
    }

    fn set_up_local_ai(
        &self,
        entry: &PlanEntry,
        writer: ItemWriter<'_>,
        hardware: Hardware,
        sink: &Sink<'_>,
        cancellation: &Cancellation,
    ) -> Result<(), Stop> {
        let item = ItemId::LocalAi;
        let present = Observation::Present { note: None };
        let mut reporter = Reporter {
            sink,
            writer: &writer,
            item,
            cancel_request: self.cancel_request(item),
            cancellation,
            offset: 0,
            total: entry.download_bytes,
            last: None,
        };
        let mut pacing = SystemPacing::default();
        let outcome = (|| -> Result<(), Stop> {
            let (mut program, models) = match self.local_ai_parts() {
                Some(Ok(parts)) => parts,
                Some(Err(error)) => return Err(error.into()),
                None => return Err(Stop::Failed(FailureCategory::NotInThisBuild)),
            };
            writer.step(SetupStep::Download)?;
            let program_part = entry.parts.iter().find(|part| part.part_id == PROGRAM_PART);
            if let Some(part) = program_part {
                let hosts: BTreeSet<HostName> = part.source_hosts.iter().cloned().collect();
                let mut on_event = |event| reporter.transfer(event);
                let mut transfer = Transfer {
                    network: &self.config.network,
                    hosts: &hosts,
                    policy: self.config.policy,
                    pacing: &mut pacing,
                    events: &mut on_event,
                    cancellation,
                };
                // Waits for the manager to stop a server running the old version.
                program.install(&mut transfer)?;
                reporter.offset += part.download_bytes.unwrap_or(0);
                writer.step(SetupStep::Install)?;
                if program.observe_quick() != present {
                    return Err(Stop::Failed(FailureCategory::DamagedDownload));
                }
                program.prune()?;
            }
            if program.observe_quick() != present {
                return Err(Stop::Failed(FailureCategory::DamagedDownload));
            }
            let recorded = matches!(self.receipts.read(item), ReceiptReading::Present(_));
            if program_part.is_some() || !recorded {
                program.settle(
                    &self.receipts,
                    self.config.local_ai_address,
                    SystemTime::now(),
                )?;
            }
            writer.step(SetupStep::Download)?;
            let server = server_under_this_proxy(
                &self.config.network,
                &program,
                &mut pacing,
                cancellation,
                sink,
                &writer,
            )?;
            let mut pulled = BTreeSet::new();
            for part in &entry.parts {
                let Some(model) = models.selection().for_role(&part.part_id) else {
                    continue;
                };
                if !pulled.insert(model.name.to_string()) {
                    continue;
                }
                let mut on_event = |event| reporter.transfer(event);
                let observation = models.pull(
                    &server,
                    model,
                    &mut Pull {
                        policy: self.config.policy,
                        pacing: &mut pacing,
                        events: &mut on_event,
                        cancellation,
                    },
                )?;
                if !observation.usable() {
                    return Err(Stop::Failed(failure_of(observation)));
                }
                reporter.offset += model.size_bytes;
            }
            writer.step(SetupStep::Verify)?;
            for model in models.selection().as_slice() {
                let observation = models.observe_full(&server, model, &hardware);
                if !observation.usable() {
                    return Err(Stop::Failed(failure_of(observation)));
                }
            }
            writer.step(SetupStep::Cleanup)?;
            Ok(())
        })();
        finish(writer, outcome)
    }

    fn remove_item(&mut self, item: ItemId, sink: &Sink<'_>) -> Result<(), Stop> {
        let layout = match item {
            ItemId::Browser => self.browser_layout(),
            ItemId::LocalAi => None,
        };
        let parts = match item {
            ItemId::Browser => None,
            ItemId::LocalAi => self.local_ai_parts(),
        };
        let observer = |step| sink.emit(Event::Phase { item, step });
        let writer = self
            .activity
            .begin_observed(item, SetupStep::Cleanup, &observer)?;
        let receipts = &self.receipts;
        let outcome = (|| -> Result<(), Stop> {
            if let Some(layout) = layout {
                layout?.remove(&writer, receipts)?;
            }
            if let Some(parts) = parts {
                let (mut program, models) = parts?;
                // Waits for the manager to stop its server first.
                program.remove()?;
                models.remove()?;
            }
            receipts.remove(item)?;
            Ok(())
        })();
        finish(writer, outcome)
    }
}

/// The server the models are pulled through, once it answers, and only while it runs
/// under the proxy setting this engine downloads under.
///
/// Looks for the manager's server at once, then at growing intervals within
/// [`SERVER_WAIT`], reporting the wait once; without a server by then the local AI is
/// `program_not_running`, which carries the local AI's setup action.
///
/// The server fetches the model bytes itself, so a server started under another proxy
/// setting would fetch them through that one. The supervisor reads its setting from its
/// own environment at its start, which nothing outside that process can change, so this
/// engine cannot bring the server onto its setting: it refuses at once with
/// `program_proxy_differs`, whose sentence names the restart that can.
fn server_under_this_proxy(
    network: &Network,
    program: &Program,
    pacing: &mut dyn Pacing,
    cancellation: &Cancellation,
    sink: &Sink<'_>,
    writer: &ItemWriter<'_>,
) -> Result<Server, Stop> {
    let server = wait_for_server(program, pacing, cancellation, sink, writer)?;
    if server.proxy_fingerprint() == network.proxy_fingerprint() {
        return Ok(server);
    }
    Err(Stop::Failed(FailureCategory::ProgramProxyDiffers))
}

fn wait_for_server(
    program: &Program,
    pacing: &mut dyn Pacing,
    cancellation: &Cancellation,
    sink: &Sink<'_>,
    writer: &ItemWriter<'_>,
) -> Result<Server, Stop> {
    let item = writer.item();
    let started = Instant::now();
    let mut delay = SERVER_LOOK_FIRST;
    loop {
        if let Some(server) = program.running_server() {
            return Ok(server);
        }
        if started.elapsed() >= SERVER_WAIT {
            return Err(Stop::Failed(FailureCategory::ProgramNotRunning));
        }
        if delay == SERVER_LOOK_FIRST {
            // Best effort, as the progress figure.
            let _ = writer.waiting_for_server();
            sink.emit(Event::WaitingForServer { item });
        }
        pacing.wait(delay, cancellation)?;
        delay = delay.saturating_mul(2).min(SERVER_LOOK_LONGEST);
    }
}

/// Records how an item's work ended: finished, or failed with its category. A part held
/// busy by another engine is no failure of this item, so it records none.
fn finish(writer: ItemWriter<'_>, outcome: Result<(), Stop>) -> Result<(), Stop> {
    match outcome {
        Ok(()) => Ok(writer.finished()?),
        Err(Stop::Failed(category)) => {
            writer.failed(category)?;
            Err(Stop::Failed(category))
        }
        Err(Stop::Busy) => {
            writer.held()?;
            Err(Stop::Busy)
        }
    }
}

impl Survey {
    fn not_in_this_build() -> Self {
        Self {
            reading: Reading::new(
                CheckMode::Quick,
                Observation::Blocked(BlockedReason::NotInThisBuild),
            ),
            entry: None,
        }
    }

    fn unreadable() -> Self {
        Self {
            reading: Reading::new(CheckMode::Quick, Observation::Unreadable),
            entry: None,
        }
    }
}

impl Report {
    fn disk_full(self) -> Self {
        Self {
            failure: Some(FailureCategory::DiskFull),
            ..self
        }
    }
}
