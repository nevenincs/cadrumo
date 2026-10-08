//! Native prerequisites before a manager acquires state or starts a child.
//!
//! These checks admit this process only. Job escape and session-end handling
//! remain prerequisites of the eventual runtime launch composition.

/// Why the current process cannot host an interactive manager.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Refusal {
    SessionUnavailable,
    SessionZero,
    ElevationUnavailable,
    FullyElevated,
    DesktopUnavailable,
}

impl Refusal {
    /// Bounded diagnostic code; no native error text or user data is emitted.
    pub fn code(self) -> &'static str {
        match self {
            Self::SessionUnavailable => "manager_session_unavailable",
            Self::SessionZero => "manager_session_zero",
            Self::ElevationUnavailable => "manager_elevation_unavailable",
            Self::FullyElevated => "manager_fully_elevated",
            Self::DesktopUnavailable => "manager_desktop_unavailable",
        }
    }
}

fn require_evidence(
    session: Option<u32>,
    fully_elevated: Option<bool>,
    desktop_available: impl FnOnce() -> bool,
) -> Result<(), Refusal> {
    match session {
        None => return Err(Refusal::SessionUnavailable),
        Some(0) => return Err(Refusal::SessionZero),
        Some(_) => {}
    }
    match fully_elevated {
        None => return Err(Refusal::ElevationUnavailable),
        Some(true) => return Err(Refusal::FullyElevated),
        Some(false) => {}
    }
    if !desktop_available() {
        return Err(Refusal::DesktopUnavailable);
    }
    Ok(())
}

/// Observe this process through the existing native process and desktop owners.
/// A full UAC token is refused; a default token is not treated as elevated.
#[cfg(windows)]
pub fn require_current() -> Result<(), Refusal> {
    let process = crate::supervision::process::open_process(std::process::id())
        .map_err(|_| Refusal::SessionUnavailable)?;
    require_evidence(
        process
            .identity
            .session
            .and_then(|value| value.parse().ok()),
        process.identity.fully_elevated,
        cadrumo_platform::desktop::available,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_session_and_session_zero_refuse_before_desktop_access() {
        for (session, refusal) in [
            (None, Refusal::SessionUnavailable),
            (Some(0), Refusal::SessionZero),
        ] {
            assert_eq!(
                require_evidence(session, Some(false), || panic!("desktop queried")),
                Err(refusal)
            );
        }
    }

    #[test]
    fn full_or_unknown_elevation_refuses_before_desktop_access() {
        for (elevation, refusal) in [
            (None, Refusal::ElevationUnavailable),
            (Some(true), Refusal::FullyElevated),
        ] {
            assert_eq!(
                require_evidence(Some(1), elevation, || panic!("desktop queried")),
                Err(refusal)
            );
        }
    }

    #[test]
    fn interactive_desktop_required() {
        assert_eq!(
            require_evidence(Some(1), Some(false), || false),
            Err(Refusal::DesktopUnavailable)
        );
        assert_eq!(require_evidence(Some(1), Some(false), || true), Ok(()));
    }
}
