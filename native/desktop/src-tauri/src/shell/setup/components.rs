//! The window's component engine: every status read, full check and setup the
//! window asks for runs on its own worker thread against an engine of this
//! installation, so no command holds the window while the engine works. Each
//! engine report, event and review becomes the window's setup state, and every
//! change bumps one counter the observer follows; nothing polls.
//!
//! A setup asks for the person's approval through the engine's review: the
//! worker publishes the plan and waits for `desktop_setup_answer`, which
//! approves exactly the digest the window showed. The engine checks that
//! digest against a plan it computes again after the answer; when the plan
//! changed meanwhile, the worker asks again with the new plan, so an old
//! approval never sets anything up. What only this window knows stays here:
//! which check and setup it started, how far each item came, and the plans it
//! approved, so a Resume whose plan is one of them applies without a second
//! dialog.
//!
//! The engine words nothing; every value here is a code or a locale-neutral
//! fact, and the window words them. A browser check's process ends with the
//! window: on Windows it runs inside the window's kill-on-close job, and on
//! Linux and macOS inside the window's process scope (`installation`).
use super::wire::{self, CheckKind, CheckStage, Outcome, Refusal, RunStage};
use cadrumo_application::{
    component::Cancellation,
    error::Error,
    provisioning::{
        engine::{Answer, Engine, Event, Outcome as Ended, Report, SetupRequest},
        failure::FailureCategory,
        items::{Destination, ItemId, Locations},
        local_ai::hardware::Hardware,
        plan::{Advisory, PlanEntry, SetupPlan},
        role_host,
        state::{
            BlockedReason, CheckMode, ItemState, Note, RecoveryAction, SetupStep, StaleReason,
            StatusRow,
        },
    },
    value::Sha256Digest,
};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::{Arc, Mutex, MutexGuard, OnceLock, mpsc},
    thread::JoinHandle,
};
use tokio::sync::watch;

/// One engine of this installation.
pub struct Installation {
    pub engine: Engine,
}

/// Builds an engine for one command.
pub type Engines = dyn Fn() -> Result<Installation, Error> + Send + Sync;

/// The engines of the installation this process belongs to. The hardware is
/// measured once, by the first engine, and every later one reuses it. On Linux
/// and macOS the window first keeps a process scope that every browser check
/// and hardware query is created into, so none outlives the window; on Windows
/// the window's kill-on-close job already holds them.
pub fn installation() -> Arc<Engines> {
    let hardware: Arc<OnceLock<Hardware>> = Arc::default();
    Arc::new(move || {
        #[cfg(unix)]
        cadrumo_platform::process_scope::contain_current()?;
        let mut config = role_host::installation_config()?;
        let measured = *hardware.get_or_init(|| Hardware::measure(&*config.ambient));
        config.hardware = Some(measured);
        Ok(Installation {
            engine: Engine::new(config)?,
        })
    })
}

fn lock<T>(value: &Mutex<T>) -> MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|error| error.into_inner())
}

