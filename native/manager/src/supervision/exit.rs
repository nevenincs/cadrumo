//! Runtime exit codes, read through the exit-reason table the contract generator projects.

use crate::contract::{
    RUNTIME_EXIT_DRAIN_WATCHDOG, RUNTIME_EXIT_ELEVATED_TOKEN_REFUSED,
    RUNTIME_EXIT_LOGIN_WITNESS_LOSS, RUNTIME_EXIT_OWNER_BUSY, RUNTIME_EXIT_ROOT_MISMATCH,
    RUNTIME_EXIT_SESSION_END_SETTLE, RUNTIME_EXIT_SIGNAL_STOP, RUNTIME_EXIT_SUPERVISOR_STOP,
    RUNTIME_EXIT_UNEXPECTED_FAILURE, RUNTIME_EXIT_VERSION_MISMATCH,
};

/// The NTSTATUS a console process reports when Ctrl+C ended it before its handlers ran.
pub const STATUS_CONTROL_C_EXIT: u32 = 0xC000_013A;

/// Python's uncaught-exception code and argparse's usage code, both before runtime code runs.
const LAUNCH_FAILURE_CODES: [u32; 2] = [1, 2];

/// One reason a runtime names by its exit code.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExitReason {
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

impl ExitReason {
    /// Every reason, in table order.
    pub const ALL: [Self; 10] = [
        Self::SupervisorStop,
        Self::SignalStop,
        Self::SessionEndSettle,
        Self::OwnerBusy,
        Self::RootMismatch,
        Self::VersionMismatch,
        Self::LoginWitnessLoss,
        Self::DrainWatchdog,
        Self::ElevatedTokenRefused,
        Self::UnexpectedFailure,
    ];

    /// The exit code the contract assigns this reason.
    pub const fn code(self) -> u32 {
        match self {
            Self::SupervisorStop => RUNTIME_EXIT_SUPERVISOR_STOP,
            Self::SignalStop => RUNTIME_EXIT_SIGNAL_STOP,
            Self::SessionEndSettle => RUNTIME_EXIT_SESSION_END_SETTLE,
            Self::OwnerBusy => RUNTIME_EXIT_OWNER_BUSY,
            Self::RootMismatch => RUNTIME_EXIT_ROOT_MISMATCH,
            Self::VersionMismatch => RUNTIME_EXIT_VERSION_MISMATCH,
            Self::LoginWitnessLoss => RUNTIME_EXIT_LOGIN_WITNESS_LOSS,
            Self::DrainWatchdog => RUNTIME_EXIT_DRAIN_WATCHDOG,
            Self::ElevatedTokenRefused => RUNTIME_EXIT_ELEVATED_TOKEN_REFUSED,
            Self::UnexpectedFailure => RUNTIME_EXIT_UNEXPECTED_FAILURE,
        }
    }

    /// The reason `code` names, if it names one.
    pub fn from_code(code: u32) -> Option<Self> {
        Self::ALL.into_iter().find(|reason| reason.code() == code)
    }
}

/// How one runtime process ended, as the supervisor reads its exit status.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RuntimeExit {
    /// A code from the runtime's own exit-reason table.
    Reason(ExitReason),
    /// Exit `0`, which a runtime never uses for its own stop.
    Zero,
    /// Ctrl+C ended the process before its handlers were installed.
    ControlC,
    /// The interpreter refused its configuration or arguments before runtime code ran.
    LaunchFailure(u32),
    /// Any other code: a crash, an NTSTATUS failure or a POSIX signal exit.
    Crash(u32),
    /// The supervisor terminated the process.
    Terminated,
    /// The exit status could not be read.
    Unknown,
}

impl RuntimeExit {
    /// Classify one platform exit code.
    pub fn from_code(code: u32) -> Self {
        if let Some(reason) = ExitReason::from_code(code) {
            Self::Reason(reason)
        } else if code == 0 {
            Self::Zero
        } else if code == STATUS_CONTROL_C_EXIT {
            Self::ControlC
        } else if LAUNCH_FAILURE_CODES.contains(&code) {
            Self::LaunchFailure(code)
        } else {
            Self::Crash(code)
        }
    }

    /// Whether the code means the runtime ended through a graceful stop signal or command.
    pub fn is_stop(self) -> bool {
        matches!(
            self,
            Self::Reason(ExitReason::SupervisorStop | ExitReason::SignalStop)
                | Self::Zero
                | Self::ControlC
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract::{RUNTIME_EXIT_REASONS, RUNTIME_RESERVED_EXIT_CODES};

    #[test]
    fn every_contract_reason_has_exactly_one_variant_of_the_same_name() {
        assert_eq!(RUNTIME_EXIT_REASONS.len(), ExitReason::ALL.len());
        for (entry, reason) in RUNTIME_EXIT_REASONS.iter().zip(ExitReason::ALL) {
            assert_eq!(entry.code, reason.code(), "{}", entry.name);
            let variant = format!("{reason:?}");
            let snake: String = variant
                .chars()
                .enumerate()
                .flat_map(|(index, character)| {
                    let separator = (index > 0 && character.is_ascii_uppercase()).then_some('_');
                    separator.into_iter().chain(character.to_lowercase())
                })
                .collect();
            assert_eq!(snake, entry.name);
        }
    }

    #[test]
    fn no_reason_falls_in_a_reserved_range() {
        for reason in ExitReason::ALL {
            assert!(
                !RUNTIME_RESERVED_EXIT_CODES
                    .iter()
                    .any(|reserved| (reserved.first..=reserved.last).contains(&reason.code())),
                "{reason:?}"
            );
        }
    }

    #[test]
    fn reserved_codes_never_read_as_runtime_reasons() {
        assert_eq!(RuntimeExit::from_code(0), RuntimeExit::Zero);
        assert_eq!(RuntimeExit::from_code(1), RuntimeExit::LaunchFailure(1));
        assert_eq!(RuntimeExit::from_code(2), RuntimeExit::LaunchFailure(2));
        assert_eq!(RuntimeExit::from_code(3), RuntimeExit::Crash(3));
        assert_eq!(RuntimeExit::from_code(120), RuntimeExit::Crash(120));
        assert_eq!(RuntimeExit::from_code(143), RuntimeExit::Crash(143));
        assert_eq!(
            RuntimeExit::from_code(STATUS_CONTROL_C_EXIT),
            RuntimeExit::ControlC
        );
        assert_eq!(
            RuntimeExit::from_code(0xC000_0005),
            RuntimeExit::Crash(0xC000_0005)
        );
        assert_eq!(
            RuntimeExit::from_code(65),
            RuntimeExit::Reason(ExitReason::SignalStop)
        );
    }
}
