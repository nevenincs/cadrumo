//! The agent service's console environment for the signed-in profile, composed
//! over the console kind's own environment.
//!
//! The service names the profile's provider homes and its agent workspace. The
//! host merges those names over the console's filtered environment, then applies
//! the console's filter to the merged result, so a name the filter clears can
//! only ever carry the value the console's own environment pinned. The `python`
//! and `tui` kinds are never composed. Without a signed-in profile or a
//! service, the console gets its base environment and the shared workspace.
use super::{Kind, session::Program};
use serde::Serialize;
use serde_json::Value;
use std::{
    collections::{BTreeMap, BTreeSet},
    ffi::{OsStr, OsString},
    path::{Path, PathBuf},
};

/// The window event that says the console environment changed.
pub const EVENT: &str = "console-environment-changed";

/// The revision of the base environment, used when the service cannot answer.
pub const BASE_REVISION: &str = "base";

/// The most names one answer may carry.
const MAX_NAMES: usize = 16;
/// The longest name or value one answer may carry.
const MAX_TEXT: usize = 4096;

/// What the service answered for the signed-in profile, or the base.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConsoleEnvironment {
    pub environment: BTreeMap<String, String>,
    pub working_directory: Option<PathBuf>,
    pub revision: String,
}

/// The window event's payload: the revision only, never what it names.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Changed {
    pub revision: String,
}

impl ConsoleEnvironment {
    /// The console's own environment and the shared workspace.
    pub fn base() -> Self {
        Self {
            environment: BTreeMap::new(),
            working_directory: None,
            revision: BASE_REVISION.to_owned(),
        }
    }

    /// The service's answer, or `None` when it is a refusal or outside the contract.
    pub fn parse(answer: &Value) -> Option<Self> {
        if answer["kind"] != "console_environment" {
            return None;
        }
        let revision = answer["revision"].as_str()?;
        if revision.len() != 64 || !revision.bytes().all(|b| b.is_ascii_hexdigit()) {
            return None;
        }
        let names = answer["environment"].as_object()?;
        if names.len() > MAX_NAMES {
            return None;
        }
        let environment = names
            .iter()
            .map(|(name, value)| {
                let value = value.as_str()?;
                (admissible_name(name) && !value.contains('\0') && value.len() <= MAX_TEXT)
                    .then(|| (name.clone(), value.to_owned()))
            })
            .collect::<Option<BTreeMap<_, _>>>()?;
        let working_directory = match &answer["working_directory"] {
            Value::Null => None,
            Value::String(directory) if Path::new(directory).is_absolute() => {
                Some(PathBuf::from(directory))
            }
            _ => return None,
        };
        Some(Self {
            environment,
            working_directory,
            revision: revision.to_owned(),
        })
    }

    pub fn changed(&self) -> Changed {
        Changed {
            revision: self.revision.clone(),
        }
    }
}

fn admissible_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= MAX_TEXT
        && name.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
        && !name.as_bytes()[0].is_ascii_digit()
}

fn same_name(left: &OsStr, right: &OsStr) -> bool {
    if cfg!(windows) {
        left.eq_ignore_ascii_case(right)
    } else {
        left == right
    }
}

/// `base` with `added` merged over it, the added value winning a name both
/// carry, and then the console's filter applied to the result: a name the
/// filter clears keeps the value `base` carried for it and is dropped otherwise.
pub fn merged(
    base: &BTreeMap<OsString, OsString>,
    added: &BTreeMap<String, String>,
) -> BTreeMap<OsString, OsString> {
    let mut merged = base.clone();
    for (name, value) in added {
        let name = OsString::from(name);
        merged.retain(|key, _| !same_name(key, &name));
        merged.insert(name, OsString::from(value));
    }
    let admitted: BTreeSet<OsString> =
        cadrumo_platform::storage::strict_host_environment(merged.clone())
            .into_iter()
            .map(|(name, _)| name)
            .collect();
    let mut filtered: BTreeMap<OsString, OsString> = merged
        .into_iter()
        .filter(|(name, _)| admitted.contains(name))
        .collect();
    for (name, value) in base {
        if !admitted.contains(name) && !filtered.keys().any(|key| same_name(key, name)) {
            filtered.insert(name.clone(), value.clone());
        }
    }
    filtered
}