fn operation_id() -> String {
    let mut bytes = [0u8; 32];
    // Without entropy the identifier is still unique within this window.
    if getrandom::fill(&mut bytes).is_err() {
        static COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(1);
        let next = COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        bytes[..8].copy_from_slice(&next.to_be_bytes());
    }
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

#[derive(Clone, Debug)]
struct ItemTrack {
    item: ItemId,
    step: Option<SetupStep>,
    progress: Option<(u64, u64)>,
    retry: Option<(u32, u32)>,
    result: Option<wire::ItemResult>,
}

impl ItemTrack {
    fn new(item: ItemId) -> Self {
        Self {
            item,
            step: None,
            progress: None,
            retry: None,
            result: None,
        }
    }
}

struct CheckTrack {
    operation_id: String,
    kind: CheckKind,
    stage: CheckStage,
}

struct SetupTrack {
    operation_id: String,
    stage: RunStage,
    /// The plan awaiting the person's answer, by its digest.
    review: Option<(String, wire::Review)>,
    /// Where the waiting review hears the answer.
    answers: Option<mpsc::Sender<Answer>>,
    /// The person answered; the engine is checking the plan again.
    answered: bool,
    items: Vec<ItemTrack>,
    phases: Vec<String>,
    hosts: BTreeSet<String>,
    cancellation: Arc<Cancellation>,
    cancel_requested: bool,
    outcome: Option<Outcome>,
    failure: Option<wire::Failure>,
}

impl SetupTrack {
    fn item(&mut self, item: ItemId) -> &mut ItemTrack {
        let index = match self.items.iter().position(|track| track.item == item) {
            Some(index) => index,
            None => {
                self.items.push(ItemTrack::new(item));
                self.items.len() - 1
            }
        };
        &mut self.items[index]
    }

    fn live(&self) -> bool {
        self.stage != RunStage::Settled
    }

    /// The answer the waiting review receives now, if one waits.
    fn decline(&mut self) {
        if let Some(answers) = self.answers.take() {
            // A review that stopped waiting has nothing left to hear.
            let _ = answers.send(Answer::Decline);
        }
        self.review = None;
        if self.stage == RunStage::Review {
            self.stage = RunStage::Planning;
        }
    }
}

#[derive(Default)]
struct Window {
    rows: Option<(CheckMode, Vec<StatusRow>)>,
    check: Option<CheckTrack>,
    setup: Option<SetupTrack>,
    /// The plans this window approved, by digest.
    approved: BTreeSet<String>,
    workers: Vec<JoinHandle<()>>,
    /// Stops a check at its next transfer chunk or browser launch once the window closes.
    checks: Arc<Cancellation>,
    closed: bool,
}

impl Window {
    fn setup_of(&mut self, operation_id: &str) -> Option<&mut SetupTrack> {
        self.setup
            .as_mut()
            .filter(|track| track.operation_id == operation_id)
    }

    fn check_running(&self) -> bool {
        self.check
            .as_ref()
            .is_some_and(|check| check.stage == CheckStage::Running)
    }
}

struct Shared {
    window: Mutex<Window>,
    changed: watch::Sender<u64>,
}

impl Shared {
    fn update<T>(&self, change: impl FnOnce(&mut Window) -> T) -> T {
        let out = change(&mut lock(&self.window));
        self.changed
            .send_modify(|revision| *revision = revision.wrapping_add(1));
        out
    }
}

/// What the engine side of the snapshot holds: every value but the account.
pub struct View {
    pub rows: Vec<wire::Row>,
    pub rows_mode: Option<wire::CheckMode>,
    pub complete: Option<bool>,
    pub hardware_limited: Option<bool>,
    pub check: Option<wire::Check>,
    pub setup: Option<wire::Run>,
    pub details: String,
}

/// The engine as this window drives it.
pub struct Components {
    engines: Arc<Engines>,
    shared: Arc<Shared>,
}

impl Components {
    pub fn new(engines: Arc<Engines>) -> Self {
        Self {
            engines,
            shared: Arc::new(Shared {
                window: Mutex::default(),
                changed: watch::Sender::new(0),
            }),
        }
    }

    /// Changes whenever a command, report, event or review changes what the
    /// window shows.
    pub fn changes(&self) -> watch::Receiver<u64> {
        self.shared.changed.subscribe()
    }

    fn spawn(&self, window: &mut Window, name: &str, work: impl FnOnce() + Send + 'static) {
        window.workers.retain(|worker| !worker.is_finished());
        match std::thread::Builder::new()
            .name(name.to_owned())
            .spawn(work)
        {
            Ok(worker) => window.workers.push(worker),
            // Without a thread the work never starts; its track says it failed.
            Err(_) => {
                if let Some(check) = window.check.as_mut().filter(|_| name == "setup-check") {
                    check.stage = CheckStage::Failed;
                }
                if let Some(track) = window.setup.as_mut().filter(|_| name == "setup-run") {
                    settle_failed(track, wire::Failure::Unexpected);
                }
            }
        }
    }

    /// Reads every item's quick state once, when nothing has read it yet.
    pub fn observe(&self) {
        let mut window = lock(&self.shared.window);
        if window.rows.is_none() && !window.check_running() && !window.closed {
            self.start_check(&mut window, CheckKind::StatusQuick, Vec::new());
            drop(window);
            self.shared
                .changed
                .send_modify(|revision| *revision = revision.wrapping_add(1));
        }
    }

    /// Starts a status read, or joins the one running.
    pub fn check(&self, mode: wire::CheckMode) {
        let kind = match mode {
            wire::CheckMode::Quick => CheckKind::StatusQuick,
            wire::CheckMode::Full => CheckKind::StatusFull,
        };
        self.shared.update(|window| {
            if !window.check_running() && !window.closed {
                self.start_check(window, kind, Vec::new());
            }
        });
    }

    /// Starts a full check of `items`, every item when empty, or joins the check running.
    pub fn verify(&self, items: Vec<ItemId>) {
        self.shared.update(|window| {
            if !window.check_running() && !window.closed {
                self.start_check(window, CheckKind::Verify, items);
            }
        });
    }

    fn start_check(&self, window: &mut Window, kind: CheckKind, items: Vec<ItemId>) {
        let id = operation_id();
        window.check = Some(CheckTrack {
            operation_id: id.clone(),
            kind,
            stage: CheckStage::Running,
        });
        let engines = self.engines.clone();
        let shared = self.shared.clone();
        let cancellation = window.checks.clone();
        self.spawn(window, "setup-check", move || {
            let report = engines().map(|mut installation| {
                let engine = &mut installation.engine;
                match kind {
                    CheckKind::StatusQuick => {
                        engine.status(CheckMode::Quick, &ItemId::ALL, &mut |_| {}, &cancellation)
                    }
                    CheckKind::StatusFull => {
                        engine.status(CheckMode::Full, &ItemId::ALL, &mut |_| {}, &cancellation)
                    }
                    CheckKind::Verify => engine.verify(&items, &mut |_| {}, &cancellation),
                }
            });
            shared.update(|window| {
                let current = window
                    .check
                    .as_ref()
                    .is_some_and(|check| check.operation_id == id);
                let stage = match report {
                    Ok(report) if report.outcome.succeeded() => {
                        window.rows = Some((report.mode, report.rows));
                        CheckStage::Done
                    }
                    _ => CheckStage::Failed,
                };
                if let Some(check) = window.check.as_mut().filter(|_| current) {
                    check.stage = stage;
                }
            });
        });
    }

    /// Plans a setup of `items`, every item whose row offers an action when
    /// `None`, and waits until it asks for an answer, runs or settles. A setup
    /// already running is joined. With `resume`, a plan this window approved
    /// before applies without asking again.
    pub async fn start(&self, items: Option<Vec<ItemId>>, resume: bool) -> Result<(), Refusal> {
        let mut changes = self.changes();
        let id = {
            let mut window = lock(&self.shared.window);
            if window.closed {
                return Err(Refusal::Unavailable);
            }
            if window.setup.as_ref().is_some_and(SetupTrack::live) {
                // One setup at a time: a second start joins the running one.
                return Ok(());
            }
            let id = operation_id();
            let cancellation = Arc::new(Cancellation::default());
            let mut track = SetupTrack {
                operation_id: id.clone(),
                stage: RunStage::Planning,
                review: None,
                answers: None,
                answered: false,
                items: Vec::new(),
                phases: Vec::new(),
                hosts: BTreeSet::new(),
                cancellation: cancellation.clone(),
                cancel_requested: false,
                outcome: None,
                failure: None,
            };
            for item in items.iter().flatten() {
                track.item(*item);
            }
            window.setup = Some(track);
            let engines = self.engines.clone();
            let shared = self.shared.clone();
            let request = SetupRequest {
                items,
                approved: None,
            };
            let run_id = id.clone();
            self.spawn(&mut window, "setup-run", move || {
                run_setup(&*engines, &shared, &run_id, &request, resume, &cancellation);
            });
            id
        };
        self.shared
            .changed
            .send_modify(|revision| *revision = revision.wrapping_add(1));
        loop {
            {
                let mut window = lock(&self.shared.window);
                match window.setup_of(&id) {
                    None => return Err(Refusal::Busy),
                    Some(track) if track.stage != RunStage::Planning => return Ok(()),
                    Some(_) => {}
                }
            }
            if changes.changed().await.is_err() {
                return Ok(());
            }
        }
    }

    /// Answers the plan on screen. An approval binds the digest the window
    /// showed; a plan that changed is refused and shown again. Waits until the
    /// setup runs, settles, or asks again.
    pub async fn answer(
        &self,
        operation_id: &str,
        plan_digest: &str,
        decision: wire::Decision,
    ) -> Result<(), Refusal> {
        let mut changes = self.changes();
        self.shared.update(|window| {
            let Some(track) = window
                .setup_of(operation_id)
                .filter(|track| track.stage == RunStage::Review && track.answers.is_some())
            else {
                return Err(Refusal::NotPending);
            };
            let shown = track
                .review
                .as_ref()
                .map(|(digest, _)| digest.clone())
                .unwrap_or_default();
            let answer = match decision {
                wire::Decision::Reject => Answer::Decline,
                wire::Decision::Apply if shown != plan_digest => {
                    return Err(Refusal::PlanChanged);
                }
                wire::Decision::Apply => Answer::Approve(
                    Sha256Digest::new(plan_digest).map_err(|_| Refusal::PlanChanged)?,
                ),
            };
            if let Some(answers) = track.answers.take() {
                // The worker is waiting for exactly this answer.
                let _ = answers.send(answer.clone());
            }
            track.review = None;
            track.answered = true;
            track.stage = RunStage::Planning;
            if matches!(answer, Answer::Approve(_)) {
                window.approved.insert(plan_digest.to_owned());
            }
            Ok(())
        })?;
        loop {
            {
                let mut window = lock(&self.shared.window);
                match window.setup_of(operation_id) {
                    None => return Err(Refusal::Busy),
                    Some(track) if track.stage == RunStage::Review => {
                        return Err(Refusal::PlanChanged);
                    }
                    Some(track) if track.stage != RunStage::Planning => return Ok(()),
                    Some(_) => {}
                }
            }
            if changes.changed().await.is_err() {
                return Ok(());
            }
        }
    }

    /// Stops the setup this window started at its next transfer chunk, or
    /// declines the plan it waits on.
    pub fn cancel(&self, operation_id: &str) -> Result<(), Refusal> {
        self.shared.update(|window| {
            let Some(track) = window.setup_of(operation_id).filter(|track| track.live()) else {
                return Err(Refusal::NotPending);
            };
            if track.cancel_requested {
                return Err(Refusal::NotCancellable);
            }
            track.cancel_requested = true;
            track.cancellation.cancel();
            track.decline();
            Ok(())
        })
    }

    /// Stops everything this window started and waits for its workers.
    pub async fn close(&self) {
        let workers = self.shared.update(|window| {
            window.closed = true;
            window.checks.cancel();
            if let Some(track) = window.setup.as_mut().filter(|track| track.live()) {
                track.cancel_requested = true;
                track.cancellation.cancel();
                track.decline();
            }
            std::mem::take(&mut window.workers)
        });
        let joined = tokio::task::spawn_blocking(move || {
            for worker in workers {
                // A worker that panicked has nothing left to stop.
                let _ = worker.join();
            }
        });
        // The join cannot fail but by a panic, which leaves nothing to wait for.
        let _ = joined.await;
    }

    /// The engine side of the window's snapshot.
    pub fn view(&self) -> View {
        let window = lock(&self.shared.window);
        let (rows, rows_mode) = match &window.rows {
            Some((mode, rows)) => (rows.iter().map(row).collect(), Some(check_mode(*mode))),
            None => (Vec::new(), None),
        };
        let read = window.rows.as_ref().map(|(_, rows)| rows.as_slice());
        View {
            rows,
            rows_mode,
            complete: read.map(|rows| rows.iter().all(|row| row.state.usable())),
            hardware_limited: read.map(|rows| {
                rows.iter()
                    .any(|row| row.state == ItemState::Blocked(BlockedReason::Hardware))
            }),
            check: window.check.as_ref().map(|check| wire::Check {
                operation_id: check.operation_id.clone(),
                kind: check.kind,
                stage: check.stage,
            }),
            setup: window.setup.as_ref().map(run),
            details: details(read.unwrap_or_default(), window.setup.as_ref()),
        }
    }
}

/// One setup on its worker: the engine's review becomes the window's dialog,
/// and a plan that changed after its approval is asked about again.
fn run_setup(
    engines: &Engines,
    shared: &Shared,
    id: &str,
    request: &SetupRequest,
    resume: bool,
    cancellation: &Cancellation,
) {
    let Installation { mut engine } = match engines() {
        Ok(installation) => installation,
        Err(_) => {
            shared.update(|window| {
                if let Some(track) = window.setup_of(id) {
                    settle_failed(track, wire::Failure::Unexpected);
                }
            });
            return;
        }
    };
    let locations = engine.locations().clone();
    loop {
        let mut review = |plan: &SetupPlan| -> Answer {
            let digest = plan.digest();
            let (answers, answer) = mpsc::channel();
            let decided = shared.update(|window| {
                let approved = resume && window.approved.contains(digest.as_str());
                let closed = window.closed;
                let Some(track) = window.setup_of(id) else {
                    return Some(Answer::Decline);
                };
                track.hosts.extend(plan_hosts(plan));
                for entry in &plan.entries {
                    track.item(entry.item);
                }
                if closed || track.cancel_requested {
                    return Some(Answer::Decline);
                }
                if approved {
                    // A Resume of a plan this window approved is the person's act.
                    track.answered = true;
                    return Some(Answer::Approve(digest.clone()));
                }
                track.review = Some((digest.as_str().to_owned(), review_view(plan, &locations)));
                track.answers = Some(answers);
                track.answered = false;
                track.stage = RunStage::Review;
                None
            });
            // A window that closes drops the sender, which declines.
            decided.unwrap_or_else(|| answer.recv().unwrap_or(Answer::Decline))
        };
        let mut events = |event: Event| {
            shared.update(|window| {
                if let Some(track) = window.setup_of(id) {
                    take_event(track, event);
                }
            });
        };
        let report = engine.setup(request, &mut review, &mut events, cancellation);
        let again = report.outcome == Ended::PlanChanged
            && !lock(&shared.window)
                .setup_of(id)
                .is_none_or(|track| track.cancel_requested);
        if again {
            shared.update(|window| {
                if let Some(track) = window.setup_of(id) {
                    track.answered = false;
                    track.stage = RunStage::Planning;
                }
            });
            continue;
        }
        shared.update(|window| {
            if !report.rows.is_empty() {
                window.rows = Some((CheckMode::Quick, report.rows.clone()));
            }
            if report.outcome == Ended::Busy {
                // Another setup changes the item; this one never started.
                if window.setup_of(id).is_some() {
                    window.setup = None;
                }
                return;
            }
            if let Some(track) = window.setup_of(id) {
                settle(track, &report);
            }
        });
        return;
    }
}

fn take_event(track: &mut SetupTrack, event: Event) {
    if track.answered && track.stage == RunStage::Planning {
        track.stage = RunStage::Running;
    }
    match event {
        Event::Phase { item, step } => {
            let code = step.phase_code(item);
            if !track.phases.contains(&code) {
                track.phases.push(code);
            }
            let item = track.item(item);
            item.step = Some(step);
            item.retry = None;
        }
        Event::Progress {
            item,
            completed,
            total,
        } => {
            if total > 0 {
                track.item(item).progress = Some((completed.min(total), total));
            }
        }
        Event::Retrying {
            item,
            attempt,
            delay,
        } => {
            if attempt >= 2 {
                let seconds = u32::try_from(delay.as_millis().div_ceil(1000)).unwrap_or(u32::MAX);
                track.item(item).retry = Some((attempt, seconds.max(1)));
            }
        }
        Event::WaitingForServer { .. } => {}
    }
}

fn settle_failed(track: &mut SetupTrack, failure: wire::Failure) {
    track.stage = RunStage::Settled;
    track.review = None;
    track.answers = None;
    track.outcome = Some(Outcome::Failed);
    track.failure = Some(failure);
}

/// Records how the engine ended the setup: the outcome, and for each planned
/// item whether it was set up, failed, or never reached.
fn settle(track: &mut SetupTrack, report: &Report) {
    let failure = report.failure.map(failure);
    let (outcome, stopped) = match report.outcome {
        Ended::Completed => (Outcome::Completed, None),
        Ended::NothingToDo => (Outcome::NothingToDo, None),
        Ended::NeedsApproval | Ended::PlanChanged if track.cancel_requested => {
            (Outcome::Cancelled, None)
        }
        Ended::NeedsApproval => (Outcome::Rejected, None),
        Ended::Cancelled => (Outcome::Cancelled, report.item),
        Ended::Refused if report.failure == Some(FailureCategory::DiskFull) => {
            (Outcome::NotEnoughSpace, None)
        }
        Ended::Refused | Ended::Failed => (Outcome::Failed, report.item),
        _ => (Outcome::Failed, None),
    };
    if let Some(plan) = &report.plan {
        for entry in &plan.entries {
            track.item(entry.item);
        }
    }
    let ran = matches!(
        report.outcome,
        Ended::Completed | Ended::Failed | Ended::Cancelled
    );
    let mut reached = false;
    for item in &mut track.items {
        let transferred = item.progress.map_or(0, |(completed, _)| completed);
        if Some(item.item) == stopped {
            reached = true;
            item.result = Some(wire::ItemResult {
                changed: false,
                failure: Some(failure.unwrap_or(wire::Failure::Unexpected)),
                transferred_bytes: transferred,
            });
        } else if ran && !reached {
            item.result = Some(wire::ItemResult {
                changed: true,
                failure: None,
                transferred_bytes: transferred,
            });
        }
        item.retry = None;
    }
    track.stage = RunStage::Settled;
    track.review = None;
    track.answers = None;
    track.outcome = Some(outcome);
    track.failure =
        (outcome == Outcome::Failed).then(|| failure.unwrap_or(wire::Failure::Unexpected));
}

fn plan_hosts(plan: &SetupPlan) -> impl Iterator<Item = String> + '_ {
    plan.entries
        .iter()
        .flat_map(|entry| &entry.source_hosts)
        .map(|host| host.as_str().to_owned())
}

