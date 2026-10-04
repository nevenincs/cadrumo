use cadrumo_application::failure::{Failure, FailureCode, Operation, Result};
use std::ffi::OsString;

#[derive(Debug, PartialEq)]
pub enum Mode {
    Gui,
    Cli(Vec<OsString>),
}

pub fn desktop_available() -> bool {
    #[cfg(windows)]
    {
        cadrumo_platform::desktop::available()
    }
    #[cfg(target_os = "linux")]
    {
        ["WAYLAND_DISPLAY", "DISPLAY"]
            .iter()
            .any(|name| std::env::var_os(name).is_some_and(|v| !v.is_empty()))
    }
    #[cfg(not(any(windows, target_os = "linux")))]
    {
        false
    }
}

pub fn select(mut arguments: Vec<OsString>, desktop: bool) -> Result<Mode> {
    if arguments.first().is_some_and(|arg| arg == "--headless") {
        arguments.remove(0);
        if arguments.first().is_some_and(|arg| arg == "--") {
            arguments.remove(0);
        }
        return Ok(Mode::Cli(arguments));
    }
    if arguments.first().is_some_and(|arg| arg == "--gui") {
        if arguments.len() != 1 {
            return Err(Failure::new(
                FailureCode::InvalidArguments,
                Operation::Launch,
            ));
        }
        return if desktop {
            Ok(Mode::Gui)
        } else {
            Err(Failure::new(
                FailureCode::DesktopUnavailable,
                Operation::Launch,
            ))
        };
    }
    if !arguments.is_empty() || !desktop {
        Ok(Mode::Cli(arguments))
    } else {
        Ok(Mode::Gui)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn mode_selection_preserves_cli_arguments_and_refuses_forced_headless_gui() {
        assert_eq!(select(vec![], true).unwrap(), Mode::Gui);
        assert_eq!(select(vec![], false).unwrap(), Mode::Cli(vec![]));
        let args = vec!["--format".into(), "json".into(), "a b á漢".into()];
        assert_eq!(select(args.clone(), true).unwrap(), Mode::Cli(args.clone()));
        let mut headless = vec!["--headless".into(), "--".into()];
        headless.extend(args.clone());
        assert_eq!(select(headless, true).unwrap(), Mode::Cli(args));
        assert_eq!(
            select(vec!["--gui".into()], false).unwrap_err().code,
            FailureCode::DesktopUnavailable
        );
        assert!(select(vec!["--gui".into(), "--help".into()], true).is_err());
    }
}
