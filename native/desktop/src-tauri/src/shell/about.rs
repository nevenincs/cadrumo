//! The About payload: the installed package manifest's statement of what this
//! installation is, plus the desktop binary's own compile-time identity.
//! A value the manifest does not state stays absent; nothing is filled in.
use super::blocking;
use crate::{app::Commands, environment::Launch};
use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    value::RelativePath,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{collections::BTreeMap, path::PathBuf, sync::Arc};
use tauri::State;

/// Where the installed package and its manifest are.
pub struct About {
    root: PathBuf,
    manifest: Option<RelativePath>,
}

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
}
#[derive(Deserialize)]
struct Layout {
    files: Files,
}
#[derive(Deserialize)]
struct Files {
    package_manifest: RelativePath,
}

impl About {
    pub fn new(launch: &Launch) -> Self {
        let manifest = serde_json::from_str::<Contract>(include_str!(concat!(
            env!("OUT_DIR"),
            "/contract.json"
        )))
        .ok()
        .map(|contract| contract.layout.files.package_manifest);
        Self {
            root: launch.package_root.clone(),
            manifest,
        }
    }
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct Named {
    pub name: String,
    pub version: String,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct Component {
    pub name: Option<String>,
    pub role: Option<String>,
    pub path: Option<String>,
    pub version: Option<String>,
    pub build_id: Option<String>,
    pub build_type: Option<String>,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct Desktop {
    pub version: Option<String>,
    pub build_id: Option<String>,
    pub build_type: String,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct Agent {
    pub version: Option<String>,
    pub dependencies: Vec<Named>,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct AboutInfo {
    pub product: Option<String>,
    pub display_version: Option<String>,
    pub version: Option<String>,
    pub build_id: Option<String>,
    pub build_type: Option<String>,
    pub build_date: Option<String>,
    pub channel: Option<String>,
    pub target: Option<String>,
    pub python: Option<String>,
    pub desktop: Desktop,
    pub components: Vec<Component>,
    pub agent: Option<Agent>,
    pub tools: BTreeMap<String, String>,
    pub distributions: Vec<Named>,
}

/// The desktop binary's own identity, fixed when it was compiled.
fn desktop() -> Desktop {
    Desktop {
        version: option_env!("CADRUMO_ID_VERSION").map(str::to_owned),
        build_id: option_env!("CADRUMO_BUILD_ID").map(str::to_owned),
        build_type: if cfg!(debug_assertions) {
            "debug"
        } else {
            "release"
        }
        .to_owned(),
    }
}

fn text(value: &Value, key: &str) -> Option<String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|text| !text.is_empty())
        .map(str::to_owned)
}

/// `name` and `version` pairs, from either an object of name to version or
/// an array of `{name, version}` objects, ordered by name.
fn named(value: Option<&Value>) -> Vec<Named> {
    let mut pairs: Vec<Named> = match value {
        Some(Value::Object(map)) => map
            .iter()
            .filter_map(|(name, version)| {
                Some(Named {
                    name: name.clone(),
                    version: version.as_str()?.to_owned(),
                })
            })
            .collect(),
        Some(Value::Array(items)) => items
            .iter()
            .filter_map(|item| {
                Some(Named {
                    name: text(item, "name")?,
                    version: text(item, "version")?,
                })
            })
            .collect(),
        _ => Vec::new(),
    };
    pairs.sort_by(|a, b| {
        a.name
            .to_lowercase()
            .cmp(&b.name.to_lowercase())
            .then_with(|| a.name.cmp(&b.name))
    });
    pairs
}

/// Projects the manifest into the About payload with `desktop` as the desktop
/// host's own entry.
fn project(manifest: &Value, desktop: Desktop) -> AboutInfo {
    let build = manifest.get("build").unwrap_or(&Value::Null);
    let agent = manifest
        .get("agent")
        .filter(|agent| agent.get("bundled").and_then(Value::as_bool) != Some(false))
        .filter(|agent| agent.is_object())
        .map(|agent| Agent {
            version: text(agent, "version"),
            dependencies: named(agent.get("dependencies")),
        });
    let components = manifest
        .get("components")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .map(|item| Component {
                    name: text(item, "name"),
                    role: text(item, "role"),
                    path: text(item, "path"),
                    version: text(item, "version"),
                    build_id: text(item, "build_id"),
                    build_type: text(item, "build_type"),
                })
                .collect()
        })
        .unwrap_or_default();
    let tools = manifest
        .get("tools")
        .and_then(Value::as_object)
        .map(|tools| {
            tools
                .iter()
                .filter_map(|(name, version)| Some((name.clone(), version.as_str()?.to_owned())))
                .collect()
        })
        .unwrap_or_default();
    AboutInfo {
        product: text(build, "product"),
        display_version: text(build, "display_version"),
        version: text(build, "version"),
        build_id: text(build, "build_id"),
        build_type: text(build, "build_type"),
        build_date: text(build, "build_date"),
        channel: text(build, "channel"),
        target: text(build, "target"),
        python: text(manifest, "python"),
        desktop,
        components,
        agent,
        tools,
        distributions: named(manifest.get("distributions")),
    }
}

fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Package)
}