/// The entry that first plans the same download as `entry`, and the entry's own key.
type DownloadKey = (Destination, String);

fn download_key(destination: Option<Destination>, version: Option<&String>) -> Option<DownloadKey> {
    Some((destination?, version?.clone()))
}

/// Each planned model whose licence bars commercial use, with the licence's display name
/// as the plan carries it; roles sharing a model name it once.
fn licences(entry: &PlanEntry) -> Vec<wire::Licence> {
    let found: BTreeSet<wire::Licence> = entry
        .parts
        .iter()
        .filter(|part| {
            part.advisories
                .contains(&Advisory::LicenceCommercialUseBarred)
        })
        .filter_map(|part| {
            let model = part.target_version.as_deref()?.split('@').next()?;
            Some(wire::Licence {
                model: model.to_owned(),
                licence: part.licence.as_ref()?.name.clone(),
            })
        })
        .collect();
    found.into_iter().collect()
}

fn review_view(plan: &SetupPlan, locations: &Locations) -> wire::Review {
    let mut first_by_download: BTreeMap<DownloadKey, ItemId> = BTreeMap::new();
    let entries = plan
        .entries
        .iter()
        .map(|entry| {
            let shares_download_with =
                download_key(entry.destination, entry.target_version.as_ref()).and_then(|key| {
                    let first = *first_by_download.entry(key).or_insert(entry.item);
                    (first != entry.item).then(|| first.as_str().to_owned())
                });
            let mut seen = BTreeSet::new();
            let parts = entry
                .parts
                .iter()
                .map(|part| {
                    let shared = download_key(part.destination, part.target_version.as_ref())
                        .is_some_and(|key| !seen.insert(key));
                    wire::PlanPart {
                        part: part.part_id.clone(),
                        download_bytes: part
                            .download_bytes
                            .map(|bytes| if shared { 0 } else { bytes }),
                    }
                })
                .collect();
            wire::PlanEntry {
                item: entry.item.as_str().to_owned(),
                download_bytes: entry.download_bytes,
                source_hosts: entry
                    .source_hosts
                    .iter()
                    .map(|host| host.as_str().to_owned())
                    .collect(),
                destination: entry
                    .destination
                    .map(|destination| locations.destination(destination).display().to_string()),
                installs_outside_program: entry.installs_outside_program,
                shares_download_with,
                advisories: entry
                    .advisories
                    .iter()
                    .map(|advisory| advice(*advisory))
                    .collect(),
                licences: licences(entry),
                parts,
            }
        })
        .collect();
    wire::Review {
        plan_digest: plan.digest().as_str().to_owned(),
        entries,
        known_download_bytes: plan.known_download_bytes(),
        has_unknown_size: plan.has_unknown_size(),
        installs_outside_program: plan.installs_outside_program(),
        required_bytes: plan.space.required_bytes,
        free_bytes: plan.space.free_bytes,
        space_sufficient: plan.space.sufficient(),
    }
}

