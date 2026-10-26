//! Derived item states: never stored, always computed from what a check observed, any
//! setup running now, and how the last setup of the item ended.
//!
//! A running setup wins, then a check that could not read gives `unknown`. A computer
//! below the model floor or a build without the item decides next, because Resume could
//! not change it. An item observed present is ready: a setup cut off during its cleanup
//! left it usable. Otherwise an interrupted setup reads `failed interrupted` with Resume,
//! whatever else the check observed, so the person resumes the plan they approved instead
//! of being offered a different act. Then the observation decides, and a failure the last
//! finished setup recorded shows only while the item is still absent. A receipt is
//! evidence a check compares against, never an observation, so no receipt can make an
//! item ready.

use super::{
    failure::FailureCategory,
    items::{ItemDeclaration, ItemId},
    network::{NetworkReport, Reachability},
};
use serde::{Deserialize, Serialize, Serializer, ser::SerializeMap};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CheckMode {
    /// Local facts only: no network and no model load, bounded at 2 s for every item.
    Quick,
    /// Also reaches the network and exercises the item.
    Full,
}

/// Why an item cannot be set up right now.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BlockedReason {
    Offline,
    /// An approval or an outside act the person must give.
    NeedsPerson,
    /// This computer is below the model floor: a limit, not a failure to fix.
    Hardware,
    NotInThisBuild,
}

/// How a usable item differs from what this version requires or was tested with: the
/// browser's revision or the local AI program's version. A model is the one the person
/// selected and the program verified, with no pinned version to differ from.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StaleReason {
    OlderRevision,
    ProgramTooOld,
}

/// The one button a surface offers for an item's state.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RecoveryAction {
    SetUp,
    Update,
    TryAgain,
    Resume,
    CheckAgain,
    /// The local AI's set-up, update, retry or resume, offered by an engine that serves
    /// it read-only: only the desktop sets the local AI up.
    SetUpInDesktop,
}

/// The ordered steps of one item's setup.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SetupStep {
    Plan,
    Preflight,
    Download,
    Install,
    Verify,
    Cleanup,
}

impl SetupStep {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Plan => "plan",
            Self::Preflight => "preflight",
            Self::Download => "download",
            Self::Install => "install",
            Self::Verify => "verify",
            Self::Cleanup => "cleanup",
        }
    }

    /// The phase code a setup publishes for this step of `item`.
    pub fn phase_code(self, item: ItemId) -> String {
        format!("dependencies.setup.{item}.{}", self.as_str())
    }
}

/// What a check observed, with exactly the reason its outcome needs. `Present` and
/// `Differs` rest on something observed on this computer, never on a receipt alone.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Observation {
    Present,
    Differs { stale: StaleReason },
    Absent,
    Unreadable,
    Blocked(BlockedReason),
    Failed(FailureCategory),
}

impl Observation {
    pub fn usable(self) -> bool {
        matches!(self, Self::Present | Self::Differs { .. })
    }
}

/// One check's answer for an item or a part of one.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Reading {
    pub mode: CheckMode,
    pub observation: Observation,
    pub version: Option<String>,
}

impl Reading {
    pub fn new(mode: CheckMode, observation: Observation) -> Self {
        Self {
            mode,
            observation,
            version: None,
        }
    }

    /// The local AI's one reading: the worst of its parts', the program's first among
    /// equals. A computer below the model floor decides first, because nothing set up here
    /// changes it; then a part that could not be read, a failure, a block, anything
    /// missing, and last anything that differs from what was tested. Only when every part
    /// is present is the local AI present. The version is the program's.
    pub fn worst_of_parts(mode: CheckMode, program: &Reading, models: &[Reading]) -> Reading {
        let parts: Vec<&Reading> = std::iter::once(program).chain(models).collect();
        let first = |wanted: fn(&Observation) -> bool| {
            parts.iter().map(|part| part.observation).find(&wanted)
        };
        let decisive = first(|o| matches!(o, Observation::Blocked(BlockedReason::Hardware)))
            .or_else(|| first(|o| matches!(o, Observation::Unreadable)))
            .or_else(|| first(|o| matches!(o, Observation::Failed(_))))
            .or_else(|| first(|o| matches!(o, Observation::Blocked(_))))
            .or_else(|| first(|o| matches!(o, Observation::Absent)))
            .or_else(|| first(|o| matches!(o, Observation::Differs { .. })));
        Reading {
            mode,
            observation: decisive.unwrap_or(Observation::Present),
            version: program.version.clone(),
        }
    }

