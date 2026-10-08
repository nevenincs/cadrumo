//! Closed lifecycle facts. Boot IDs, version strings, paths and protocol text are excluded.
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AdmissionRefusal {
    SessionUnavailable,
    SessionZero,
    ElevationUnavailable,
    FullyElevated,
    DesktopUnavailable,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InspectionRefusal {
    FailedVersionMarker,
    PackageUnavailable,
    PackageIntegrityRefused,
    PackageIncompatible,
    PackageIncomplete,
    EnvironmentUnavailable,
    RuntimeProbeFailed,
    RuntimeIdentityMismatch,
    LaunchTargetRefused,
    UnsupportedPlatform,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WaitReason {
    Quit,
    QuitUnreadable,
    Inactive,
    StartingElsewhere,
    ClaimUnavailable,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ForeignReason {
    RecordAbsent,
    RecordUnreadable,
    StaleRecord,
    IdentityMismatch,
    Uninspectable,
    OtherSession,
    Elevated,
    DevelopmentAdmission,
    NotInstalled,
    VersionMismatch,
    FailedVersion,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StandDownReason {
    RootMismatch,
    ElevatedTokenRefused,
    VersionMismatch,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RestartClass {
    Unexpected,
    LaunchFailure,
    Hang,
    OutsideStop,
    WitnessLoss,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StopCause {
    Defect,
    Hang,
    IdleRequested,
    Requested,
    SessionEnd,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StopSignalRefusal {
    NotRunning,
    Unsupported,
    AlreadyAttached,
    NoConsole,
    Unconfirmed,
    Failed,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(tag = "delivery", rename_all = "snake_case", deny_unknown_fields)]
pub enum StopPath {
    Channel {},
    Signal {},
    Undelivered { refusal: StopSignalRefusal },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeReason {
    SupervisorStop,
    SignalStop,
    SessionEndSettle,
    OwnerBusy,
    RootMismatch,
    VersionMismatch,
    LoginWitnessLoss,
    DrainWatchdog,
    ElevatedTokenRefused,
    UnexpectedFailure,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(tag = "classification", rename_all = "snake_case", deny_unknown_fields)]
pub enum RuntimeExit {
    Reason { reason: RuntimeReason, code: u32 },
    Zero {},
    ControlC {},
    LaunchFailure { code: u32 },
    Crash { code: u32 },
    Terminated {},
    Unknown {},
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Effects {
    Settled,
    Unknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LineRefusal {
    Malformed,
    Oversized,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(tag = "outcome", rename_all = "snake_case", deny_unknown_fields)]
pub enum SupervisorOutcome {
    RestartDeferred { reason: WaitReason },
    OwnershipChanged {},
    Stopped { effects: Effects },
    StoodDown { reason: StandDownReason },
    Foreign { reason: ForeignReason },
    AwaitingActiveSession {},
    Failed { last: RestartClass },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(
    tag = "event",
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
pub enum LifecycleFact {
    AdmissionRefused {
        reason: AdmissionRefusal,
    },
    InspectionRefused {
        reason: InspectionRefusal,
    },
    SupervisorStarted {},
    Waiting {
        reason: WaitReason,
    },
    Observing {
        pid: u32,
    },
    RestartDeferred {
        reason: WaitReason,
    },
    OwnershipChanged {},
    Launched {
        pid: u32,
    },
    LaunchFailed {},
    Ready {
        pid: u32,
    },
    BootRecordConfirmed {
        pid: u32,
    },
    BootRecordMismatch {
        pid: u32,
    },
    AnnouncementRefused {
        reason: LineRefusal,
    },
    CommandRefused {
        reason: LineRefusal,
    },
    ChannelClosed {
        pid: u32,
    },
    Busy {
        pid: u32,
    },
    IdleStopUnavailable {
        pid: u32,
    },
    HangDetected {
        pid: u32,
        ready: bool,
    },
    StopRequested {
        pid: u32,
        cause: StopCause,
        path: StopPath,
    },
    TerminationRequested {
        pid: u32,
    },
    TerminationFailed {
        pid: u32,
    },
    TerminationUnconfirmed {
        pid: u32,
    },
    ProcessInspectionFailed {
        pid: u32,
    },
    Terminated {
        pid: u32,
    },
    EffectsUnknown {
        pid: u32,
    },
    Exited {
        pid: u32,
        exit: RuntimeExit,
        announced: Option<RuntimeReason>,
    },
    VersionReprobed {},
    RestartScheduled {
        class: RestartClass,
        delay_ms: u64,
    },
    Adopted {
        pid: u32,
    },
    Foreign {
        reason: ForeignReason,
    },
    StoodDown {
        reason: StandDownReason,
    },
    AwaitingActiveSession {},
    Failed {
        last: RestartClass,
    },
    SupervisorEnded {
        result: SupervisorOutcome,
    },
    SessionEndRequested {},
    SessionEndCancelled {},
    EventsDropped {
        count: u64,
    },
}