/// `program`, started as `kind`, with `console` composed into it when `kind`
/// is the console: its names merged over the environment and its working
/// directory, when it gives one that `admit` accepts. Every other kind is unchanged.
pub fn composed(
    kind: Kind,
    mut program: Program,
    console: &ConsoleEnvironment,
    admit: impl Fn(&Path) -> bool,
) -> Program {
    if kind != Kind::Console {
        return program;
    }
    if let Some(directory) = &console.working_directory {
        if !admit(directory) {
            return program;
        }
        program.directory = directory.clone();
    }
    program.environment = merged(&program.environment, &console.environment);
    program
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::process::status::ProcessRole;
    use serde_json::json;

    const REVISION: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    fn os(pairs: &[(&str, &str)]) -> BTreeMap<OsString, OsString> {
        pairs
            .iter()
            .map(|(name, value)| (OsString::from(name), OsString::from(value)))
            .collect()
    }

    fn text(pairs: &[(&str, &str)]) -> BTreeMap<String, String> {
        pairs
            .iter()
            .map(|(name, value)| ((*name).to_owned(), (*value).to_owned()))
            .collect()
    }

    fn base_environment() -> BTreeMap<OsString, OsString> {
        os(&[
            ("PATH", r"C:\package\bin"),
            ("CODEX_HOME", r"C:\person\codex"),
            ("CADRUMO_STORAGE_ROOT", r"C:\root"),
        ])
    }

    fn program(role: ProcessRole) -> Program {
        Program {
            executable: PathBuf::from(r"C:\shell.exe"),
            arguments: Vec::new(),
            directory: PathBuf::from(r"C:\root\workspace"),
            environment: base_environment(),
            role,
        }
    }

    fn profile() -> ConsoleEnvironment {
        ConsoleEnvironment {
            environment: text(&[
                ("CLAUDE_CONFIG_DIR", r"C:\root\agent\a\providers\claude"),
                ("CODEX_HOME", r"C:\root\agent\a\providers\codex"),
            ]),
            working_directory: Some(PathBuf::from(r"C:\root\agent\a\home\workspaces\cadrumo")),
            revision: REVISION.to_owned(),
        }
    }

    fn value<'a>(environment: &'a BTreeMap<OsString, OsString>, name: &str) -> Option<&'a OsStr> {
        environment
            .iter()
            .find(|(key, _)| same_name(key, OsStr::new(name)))
            .map(|(_, value)| value.as_os_str())
    }

    #[test]
    fn the_service_value_wins_and_the_base_keeps_every_other_name() {
        let merged = merged(&base_environment(), &profile().environment);

        assert_eq!(
            value(&merged, "CODEX_HOME"),
            Some(OsStr::new(r"C:\root\agent\a\providers\codex"))
        );
        assert_eq!(
            value(&merged, "CLAUDE_CONFIG_DIR"),
            Some(OsStr::new(r"C:\root\agent\a\providers\claude"))
        );
        assert_eq!(value(&merged, "PATH"), Some(OsStr::new(r"C:\package\bin")));
        assert_eq!(
            value(&merged, "CADRUMO_STORAGE_ROOT"),
            Some(OsStr::new(r"C:\root"))
        );
        assert_eq!(merged.len(), 4);
    }

    #[test]
    fn the_filter_clears_its_names_after_the_merge() {
        // Any product-namespace name the console does not pin, as the platform declares it.
        let unpinned = format!("{}CONSOLE_PROBE", cadrumo_platform::NAMESPACE_PREFIX);
        let added = text(&[
            ("CADRUMO_STORAGE_ROOT", r"C:\elsewhere"),
            (unpinned.as_str(), "1"),
            ("PYTHONPATH", r"C:\elsewhere"),
            ("AEAT_CERTIFICATE", "x"),
            ("FINANCIAL_SOURCE", "x"),
            ("CLAUDE_CONFIG_DIR", r"C:\root\agent\a\providers\claude"),
        ]);

        let merged = merged(&base_environment(), &added);

        // The base's own pin survives with the base value; nothing else the filter clears does.
        assert_eq!(
            value(&merged, "CADRUMO_STORAGE_ROOT"),
            Some(OsStr::new(r"C:\root"))
        );
        for cleared in [
            unpinned.as_str(),
            "PYTHONPATH",
            "AEAT_CERTIFICATE",
            "FINANCIAL_SOURCE",
        ] {
            assert_eq!(value(&merged, cleared), None, "{cleared}");
        }
        assert!(value(&merged, "CLAUDE_CONFIG_DIR").is_some());
    }

    #[test]
    fn only_the_console_kind_is_composed() {
        let console = profile();
        for (kind, role) in [
            (Kind::Python, ProcessRole::Repl),
            (Kind::Tui, ProcessRole::Tui),
        ] {
            let unchanged = composed(kind, program(role), &console, |_| true);
            assert_eq!(unchanged.environment, base_environment());
            assert_eq!(unchanged.directory, PathBuf::from(r"C:\root\workspace"));
        }

        let started = composed(
            Kind::Console,
            program(ProcessRole::Console),
            &console,
            |_| true,
        );
        assert_eq!(
            started.directory,
            PathBuf::from(r"C:\root\agent\a\home\workspaces\cadrumo")
        );
        assert_eq!(
            value(&started.environment, "CLAUDE_CONFIG_DIR"),
            Some(OsStr::new(r"C:\root\agent\a\providers\claude"))
        );
    }

    #[test]
    fn a_working_directory_the_host_refuses_leaves_the_console_at_its_base() {
        let refused = composed(
            Kind::Console,
            program(ProcessRole::Console),
            &profile(),
            |_| false,
        );

        assert_eq!(refused.environment, base_environment());
        assert_eq!(refused.directory, PathBuf::from(r"C:\root\workspace"));
    }

    #[test]
    fn after_sign_out_the_console_holds_none_of_the_previous_profiles_values() {
        let previous = profile();
        let signed_in = composed(
            Kind::Console,
            program(ProcessRole::Console),
            &previous,
            |_| true,
        );
        assert_ne!(signed_in.environment, base_environment());

        let signed_out = composed(
            Kind::Console,
            program(ProcessRole::Console),
            &ConsoleEnvironment::base(),
            |_| true,
        );

        assert_eq!(signed_out.environment, base_environment());
        assert_eq!(signed_out.directory, PathBuf::from(r"C:\root\workspace"));
        let held: Vec<&OsStr> = signed_out
            .environment
            .values()
            .map(OsString::as_os_str)
            .collect();
        for value in previous.environment.values() {
            assert!(!held.contains(&OsStr::new(value)), "{value}");
        }
    }

    #[test]
    fn the_event_payload_carries_only_the_revision() {
        let payload = serde_json::to_value(profile().changed()).unwrap();

        assert_eq!(payload, json!({"revision": REVISION}));
        let base = serde_json::to_value(ConsoleEnvironment::base().changed()).unwrap();
        assert_eq!(base, json!({"revision": BASE_REVISION}));
    }

    #[test]
    fn the_answer_is_parsed_strictly() {
        let workspace = std::env::temp_dir().join("workspace");
        let answer = json!({
            "kind": "console_environment",
            "environment": {"CODEX_HOME": r"C:\root\agent\a\providers\codex"},
            "working_directory": workspace,
            "revision": REVISION,
        });
        let parsed = ConsoleEnvironment::parse(&answer).unwrap();
        assert_eq!(parsed.revision, REVISION);
        assert_eq!(parsed.environment.len(), 1);
        assert_eq!(parsed.working_directory, Some(workspace));

        let no_profile = json!({
            "kind": "console_environment", "environment": {}, "working_directory": null, "revision": REVISION,
        });
        let parsed = ConsoleEnvironment::parse(&no_profile).unwrap();
        assert!(parsed.environment.is_empty() && parsed.working_directory.is_none());

        for refused in [
            json!({"kind": "refused", "code": "signed_out"}),
            json!({"kind": "console_environment", "environment": {}, "working_directory": null, "revision": "short"}),
            json!({"kind": "console_environment", "environment": {"A=B": "x"}, "working_directory": null, "revision": REVISION}),
            json!({"kind": "console_environment", "environment": {"A": 1}, "working_directory": null, "revision": REVISION}),
            json!({"kind": "console_environment", "environment": {}, "working_directory": "relative", "revision": REVISION}),
        ] {
            assert_eq!(ConsoleEnvironment::parse(&refused), None, "{refused}");
        }
    }
}