    /// A full check's reading held against the item's host preflight: a usable item stays
    /// usable offline, while one that still needs the network becomes blocked offline or
    /// fails with the preflight's category.
    pub fn held_by_network(self, report: &NetworkReport) -> Reading {
        if self.observation.usable() {
            return self;
        }
        let observation = match report.outcome() {
            Reachability::Reachable => return self,
            Reachability::Offline => Observation::Blocked(BlockedReason::Offline),
            other => Observation::Failed(
                other
                    .failure_category()
                    .unwrap_or(FailureCategory::Unexpected),
            ),
        };
        Reading {
            observation,
            ..self
        }
    }
}

/// An item's derived state, carrying exactly the reason it requires.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ItemState {
    Absent,
    Provisioning,
    Verifying,
    Ready,
    Stale(StaleReason),
    Failed(FailureCategory),
    Blocked(BlockedReason),
    Unknown,
}

impl ItemState {
    pub fn code(self) -> &'static str {
        match self {
            Self::Absent => "absent",
            Self::Provisioning => "provisioning",
            Self::Verifying => "verifying",
            Self::Ready => "ready",
            Self::Stale(_) => "stale",
            Self::Failed(_) => "failed",
            Self::Blocked(_) => "blocked",
            Self::Unknown => "unknown",
        }
    }

    pub fn usable(self) -> bool {
        matches!(self, Self::Ready | Self::Stale(_))
    }
}

/// What a running or interrupted setup of an item says about it right now.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Activity {
    /// No setup is changing the item.
    Idle,
    /// A live setup holds the item's lock and has reached this step.
    Running(SetupStep),
    /// A setup began changing the item and its process ended without finishing.
    Interrupted,
}

/// The derived, renderer-neutral status of one item. Every surface renders this row:
/// the state with exactly its reason and at most one recovery button.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StatusRow {
    pub item: ItemId,
    pub mode: CheckMode,
    pub state: ItemState,
    pub version: Option<String>,
    pub size_estimate_bytes: Option<u64>,
    pub recovery: Option<RecoveryAction>,
}

impl StatusRow {
    /// The operator action the recovery button performs, when there is one.
    pub fn recovery_action_id(&self) -> Option<&'static str> {
        self.recovery
            .map(|_| self.item.declaration().recovery_action)
    }
}

impl Serialize for StatusRow {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(None)?;
        map.serialize_entry("item_id", &self.item)?;
        map.serialize_entry("mode", &self.mode)?;
        map.serialize_entry("state", self.state.code())?;
        match self.state {
            ItemState::Stale(reason) => map.serialize_entry("stale_reason", &reason)?,
            ItemState::Blocked(reason) => map.serialize_entry("blocked_reason", &reason)?,
            ItemState::Failed(category) => map.serialize_entry("failure_category", &category)?,
            _ => {}
        }
        if let Some(version) = &self.version {
            map.serialize_entry("version", version)?;
        }
        if let Some(size) = self.size_estimate_bytes {
            map.serialize_entry("size_estimate_bytes", &size)?;
        }
        if let Some(recovery) = self.recovery {
            map.serialize_entry("recovery", &recovery)?;
            map.serialize_entry("recovery_action_id", &self.recovery_action_id())?;
        }
        map.end()
    }
}

/// Derives one item's row from its reading, any running or interrupted setup, and the
/// category its last setup recorded when it did not end ready.
pub fn derive_row(
    declaration: &ItemDeclaration,
    reading: &Reading,
    activity: Activity,
    last_failure: Option<FailureCategory>,
) -> StatusRow {
    let state = match (activity, reading.observation) {
        (Activity::Running(SetupStep::Verify), _) => ItemState::Verifying,
        (Activity::Running(_), _) => ItemState::Provisioning,
        (_, Observation::Unreadable) => ItemState::Unknown,
        (
            _,
            Observation::Blocked(
                reason @ (BlockedReason::Hardware | BlockedReason::NotInThisBuild),
            ),
        ) => ItemState::Blocked(reason),
        (_, Observation::Present) => ItemState::Ready,
        (Activity::Interrupted, _) => ItemState::Failed(FailureCategory::Interrupted),
        // A setup that failed outranks what the item differs by: the Update a stale row
        // offers would run the very transfer that failed, so the row keeps the failure
        // and its Try again until a setup ends another way.
        (_, Observation::Differs { stale, .. }) => match last_failure {
            Some(category) => ItemState::Failed(category),
            None => ItemState::Stale(stale),
        },
        (_, Observation::Failed(category)) => ItemState::Failed(category),
        (_, Observation::Blocked(reason)) => ItemState::Blocked(reason),
        (_, Observation::Absent) => match last_failure {
            Some(category) => ItemState::Failed(category),
            None => ItemState::Absent,
        },
    };
    StatusRow {
        item: declaration.id,
        mode: reading.mode,
        state,
        version: reading.version.clone(),
        size_estimate_bytes: None,
        recovery: recovery_for(state),
    }
}