fn read(about: &About) -> Result<AboutInfo> {
    let path = about
        .manifest
        .as_ref()
        .ok_or_else(unavailable)?
        .under(&about.root);
    let bytes = std::fs::read(&path)
        .map_err(|e| ApplicationError::new(ErrorCode::ReadFailed, Operation::Package).caused_by(e))?;
    let manifest: Value = serde_json::from_slice(&bytes).map_err(|e| unavailable().caused_by(e))?;
    if !manifest.is_object() {
        return Err(unavailable());
    }
    Ok(project(&manifest, desktop()))
}

#[tauri::command]
async fn about_info(about: State<'_, Arc<About>>) -> Result<AboutInfo> {
    let (root, manifest) = (about.root.clone(), about.manifest.clone());
    blocking(move || read(&About { root, manifest })).await
}

pub fn commands<R: tauri::Runtime>() -> Commands<R> {
    crate::app::commands![about_info]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn host() -> Desktop {
        Desktop {
            version: Some("0.6.0".into()),
            build_id: None,
            build_type: "debug".into(),
        }
    }

    fn manifest(text: &str) -> Value {
        serde_json::from_str(text).unwrap()
    }

    #[test]
    fn a_full_manifest_projects_every_field_and_sorts_lists_by_name() {
        let info = project(
            &manifest(
                r#"{
                "build": {"product": "Cadrumo", "version": "0.6.0",
                  "build_date": "2026-10-19T08:00:00Z", "channel": "stable",
                  "target": "windows-x86-64", "build_id": "2026101903",
                  "build_sequence": 412, "build_type": "debug",
                  "display_version": "0.6.0+2026101903.debug", "build_number": 412},
                "python": "3.13.11",
                "agent": {"bundled": true, "version": "1.2.0",
                  "dependencies": [{"name": "langgraph", "version": "1.2.3"},
                                   {"name": "anyio", "version": "4.0.0"}]},
                "components": [{"name": "cadrumo", "role": "desktop",
                  "path": "bin/cadrumo.exe", "version": "0.6.0",
                  "build_id": "2026101903", "build_type": "debug"}],
                "tools": {"node": "22.1.0"},
                "distributions": {"zeta": "1", "Alpha": "2", "beta": "3"}
            }"#,
            ),
            host(),
        );
        assert_eq!(info.display_version.as_deref(), Some("0.6.0+2026101903.debug"));
        assert_eq!(info.build_id.as_deref(), Some("2026101903"));
        assert_eq!(info.build_type.as_deref(), Some("debug"));
        assert_eq!(info.channel.as_deref(), Some("stable"));
        assert_eq!(info.python.as_deref(), Some("3.13.11"));
        assert_eq!(info.desktop, host());
        let agent = info.agent.unwrap();
        assert_eq!(agent.version.as_deref(), Some("1.2.0"));
        assert_eq!(
            agent
                .dependencies
                .iter()
                .map(|d| d.name.as_str())
                .collect::<Vec<_>>(),
            ["anyio", "langgraph"]
        );
        assert_eq!(info.components.len(), 1);
        assert_eq!(info.components[0].role.as_deref(), Some("desktop"));
        assert_eq!(info.tools["node"], "22.1.0");
        assert_eq!(
            info.distributions
                .iter()
                .map(|d| d.name.as_str())
                .collect::<Vec<_>>(),
            ["Alpha", "beta", "zeta"]
        );
    }

    #[test]
    fn keys_the_manifest_does_not_state_stay_absent() {
        let info = project(
            &manifest(r#"{"build": {"version": "0.6.0"}, "python": "3.13.11", "distributions": {}}"#),
            host(),
        );
        assert_eq!(info.version.as_deref(), Some("0.6.0"));
        assert_eq!(info.build_id, None);
        assert_eq!(info.build_type, None);
        assert_eq!(info.display_version, None);
        assert!(info.components.is_empty());
        assert!(info.tools.is_empty());
        assert!(info.agent.is_none());
    }

    #[test]
    fn an_interpreter_only_package_has_no_agent() {
        let info = project(
            &manifest(r#"{"agent": {"bundled": false, "version": "9"}}"#),
            host(),
        );
        assert!(info.agent.is_none());
    }

    #[test]
    fn malformed_entries_are_skipped_not_invented() {
        let info = project(
            &manifest(
                r#"{"agent": {"dependencies": [{"name": "a"}, {"version": "1"}, {"name": "b", "version": "2"}]},
                    "distributions": {"x": 3, "y": "1"}, "tools": {"node": 22}}"#,
            ),
            host(),
        );
        let agent = info.agent.unwrap();
        assert_eq!(agent.version, None);
        assert_eq!(agent.dependencies.len(), 1);
        assert_eq!(agent.dependencies[0].name, "b");
        assert_eq!(info.distributions.len(), 1);
        assert!(info.tools.is_empty());
    }

    #[test]
    fn the_desktop_entry_reports_its_own_profile() {
        let own = desktop();
        assert_eq!(
            own.build_type,
            if cfg!(debug_assertions) { "debug" } else { "release" }
        );
    }

    #[test]
    fn an_unreadable_manifest_is_a_precise_refusal() {
        let about = About {
            root: PathBuf::from("this-directory-does-not-exist"),
            manifest: Some(RelativePath::new("data/package-manifest.json").unwrap()),
        };
        assert_eq!(read(&about).unwrap_err().code, ErrorCode::ReadFailed);
        let without = About {
            root: PathBuf::new(),
            manifest: None,
        };
        assert_eq!(read(&without).unwrap_err().code, ErrorCode::PackageUnavailable);
    }
}
