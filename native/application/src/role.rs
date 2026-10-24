//! The roles the one Cadrumo binary runs as, selected by a reserved first argument.
//!
//! Every Cadrumo-managed process is the `cadrumo` image, so Windows shows the whole tree
//! under one application. No argument is the desktop; `--role NAME` selects another role
//! before any window or webview exists. A role name grants nothing by itself: admission
//! still proves how a peer was started. Every role but `components` runs inside the linked
//! interpreter host; `components` runs the native component engine and hosts no
//! interpreter.

use std::ffi::OsStr;

/// The argument that, in first position, selects a role.
pub const ROLE_ARGUMENT: &str = "--role";

/// A role other than the desktop.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Role {
    /// The `cadrumo-runtime` console script: the supervised local runtime, and the
    /// runtime session commands the desktop runs.
    Runtime,
    /// The `aeat` console script, for the commands the desktop runs.
    Cli,
    /// The package interpreter itself, which the runtime's workers and its KDF child run.
    Python,
    /// The component engine, which sets up, checks and removes the browser and the local
    /// AI for the command line, the TUI and the MCP service. It hosts no interpreter.
    Components,
}

/// What a role runs inside the linked interpreter host.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct HostedImage {
    /// The declared launch image whose profile defines the environment.
    pub image: &'static str,
    /// The console script it runs, or `None` for the interpreter itself.
    pub entrypoint: Option<&'static str>,
}

/// Why role selection refused the arguments.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RoleRefusal {
    /// `--role` with no name.
    Missing,
    /// A name that is not a declared role.
    Unknown,
}

impl Role {
    pub const ALL: [Role; 4] = [Role::Runtime, Role::Cli, Role::Python, Role::Components];

    pub const fn name(self) -> &'static str {
        match self {
            Role::Runtime => "runtime",
            Role::Cli => "cli",
            Role::Python => "python",
            Role::Components => "components",
        }
    }

    /// The leading arguments that start this role.
    pub const fn arguments(self) -> &'static [&'static str; 2] {
        match self {
            Role::Runtime => &[ROLE_ARGUMENT, "runtime"],
            Role::Cli => &[ROLE_ARGUMENT, "cli"],
            Role::Python => &[ROLE_ARGUMENT, "python"],
            Role::Components => &[ROLE_ARGUMENT, "components"],
        }
    }

    /// What the role runs inside the linked interpreter host, or `None` for a role that
    /// hosts no interpreter.
    pub fn hosted(self) -> Option<HostedImage> {
        match self {
            Role::Runtime => Some(HostedImage {
                image: "cadrumo-runtime",
                entrypoint: Some("cadrumo-runtime"),
            }),
            Role::Cli => Some(HostedImage {
                image: "aeat",
                entrypoint: Some("aeat"),
            }),
            Role::Python => Some(HostedImage {
                image: "python",
                entrypoint: None,
            }),
            Role::Components => None,
        }
    }

    /// The role that runs the console script `entrypoint`, if one does.
    pub fn hosting(entrypoint: &str) -> Option<Role> {
        Role::ALL.into_iter().find(|role| {
            role.hosted()
                .is_some_and(|hosted| hosted.entrypoint == Some(entrypoint))
        })
    }

    fn named(name: &OsStr) -> Option<Role> {
        Role::ALL.into_iter().find(|role| name == role.name())
    }
}

/// The role `arguments` (after the image path) select and the arguments it receives,
/// or `None` when the first argument is not the role argument.
pub fn select<T: AsRef<OsStr>>(arguments: &[T]) -> Option<Result<(Role, &[T]), RoleRefusal>> {
    let (first, rest) = arguments.split_first()?;
    if first.as_ref() != ROLE_ARGUMENT {
        return None;
    }
    let Some((name, forwarded)) = rest.split_first() else {
        return Some(Err(RoleRefusal::Missing));
    };
    Some(
        Role::named(name.as_ref())
            .map(|role| (role, forwarded))
            .ok_or(RoleRefusal::Unknown),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::OsString;

    fn arguments(values: &[&str]) -> Vec<OsString> {
        values.iter().map(OsString::from).collect()
    }

    #[test]
    fn a_declared_role_receives_only_the_arguments_after_its_name() {
        let given = arguments(&["--role", "runtime", "--supervised", "--role"]);
        let (role, forwarded) = select(&given).unwrap().unwrap();
        assert_eq!(role, Role::Runtime);
        assert_eq!(forwarded, &given[2..]);
        assert_eq!(Role::Runtime.arguments(), &["--role", "runtime"]);
        assert_eq!(Role::Cli.arguments(), &["--role", "cli"]);
        let given = arguments(&["--role", "components", "status", "--full"]);
        let (role, forwarded) = select(&given).unwrap().unwrap();
        assert_eq!(role, Role::Components);
        assert_eq!(forwarded, &given[2..]);
    }

    #[test]
    fn other_first_arguments_are_not_a_role() {
        for given in [
            arguments(&[]),
            arguments(&["runtime"]),
            arguments(&["--headless", "--role", "runtime"]),
            arguments(&["--role=runtime"]),
        ] {
            assert!(select(&given).is_none(), "{given:?}");
        }
    }

    #[test]
    fn a_missing_or_undeclared_role_is_refused() {
        assert_eq!(
            select(&arguments(&["--role"])).unwrap().unwrap_err(),
            RoleRefusal::Missing
        );
        for name in [
            "",
            "Runtime",
            "desktop",
            "Python",
            "Components",
            "component",
            "interpreter",
            "runtime ",
        ] {
            assert_eq!(
                select(&arguments(&["--role", name])).unwrap().unwrap_err(),
                RoleRefusal::Unknown,
                "{name:?}"
            );
        }
    }

    #[test]
    fn every_interpreter_role_hosts_a_declared_launch_image_and_components_hosts_none() {
        for role in Role::ALL {
            assert_eq!(role.arguments()[1], role.name());
            assert_eq!(select(role.arguments()).unwrap().unwrap().0, role);
            let Some(hosted) = role.hosted() else {
                assert_eq!(role, Role::Components);
                continue;
            };
            assert!(!hosted.image.is_empty());
            if let Some(entrypoint) = hosted.entrypoint {
                assert!(!entrypoint.is_empty());
                assert_eq!(Role::hosting(entrypoint), Some(role));
            }
        }
        assert_eq!(Role::Python.hosted().unwrap().entrypoint, None);
        assert_eq!(Role::Components.hosted(), None);
        for entrypoint in [
            "cadrumo-agent-service",
            "cadrumo-mcp",
            "python",
            "components",
            "",
            "AEAT",
        ] {
            assert_eq!(Role::hosting(entrypoint), None, "{entrypoint:?}");
        }
    }
}