/// The one button a state offers, or `None` when the person has nothing to do: a
/// computer below the model floor and a build without the item have no button.
pub fn recovery_for(state: ItemState) -> Option<RecoveryAction> {
    match state {
        ItemState::Ready | ItemState::Provisioning | ItemState::Verifying => None,
        ItemState::Unknown => Some(RecoveryAction::CheckAgain),
        ItemState::Absent => Some(RecoveryAction::SetUp),
        ItemState::Stale(_) => Some(RecoveryAction::Update),
        ItemState::Blocked(BlockedReason::Offline) => Some(RecoveryAction::CheckAgain),
        ItemState::Blocked(BlockedReason::NeedsPerson) => Some(RecoveryAction::SetUp),
        ItemState::Blocked(BlockedReason::Hardware | BlockedReason::NotInThisBuild) => None,
        ItemState::Failed(FailureCategory::NotInThisBuild | FailureCategory::NotEnoughMemory) => {
            None
        }
        ItemState::Failed(FailureCategory::Interrupted) => Some(RecoveryAction::Resume),
        ItemState::Failed(_) => Some(RecoveryAction::TryAgain),
    }
}

/// Whether Cadrumo is set up: every item ready or stale.
pub fn setup_complete(rows: &[StatusRow]) -> bool {
    rows.iter().all(|row| row.state.usable())
}