fn run(track: &SetupTrack) -> wire::Run {
    let settled = track.stage == RunStage::Settled;
    wire::Run {
        operation_id: track.operation_id.clone(),
        stage: track.stage,
        review: track
            .review
            .as_ref()
            .filter(|_| track.stage == RunStage::Review)
            .map(|(_, review)| review.clone()),
        items: track
            .items
            .iter()
            .map(|item| wire::ItemProgress {
                item: item.item.as_str().to_owned(),
                step: item.step.map(step),
                completed: item.progress.map(|(completed, _)| completed),
                total: item.progress.map(|(_, total)| total),
                retry: item
                    .retry
                    .filter(|_| !settled)
                    .map(|(attempt, delay_s)| wire::Retry { attempt, delay_s }),
                result: item.result.clone(),
            })
            .collect(),
        cancellable: !settled && !track.cancel_requested,
        cancel_requested: track.cancel_requested,
        outcome: track.outcome,
        failure: track.failure,
    }
}

/// The redacted report "Copy details" puts on the clipboard: closed values,
/// versions, the operation id, phase codes and hosts, and nothing else.
fn details(rows: &[StatusRow], setup: Option<&SetupTrack>) -> String {
    let mut lines = vec!["Cadrumo setup details".to_owned()];
    if let Some(track) = setup {
        lines.push(format!("operation: {}", track.operation_id));
    }
    for row in rows {
        let mut parts = vec![
            format!("item: {}", row.item),
            format!("state: {}", row.state.code()),
            format!("check: {}", code(check_mode(row.mode))),
        ];
        let reason = match row.state {
            ItemState::Stale(reason) => Some(code(stale(reason))),
            ItemState::Blocked(reason) => Some(code(blocked(reason))),
            ItemState::Failed(category) => Some(code(failure(category))),
            _ => None,
        };
        if let Some(reason) = reason {
            parts.push(format!("reason: {reason}"));
        }
        if let Some(version) = &row.version {
            parts.push(format!("version: {version}"));
        }
        if let Some(note) = row.note {
            parts.push(format!("note: {}", code(self::note(note))));
        }
        lines.push(parts.join("; "));
    }
    if let Some(track) = setup {
        if !track.phases.is_empty() {
            lines.push(format!("phases: {}", track.phases.join(", ")));
        }
        if !track.hosts.is_empty() {
            let hosts: Vec<&str> = track.hosts.iter().map(String::as_str).collect();
            lines.push(format!("hosts: {}", hosts.join(", ")));
        }
    }
    lines.join("\n") + "\n"
}

