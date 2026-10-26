use crate::package::{PackageInspection, Readiness};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Requirement {
    PythonDistribution { name: String, version: String },
    Component { id: String, revision: String },
    UserAction { action: String },
    Unimplemented { reason: String },
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Capability {
    pub id: String,
    pub requirements: Vec<Requirement>,
}

impl Capability {
    /// Return every unmet condition, so an optional dependency cannot mask user consent.
    pub fn inspect(
        &self,
        package: &PackageInspection,
        components: &BTreeMap<(String, String), Readiness>,
    ) -> Vec<Readiness> {
        let mut findings = Vec::new();
        if package.readiness != Readiness::Ready {
            findings.push(package.readiness.clone());
        }
        for requirement in &self.requirements {
            let state = match requirement {
                Requirement::PythonDistribution { name, version } => {
                    match package.manifest.distributions.get(name) {
                        Some(actual) if actual == version => Readiness::Ready,
                        Some(_) => Readiness::Incompatible(format!("Python distribution: {name}")),
                        None => Readiness::Missing(format!("Python distribution: {name}")),
                    }
                }
                Requirement::Component { id, revision } => components
                    .get(&(id.clone(), revision.clone()))
                    .cloned()
                    .unwrap_or_else(|| Readiness::Missing(format!("component: {id}@{revision}"))),
                Requirement::UserAction { action } => Readiness::NeedsUser(action.clone()),
                Requirement::Unimplemented { reason } => Readiness::Incompatible(reason.clone()),
            };
            if state != Readiness::Ready {
                findings.push(state);
            }
        }
        if findings.is_empty() {
            findings.push(Readiness::Ready);
        }
        findings
    }
}