/// The items a setup with no explicit request covers, in setup order: every item whose
/// row offers the person an action this engine performs. That leaves out an item that is
/// ready or already running, one held back by this computer or this build, blocked or
/// failed, and one only the desktop sets up.
pub fn items_to_set_up(rows: &[StatusRow]) -> Vec<ItemId> {
    ItemId::ALL
        .into_iter()
        .filter(|item| {
            rows.iter().any(|row| {
                row.item == *item
                    && row
                        .recovery
                        .is_some_and(|recovery| recovery != RecoveryAction::SetUpInDesktop)
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        provisioning::{
            items::{BROWSER, LOCAL_AI},
            network::HostCheck,
        },
        value::HostName,
    };

    fn reading(observation: Observation) -> Reading {
        Reading::new(CheckMode::Quick, observation)
    }

    fn row(
        observation: Observation,
        activity: Activity,
        last: Option<FailureCategory>,
    ) -> StatusRow {
        derive_row(&BROWSER, &reading(observation), activity, last)
    }

    #[test]
    fn a_running_setup_wins_then_unreadable_then_the_observation() {
        let present = Observation::Present;
        assert_eq!(
            row(present, Activity::Running(SetupStep::Download), None).state,
            ItemState::Provisioning
        );
        assert_eq!(
            row(
                Observation::Absent,
                Activity::Running(SetupStep::Verify),
                None
            )
            .state,
            ItemState::Verifying
        );
        assert_eq!(
            row(
                Observation::Unreadable,
                Activity::Idle,
                Some(FailureCategory::DiskFull)
            )
            .state,
            ItemState::Unknown
        );
        assert_eq!(row(present, Activity::Idle, None).state, ItemState::Ready);
        assert_eq!(
            row(present, Activity::Interrupted, None).state,
            ItemState::Ready,
            "a setup cut off during its cleanup left the item usable"
        );
    }

    #[test]
    fn an_interruption_offers_resume_whatever_else_the_check_observed() {
        let differs = Observation::Differs {
            stale: StaleReason::OlderRevision,
        };
        for observation in [
            Observation::Absent,
            differs,
            Observation::Failed(FailureCategory::HostUnreachable),
            Observation::Failed(FailureCategory::DamagedDownload),
            Observation::Blocked(BlockedReason::Offline),
            Observation::Blocked(BlockedReason::NeedsPerson),
        ] {
            let interrupted = row(
                observation,
                Activity::Interrupted,
                Some(FailureCategory::DiskFull),
            );
            assert_eq!(
                (interrupted.state, interrupted.recovery),
                (
                    ItemState::Failed(FailureCategory::Interrupted),
                    Some(RecoveryAction::Resume)
                ),
                "{observation:?}"
            );
        }
        for reason in [BlockedReason::Hardware, BlockedReason::NotInThisBuild] {
            let held = row(Observation::Blocked(reason), Activity::Interrupted, None);
            assert_eq!(
                (held.state, held.recovery),
                (ItemState::Blocked(reason), None),
                "{reason:?}: Resume could not change it"
            );
        }
        assert_eq!(
            row(Observation::Unreadable, Activity::Interrupted, None).state,
            ItemState::Unknown
        );
        let after_failure = row(differs, Activity::Idle, Some(FailureCategory::DiskFull));
        assert_eq!(
            (after_failure.state, after_failure.recovery),
            (
                ItemState::Failed(FailureCategory::DiskFull),
                Some(RecoveryAction::TryAgain)
            ),
            "the failure the last setup recorded outranks what the item differs by"
        );
        assert_eq!(
            row(differs, Activity::Idle, None).state,
            ItemState::Stale(StaleReason::OlderRevision),
            "with no recorded failure the difference is what the row reads"
        );
    }

    #[test]
    fn a_recorded_failure_or_an_interruption_reads_failed_with_its_button() {
        let interrupted = row(
            Observation::Absent,
            Activity::Interrupted,
            Some(FailureCategory::DiskFull),
        );
        assert_eq!(
            interrupted.state,
            ItemState::Failed(FailureCategory::Interrupted)
        );
        assert_eq!(interrupted.recovery, Some(RecoveryAction::Resume));
        assert_eq!(
            interrupted.recovery_action_id(),
            Some("operator.provision.browser")
        );
        let failed = row(
            Observation::Absent,
            Activity::Idle,
            Some(FailureCategory::DamagedDownload),
        );
        assert_eq!(
            failed.state,
            ItemState::Failed(FailureCategory::DamagedDownload)
        );
        assert_eq!(failed.recovery, Some(RecoveryAction::TryAgain));
        let absent = row(Observation::Absent, Activity::Idle, None);
        assert_eq!(
            (absent.state, absent.recovery),
            (ItemState::Absent, Some(RecoveryAction::SetUp))
        );
    }

    #[test]
    fn every_state_offers_the_button_the_contract_names() {
        for (state, recovery) in [
            (ItemState::Ready, None),
            (ItemState::Unknown, Some(RecoveryAction::CheckAgain)),
            (
                ItemState::Stale(StaleReason::OlderRevision),
                Some(RecoveryAction::Update),
            ),
            (
                ItemState::Blocked(BlockedReason::Offline),
                Some(RecoveryAction::CheckAgain),
            ),
            (
                ItemState::Blocked(BlockedReason::NeedsPerson),
                Some(RecoveryAction::SetUp),
            ),
            (ItemState::Blocked(BlockedReason::Hardware), None),
            (ItemState::Blocked(BlockedReason::NotInThisBuild), None),
            (ItemState::Failed(FailureCategory::NotEnoughMemory), None),
            (
                ItemState::Failed(FailureCategory::Offline),
                Some(RecoveryAction::TryAgain),
            ),
        ] {
            assert_eq!(recovery_for(state), recovery, "{state:?}");
        }
    }

    #[test]
    fn rows_serialize_exactly_the_reason_their_state_needs() {
        let mut stale = row(
            Observation::Differs {
                stale: StaleReason::OlderRevision,
            },
            Activity::Idle,
            None,
        );
        stale.version = Some("0.40.10".into());
        assert_eq!(
            serde_json::to_value(&stale).unwrap(),
            serde_json::json!({
                "item_id": "browser",
                "mode": "quick",
                "state": "stale",
                "stale_reason": "older_revision",
                "version": "0.40.10",
                "recovery": "update",
                "recovery_action_id": "operator.provision.browser",
            })
        );
        let blocked = derive_row(
            &LOCAL_AI,
            &reading(Observation::Blocked(BlockedReason::NotInThisBuild)),
            Activity::Idle,
            None,
        );
        assert_eq!(
            serde_json::to_value(&blocked).unwrap(),
            serde_json::json!({
                "item_id": "local_ai",
                "mode": "quick",
                "state": "blocked",
                "blocked_reason": "not_in_this_build",
            })
        );
        let failed = row(
            Observation::Failed(FailureCategory::DiskFull),
            Activity::Idle,
            None,
        );
        assert_eq!(
            serde_json::to_value(&failed).unwrap()["failure_category"],
            "disk_full"
        );
    }

    fn part(observation: Observation) -> Reading {
        reading(observation)
    }

    #[test]
    fn the_local_ai_reads_as_the_worst_of_its_parts() {
        let present = Observation::Present;
        let differs = Observation::Differs {
            stale: StaleReason::OlderRevision,
        };
        let mut program = part(present);
        program.version = Some("0.40.10".into());
        let cases = [
            (vec![present, present], Observation::Present),
            (vec![present, differs], differs),
            (vec![differs, Observation::Absent], Observation::Absent),
            (
                vec![
                    Observation::Absent,
                    Observation::Blocked(BlockedReason::Offline),
                ],
                Observation::Blocked(BlockedReason::Offline),
            ),
            (
                vec![
                    Observation::Blocked(BlockedReason::Offline),
                    Observation::Failed(FailureCategory::DamagedDownload),
                ],
                Observation::Failed(FailureCategory::DamagedDownload),
            ),
            (
                vec![
                    Observation::Failed(FailureCategory::DamagedDownload),
                    Observation::Unreadable,
                ],
                Observation::Unreadable,
            ),
            (
                vec![
                    Observation::Unreadable,
                    Observation::Blocked(BlockedReason::Hardware),
                ],
                Observation::Blocked(BlockedReason::Hardware),
            ),
        ];
        for (models, expected) in cases {
            let models: Vec<Reading> = models.into_iter().map(part).collect();
            let combined = Reading::worst_of_parts(CheckMode::Quick, &program, &models);
            assert_eq!(combined.observation, expected, "{models:?}");
            assert_eq!(combined.version.as_deref(), Some("0.40.10"));
        }
        let missing_program = Reading::worst_of_parts(
            CheckMode::Full,
            &part(Observation::Absent),
            &[part(Observation::Present)],
        );
        assert_eq!(missing_program.observation, Observation::Absent);
    }

    fn report(outcome: Reachability) -> NetworkReport {
        NetworkReport {
            hosts: vec![HostCheck {
                host: HostName::new("cdn.example.com").unwrap(),
                outcome,
                connected: false,
                via_proxy: false,
                status: None,
            }],
        }
    }

    #[test]
    fn the_network_holds_only_an_item_that_still_needs_it() {
        let absent = reading(Observation::Absent);
        assert_eq!(
            absent
                .clone()
                .held_by_network(&report(Reachability::Offline))
                .observation,
            Observation::Blocked(BlockedReason::Offline)
        );
        assert_eq!(
            absent
                .clone()
                .held_by_network(&report(Reachability::BlockedByNetwork))
                .observation,
            Observation::Failed(FailureCategory::BlockedByNetwork)
        );
        assert_eq!(
            absent
                .clone()
                .held_by_network(&report(Reachability::Reachable)),
            absent
        );
        let ready = reading(Observation::Present);
        assert_eq!(
            ready
                .clone()
                .held_by_network(&report(Reachability::Offline)),
            ready
        );
    }

    #[test]
    fn setup_covers_every_item_whose_row_offers_an_action() {
        let rows = |browser: Observation, local: Observation| {
            vec![
                derive_row(&BROWSER, &reading(browser), Activity::Idle, None),
                derive_row(&LOCAL_AI, &reading(local), Activity::Idle, None),
            ]
        };
        let all = rows(
            Observation::Absent,
            Observation::Failed(FailureCategory::Offline),
        );
        assert_eq!(items_to_set_up(&all), [ItemId::Browser, ItemId::LocalAi]);
        assert!(!setup_complete(&all));
        let held = rows(
            Observation::Blocked(BlockedReason::NotInThisBuild),
            Observation::Blocked(BlockedReason::Hardware),
        );
        assert!(items_to_set_up(&held).is_empty());
        let failed_without_a_button = rows(
            Observation::Failed(FailureCategory::NotInThisBuild),
            Observation::Failed(FailureCategory::NotEnoughMemory),
        );
        assert!(
            failed_without_a_button
                .iter()
                .all(|row| row.recovery.is_none())
        );
        assert!(items_to_set_up(&failed_without_a_button).is_empty());
        let done = rows(
            Observation::Present,
            Observation::Differs {
                stale: StaleReason::OlderRevision,
            },
        );
        assert!(setup_complete(&done));
        assert_eq!(items_to_set_up(&done), [ItemId::LocalAi]);
        let mut desktop_only = rows(Observation::Absent, Observation::Absent);
        desktop_only[1].recovery = Some(RecoveryAction::SetUpInDesktop);
        assert_eq!(items_to_set_up(&desktop_only), [ItemId::Browser]);
        assert_eq!(
            SetupStep::Download.phase_code(ItemId::LocalAi),
            "dependencies.setup.local_ai.download"
        );
    }
}