/// The code a closed value is serialized as.
fn code(value: impl serde::Serialize) -> String {
    match serde_json::to_value(value) {
        Ok(serde_json::Value::String(code)) => code,
        _ => String::new(),
    }
}

// ── The engine's codes as the window's ──────────────────────────────────────

fn row(row: &StatusRow) -> wire::Row {
    let (state, stale_reason, blocked_reason, failure_category) = match row.state {
        ItemState::Absent => (wire::State::Absent, None, None, None),
        ItemState::Provisioning => (wire::State::Provisioning, None, None, None),
        ItemState::Verifying => (wire::State::Verifying, None, None, None),
        ItemState::Ready => (wire::State::Ready, None, None, None),
        ItemState::Stale(reason) => (wire::State::Stale, Some(stale(reason)), None, None),
        ItemState::Failed(category) => (wire::State::Failed, None, None, Some(failure(category))),
        ItemState::Blocked(reason) => (wire::State::Blocked, None, Some(blocked(reason)), None),
        ItemState::Unknown => (wire::State::Unknown, None, None, None),
    };
    wire::Row {
        item: row.item.as_str().to_owned(),
        kind: match row.item {
            ItemId::Browser => wire::ItemKind::Browser,
            ItemId::LocalAi => wire::ItemKind::LocalAi,
        },
        mode: check_mode(row.mode),
        state,
        stale_reason,
        blocked_reason,
        failure: failure_category,
        recovery: row.recovery.map(recovery),
        recovery_action_id: row.recovery_action_id().map(str::to_owned),
        version: row.version.clone(),
        size_bytes: row.size_estimate_bytes,
        note: row.note.map(note),
    }
}

