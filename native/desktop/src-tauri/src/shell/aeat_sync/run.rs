//! The run the AEAT sync page follows: a queue of items over the asked areas,
//! held by the profile host so it survives page navigation and reattaches on a
//! repeat start. Items run one at a time in the fixed area order; a stop lets
//! the item in flight settle and starts nothing further, and an ended AEAT
//! session pauses the run at that item until the person signs in again.
//!
//! The run keeps item addresses and closed states only. Which operation an
//! item submits, and how its settlement reads, belong to the driver.
use super::admitted::Area;
use super::outcome::{self, Counts, Outcome, Reason};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};
use std::future::Future;
use std::sync::{Arc, Mutex};

/// What one item reads, as the driver submits it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) enum Step {
    /// The census session the profile page also opens.
    Census,
    /// One identity check of the profile's own tax number.
    Verify(&'static str),
    Notifications,
    /// The VAT balance carried forward over every year the backend serves.
    Vat,
    /// Which forms AEAT holds filed, by year.
    Discover,
    /// The filed declarations of one year, for the forms discovered in it.
    Filed {
        year: u16,
        forms: Vec<String>,
    },
}

/// How an item settled, with what the driver read beside its outcome.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct Settled {
    pub(crate) outcome: Outcome,
    pub(crate) counts: Counts,
    /// For a discovery: the forms found, by year.
    pub(crate) discovered: Option<BTreeMap<u16, BTreeSet<String>>>,
    /// For the census: its comparison waits for the person.
    pub(crate) review_pending: bool,
    /// Its AEAT session ended: the run pauses at it, whatever its outcome.
    pub(crate) session_ended: bool,
}
impl Settled {
    pub(crate) fn of(outcome: Outcome) -> Self {
        Self {
            outcome,
            ..Self::default()
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum ItemState {
    Waiting,
    Running,
    Brought,
    NothingFound,
    Failed,
    Unknown,
    NotStarted,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum AreaState {
    Waiting,
    Running,
    Finished,
    NotStarted,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum RunState {
    Running,
    Stopping,
    Stopped,
    Paused,
    Done,
}

#[derive(Clone, Debug)]
pub(crate) struct Item {
    pub(crate) id: u32,
    pub(crate) year: Option<u16>,
    pub(crate) step: Step,
    pub(crate) state: ItemState,
    pub(crate) reason: Option<Reason>,
    pub(crate) counts: Counts,
    pub(crate) review_pending: bool,
    /// A discovery the window does not see unless it fails: the area's parts
    /// are the years it finds.
    hidden: bool,
}
impl Item {
    fn settled(&self) -> bool {
        !matches!(
            self.state,
            ItemState::Waiting | ItemState::Running | ItemState::NotStarted
        )
    }
    /// How the item settled; none while it has not.
    pub(crate) fn outcome(&self) -> Option<Outcome> {
        Some(match self.state {
            ItemState::Brought => Outcome::Brought,
            ItemState::NothingFound => Outcome::NothingFound,
            ItemState::Failed => Outcome::Failed(self.reason.unwrap_or(Reason::Other)),
            ItemState::Unknown => Outcome::Unknown,
            ItemState::Waiting | ItemState::Running | ItemState::NotStarted => return None,
        })
    }
}

#[derive(Clone, Debug)]
pub(crate) struct AreaRun {
    pub(crate) area: Area,
    pub(crate) items: Vec<Item>,
}
impl AreaRun {
    fn state(&self) -> AreaState {
        let items = &self.items;
        if items.iter().any(|i| i.state == ItemState::Running) {
            AreaState::Running
        } else if items.iter().any(|i| i.state == ItemState::Waiting) {
            if items.iter().any(Item::settled) {
                AreaState::Running
            } else {
                AreaState::Waiting
            }
        } else if items.iter().any(Item::settled) {
            AreaState::Finished
        } else {
            AreaState::NotStarted
        }
    }
    /// The worst outcome of the items settled so far; none before any.
    pub(crate) fn outcome(&self) -> Option<Outcome> {
        outcome::worst(self.items.iter().filter_map(Item::outcome))
    }
}

/// The window's view of one item: its address, year, state and reason.
#[derive(Debug, PartialEq, Eq, Serialize)]
pub(crate) struct ItemView {
    pub(crate) item: u32,
    pub(crate) year: Option<u16>,
    pub(crate) state: ItemState,
    pub(crate) reason: Option<Reason>,
}
#[derive(Debug, PartialEq, Eq, Serialize)]
pub(crate) struct AreaView {
    pub(crate) area: Area,
    pub(crate) state: AreaState,
    /// The worst of the items settled so far, in the window's words.
    pub(crate) outcome: Option<&'static str>,
    pub(crate) items: Vec<ItemView>,
}
#[derive(Debug, PartialEq, Eq, Serialize)]
pub(crate) struct Snapshot {
    pub(crate) state: RunState,
    pub(crate) areas: Vec<AreaView>,
}

/// The forms a discovery found for each year, in year order.
type Parts = Vec<(u16, Vec<String>)>;

/// Why the run refused a person's request.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Refusal {
    /// The address names nothing in this run.
    Invalid,
    /// Nothing there may be read again now.
    Refused,
    /// The part may already have been brought and the person was not told.
    Unknown,
}

pub(crate) struct Run {
    pub(crate) state: RunState,
    pub(crate) areas: Vec<AreaRun>,
    /// Whether a driver loop is following the queue.
    driving: bool,
    next_id: u32,
}

impl Run {
    pub(crate) fn new(plan: &super::Plan) -> Self {
        let mut run = Self {
            state: RunState::Running,
            areas: Vec::new(),
            driving: false,
            next_id: 0,
        };
        for &area in &plan.areas {
            let steps: Vec<(Step, bool)> = match area {
                Area::Census => vec![(Step::Census, false)],
                Area::Identity => area
                    .definitions()
                    .iter()
                    .map(|id| (Step::Verify(id), false))
                    .collect(),
                Area::Notifications => vec![(Step::Notifications, false)],
                Area::Vat => vec![(Step::Vat, false)],
                Area::Filed => vec![(Step::Discover, true)],
            };
            let items = steps
                .into_iter()
                .map(|(step, hidden)| run.item(None, step, ItemState::Waiting, hidden))
                .collect();
            run.areas.push(AreaRun { area, items });
        }
        run
    }
    fn item(&mut self, year: Option<u16>, step: Step, state: ItemState, hidden: bool) -> Item {
        let id = self.next_id;
        self.next_id += 1;
        Item {
            id,
            year,
            step,
            state,
            reason: None,
            counts: Counts::default(),
            review_pending: false,
            hidden,
        }
    }

    /// What the window is shown.
    pub(crate) fn snapshot(&self) -> Snapshot {
        Snapshot {
            state: self.state,
            areas: self
                .areas
                .iter()
                .map(|area| AreaView {
                    area: area.area,
                    state: area.state(),
                    outcome: area.outcome().map(Outcome::word),
                    items: area
                        .items
                        .iter()
                        .filter(|item| !item.hidden)
                        .map(|item| ItemView {
                            item: item.id,
                            year: item.year,
                            state: item.state,
                            reason: item.reason,
                        })
                        .collect(),
                })
                .collect(),
        }
    }

    /// Whether the run still moves: it waits for a resume, or an item is in
    /// flight or waits its turn. A run whose last item settled is finished
    /// even before its driver lets go, so a start then holds a fresh one.
    pub(crate) fn active(&self) -> bool {
        match self.state {
            RunState::Paused => true,
            RunState::Running | RunState::Stopping => self
                .areas
                .iter()
                .flat_map(|area| area.items.iter())
                .any(|item| matches!(item.state, ItemState::Waiting | ItemState::Running)),
            RunState::Stopped | RunState::Done => false,
        }
    }

    /// Claims the queue for one driver loop; false when one already follows it.
    pub(crate) fn claim(&mut self) -> bool {
        !std::mem::replace(&mut self.driving, true)
    }

    /// The next item to run, marked running, in area order. A stop asked for
    /// ends the run here, before anything further starts, and an empty queue
    /// ends it as done; either releases the driver.
    pub(crate) fn next(&mut self) -> Option<(u32, Step)> {
        if self.state == RunState::Stopping {
            self.not_started();
            self.state = RunState::Stopped;
        }
        if self.state != RunState::Running {
            self.driving = false;
            return None;
        }
        let found = self
            .areas
            .iter_mut()
            .flat_map(|area| area.items.iter_mut())
            .find(|item| item.state == ItemState::Waiting);
        match found {
            Some(item) => {
                item.state = ItemState::Running;
                Some((item.id, item.step.clone()))
            }
            None => {
                self.state = RunState::Done;
                self.driving = false;
                None
            }
        }
    }

    fn not_started(&mut self) {
        for item in self.areas.iter_mut().flat_map(|area| area.items.iter_mut()) {
            if item.state == ItemState::Waiting {
                item.state = ItemState::NotStarted;
                item.hidden = false;
            }
        }
    }

    /// Records how item `id` settled. An ended AEAT session pauses the run at
    /// that item, whatever its outcome; a discovery is replaced by one item
    /// per year it found.
    pub(crate) fn settle(&mut self, id: u32, settled: Settled) {
        let mut fresh: Option<(usize, Parts)> = None;
        let Some((index, item)) = self.areas.iter_mut().enumerate().find_map(|(index, area)| {
            area.items
                .iter_mut()
                .find(|i| i.id == id)
                .map(|i| (index, i))
        }) else {
            return;
        };
        if item.state != ItemState::Running {
            return;
        }
        let Settled {
            outcome,
            counts,
            discovered,
            review_pending,
            session_ended,
        } = settled;
        // An ended session pauses the run whatever the item kept: an item that
        // kept nothing is read again on resume, and an unknown one never is.
        let pause = session_ended || outcome == Outcome::Failed(Reason::SessionEnded);
        match (&item.step, outcome, discovered) {
            (Step::Discover, Outcome::Brought | Outcome::NothingFound, Some(found)) => {
                let parts = found
                    .into_iter()
                    .map(|(year, forms)| (year, forms.into_iter().collect()))
                    .collect();
                fresh = Some((index, parts));
            }
            (_, outcome, _) => {
                item.hidden = false;
                item.counts = counts;
                item.review_pending = review_pending;
                let (state, reason) = match outcome {
                    Outcome::Brought => (ItemState::Brought, None),
                    Outcome::NothingFound => (ItemState::NothingFound, None),
                    Outcome::Failed(reason) => (ItemState::Failed, Some(reason)),
                    Outcome::Unknown => (ItemState::Unknown, None),
                };
                item.state = state;
                item.reason = reason;
            }
        }
        if pause {
            self.not_started();
            self.state = RunState::Paused;
        }
        if let Some((index, parts)) = fresh {
            let mut items = Vec::new();
            for (year, forms) in parts {
                let state = if forms.is_empty() {
                    ItemState::NothingFound
                } else {
                    ItemState::Waiting
                };
                let step = Step::Filed { year, forms };
                items.push(self.item(Some(year), step, state, false));
            }
            if self.state != RunState::Running {
                for item in &mut items {
                    if item.state == ItemState::Waiting {
                        item.state = ItemState::NotStarted;
                    }
                }
            }
            self.areas[index].items = items;
        }
    }

    /// Asks the run to stop after the item in flight. A run no driver follows
    /// stops at once.
    pub(crate) fn stop(&mut self) {
        match self.state {
            RunState::Running if self.driving => self.state = RunState::Stopping,
            RunState::Running | RunState::Paused => {
                self.not_started();
                self.state = RunState::Stopped;
            }
            _ => {}
        }
    }

    /// Carries a paused run on from the first item not brought: the item the
    /// session ended at and those never started. An item whose outcome is
    /// unknown is never run again here. True when a driver must follow it.
    pub(crate) fn resume(&mut self) -> Result<bool, Refusal> {
        match self.state {
            RunState::Running | RunState::Stopping => Ok(false),
            RunState::Paused => {
                for item in self.areas.iter_mut().flat_map(|a| a.items.iter_mut()) {
                    let ended = item.state == ItemState::Failed
                        && item.reason == Some(Reason::SessionEnded);
                    if ended || item.state == ItemState::NotStarted {
                        item.state = ItemState::Waiting;
                        item.reason = None;
                    }
                }
                self.state = RunState::Running;
                Ok(self.claim())
            }
            RunState::Stopped | RunState::Done => Err(Refusal::Refused),
        }
    }

    /// Reads one item again on the person's request, or every part of `area`
    /// that was not brought. A part whose outcome is unknown is read again
    /// only once the person was told it may already have been brought. True
    /// when a driver must follow the run.
    pub(crate) fn retry(
        &mut self,
        area: Area,
        item: Option<u32>,
        acknowledged_unknown: bool,
    ) -> Result<bool, Refusal> {
        if self.state == RunState::Paused {
            return Err(Refusal::Refused);
        }
        let area = self
            .areas
            .iter_mut()
            .find(|run| run.area == area)
            .ok_or(Refusal::Invalid)?;
        let again = |i: &Item| {
            matches!(
                i.state,
                ItemState::Failed | ItemState::Unknown | ItemState::NotStarted
            )
        };
        let chosen: Vec<usize> = match item {
            Some(id) => {
                let index = area
                    .items
                    .iter()
                    .position(|i| i.id == id && !i.hidden)
                    .ok_or(Refusal::Invalid)?;
                if !again(&area.items[index]) {
                    return Err(Refusal::Refused);
                }
                vec![index]
            }
            None => (0..area.items.len())
                .filter(|&index| again(&area.items[index]))
                .collect(),
        };
        if chosen.is_empty() {
            return Err(Refusal::Refused);
        }
        if !acknowledged_unknown
            && chosen
                .iter()
                .any(|&index| area.items[index].state == ItemState::Unknown)
        {
            return Err(Refusal::Unknown);
        }
        for index in chosen {
            let item = &mut area.items[index];
            item.state = ItemState::Waiting;
            item.reason = None;
            item.counts = Counts::default();
            item.review_pending = false;
        }
        if matches!(self.state, RunState::Stopped | RunState::Done) {
            self.state = RunState::Running;
        }
        Ok(self.claim())
    }

    /// Releases the queue without a driver, as when the driver loop ends
    /// because the person signed out.
    pub(crate) fn release(&mut self) {
        self.driving = false;
    }
}

/// Runs the items one at a time: the one seam between the queue and the
/// relay, so the queue is tested without one.
pub(crate) trait Driver: Send + Sync + 'static {
    /// Runs `step` to its settlement. A wait has no limit of its own: only a
    /// lost reply or an unknown effect makes an item unknown.
    fn run(&self, step: Step) -> impl Future<Output = Settled> + Send;
    /// Whether the person the run was started for is still the one signed in.
    fn current(&self) -> impl Future<Output = bool> + Send;
    /// Cues the window that the run changed.
    fn changed(&self);
}

pub(crate) fn lock(run: &Mutex<Run>) -> std::sync::MutexGuard<'_, Run> {
    run.lock().unwrap_or_else(|e| e.into_inner())
}

/// Follows the queue until it stops, pauses, is done or its person signs
/// out. Call only after [`Run::claim`] answered true.
pub(crate) async fn drive<D: Driver>(run: Arc<Mutex<Run>>, driver: Arc<D>) {
    loop {
        if !driver.current().await {
            lock(&run).release();
            driver.changed();
            return;
        }
        let next = lock(&run).next();
        driver.changed();
        let Some((id, step)) = next else {
            return;
        };
        let settled = driver.run(step).await;
        lock(&run).settle(id, settled);
        driver.changed();
    }
}