fn check_mode(mode: CheckMode) -> wire::CheckMode {
    match mode {
        CheckMode::Quick => wire::CheckMode::Quick,
        CheckMode::Full => wire::CheckMode::Full,
    }
}

fn stale(reason: StaleReason) -> wire::StaleReason {
    match reason {
        StaleReason::OlderRevision => wire::StaleReason::OlderRevision,
        StaleReason::DifferentModelVersion => wire::StaleReason::DifferentModelVersion,
        StaleReason::ProgramTooOld => wire::StaleReason::ProgramTooOld,
    }
}

fn blocked(reason: BlockedReason) -> wire::BlockedReason {
    match reason {
        BlockedReason::Offline => wire::BlockedReason::Offline,
        BlockedReason::NeedsPerson => wire::BlockedReason::NeedsPerson,
        BlockedReason::Hardware => wire::BlockedReason::Hardware,
        BlockedReason::NotInThisBuild => wire::BlockedReason::NotInThisBuild,
    }
}

fn note(note: Note) -> wire::Note {
    match note {
        Note::DownloadedNotLoaded => wire::Note::DownloadedNotLoaded,
        Note::OwnNetworkSettings => wire::Note::OwnNetworkSettings,
    }
}

fn recovery(action: RecoveryAction) -> wire::Recovery {
    match action {
        RecoveryAction::SetUp => wire::Recovery::SetUp,
        RecoveryAction::Update => wire::Recovery::Update,
        RecoveryAction::TryAgain => wire::Recovery::TryAgain,
        RecoveryAction::Resume => wire::Recovery::Resume,
        RecoveryAction::CheckAgain => wire::Recovery::CheckAgain,
    }
}

fn step(step: SetupStep) -> wire::Step {
    match step {
        SetupStep::Plan => wire::Step::Plan,
        SetupStep::Preflight => wire::Step::Preflight,
        SetupStep::Download => wire::Step::Download,
        SetupStep::Install => wire::Step::Install,
        SetupStep::Verify => wire::Step::Verify,
        SetupStep::Cleanup => wire::Step::Cleanup,
    }
}

fn advice(advisory: Advisory) -> wire::Advisory {
    match advisory {
        Advisory::FitExceedsMeasuredHeadroom => wire::Advisory::FitExceedsMeasuredHeadroom,
        Advisory::FitUnverified => wire::Advisory::FitUnverified,
        Advisory::LicenceCommercialUseBarred => wire::Advisory::LicenceCommercialUseBarred,
        Advisory::LicenceUnverified => wire::Advisory::LicenceUnverified,
        Advisory::OverrideBelowContextFloor => wire::Advisory::OverrideBelowContextFloor,
        Advisory::OverrideNotInCatalogue => wire::Advisory::OverrideNotInCatalogue,
    }
}

fn failure(category: FailureCategory) -> wire::Failure {
    match category {
        FailureCategory::Offline => wire::Failure::Offline,
        FailureCategory::HostUnreachable => wire::Failure::HostUnreachable,
        FailureCategory::SecureConnectionFailed => wire::Failure::SecureConnectionFailed,
        FailureCategory::BlockedByNetwork => wire::Failure::BlockedByNetwork,
        FailureCategory::DiskFull => wire::Failure::DiskFull,
        FailureCategory::NoPermission => wire::Failure::NoPermission,
        FailureCategory::DamagedDownload => wire::Failure::DamagedDownload,
        FailureCategory::NotEnoughMemory => wire::Failure::NotEnoughMemory,
        FailureCategory::MemoryBusy => wire::Failure::MemoryBusy,
        FailureCategory::ProgramMissing => wire::Failure::ProgramMissing,
        FailureCategory::ProgramNotRunning => wire::Failure::ProgramNotRunning,
        FailureCategory::Interrupted => wire::Failure::Interrupted,
        FailureCategory::NeedsSignIn => wire::Failure::NeedsSignIn,
        FailureCategory::NotInThisBuild => wire::Failure::NotInThisBuild,
        FailureCategory::Cancelled => wire::Failure::Cancelled,
        FailureCategory::Unexpected => wire::Failure::Unexpected,
    }
}

#[cfg(test)]
#[path = "components_tests.rs"]
mod tests;
