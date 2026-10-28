//! The closed set of setup items and where each one lives under the storage root.
//!
//! Two pieces of outside software make Cadrumo work: the browser that reads the tax
//! agency's website, and the local AI, which is the program that runs models together
//! with the model the person selected for each local role. Each is one item, set up once
//! for the whole installation, in this order. The local AI's program and models are parts
//! of its plan, never items of their own; with no local selection the item is the
//! program alone.

use serde::{Deserialize, Serialize};
use std::{fmt, path::PathBuf, time::Duration};

/// One setup item; the identity doubles as the progress subject and a phase-code segment.
#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ItemId {
    Browser,
    LocalAi,
}

impl ItemId {
    /// Every item, in setup order.
    pub const ALL: [Self; 2] = [Self::Browser, Self::LocalAi];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Browser => "browser",
            Self::LocalAi => "local_ai",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        Self::ALL.into_iter().find(|item| item.as_str() == value)
    }

    pub fn declaration(self) -> &'static ItemDeclaration {
        match self {
            Self::Browser => &BROWSER,
            Self::LocalAi => &LOCAL_AI,
        }
    }
}

impl fmt::Display for ItemId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// The local AI's program part.
pub const PROGRAM_PART: &str = "program";

/// Bound for one item's, or one part's, full check.
pub const FULL_CHECK_BUDGET: Duration = Duration::from_secs(60);

/// What the engine knows about an item before anything is probed. `display_key` and
/// `recovery_action` are identities: the item's plain name in the locale catalogues,
/// and the operator action a refusal for this item offers.
#[derive(Debug, Eq, PartialEq)]
pub struct ItemDeclaration {
    pub id: ItemId,
    pub display_key: &'static str,
    pub recovery_action: &'static str,
    pub full_check_budget: Duration,
}

pub static BROWSER: ItemDeclaration = ItemDeclaration {
    id: ItemId::Browser,
    display_key: "provisioning.dependency.browser.name",
    recovery_action: "operator.provision.browser",
    full_check_budget: FULL_CHECK_BUDGET,
};

pub static LOCAL_AI: ItemDeclaration = ItemDeclaration {
    id: ItemId::LocalAi,
    display_key: "provisioning.dependency.local_ai.name",
    recovery_action: "operator.provision.local_ai",
    // The program's bound; each selected model's check is bounded on its own.
    full_check_budget: FULL_CHECK_BUDGET,
};

/// Where a plan stores what it downloads; the codes are the storage categories' names.
#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
pub enum Destination {
    #[serde(rename = "playwright-browsers")]
    PlaywrightBrowsers,
    #[serde(rename = "ollama-models")]
    OllamaModels,
    #[serde(rename = "local-ai-program")]
    LocalAiProgram,
}

/// The installation-wide component locations under one storage root. Components are
/// public artifacts outside encrypted custody, shared by every profile.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Locations {
    pub browsers: PathBuf,
    pub models: PathBuf,
    pub ollama_home: PathBuf,
    /// The program's versions, one folder each.
    pub programs: PathBuf,
    pub receipts: PathBuf,
    /// The per-item writer locks and activity records.
    pub activity: PathBuf,
}

impl Locations {
    /// The default layout under `root`, the owner-resolved storage root. An owner that
    /// honours a relocated browsers, models or home folder replaces that member.
    pub fn under(root: &std::path::Path) -> Self {
        let components = root.join("components");
        Self {
            browsers: components.join("playwright"),
            models: root.join("models").join("ollama"),
            ollama_home: components.join("ollama").join("home"),
            programs: components.join("ollama"),
            receipts: components.join("receipts"),
            activity: components.join("activity"),
        }
    }

    pub fn destination(&self, destination: Destination) -> &std::path::Path {
        match destination {
            Destination::PlaywrightBrowsers => &self.browsers,
            Destination::OllamaModels => &self.models,
            Destination::LocalAiProgram => &self.programs,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn items_keep_their_ids_recovery_actions_and_order() {
        assert_eq!(ItemId::ALL.map(ItemId::as_str), ["browser", "local_ai"]);
        assert_eq!(
            ItemId::ALL.map(|item| item.declaration().recovery_action),
            ["operator.provision.browser", "operator.provision.local_ai"]
        );
        for item in ItemId::ALL {
            assert_eq!(item.declaration().id, item);
            assert_eq!(ItemId::parse(item.as_str()), Some(item));
            assert_eq!(
                serde_json::to_value(item).unwrap(),
                serde_json::Value::String(item.as_str().into())
            );
        }
        assert_eq!(ItemId::parse("google"), None);
        assert_eq!(LOCAL_AI.full_check_budget, Duration::from_secs(60));
    }

    #[test]
    fn components_live_under_the_storage_root_as_the_storage_ruling_places_them() {
        let root = Path::new("/state");
        let locations = Locations::under(root);
        assert_eq!(locations.browsers, root.join("components/playwright"));
        assert_eq!(locations.models, root.join("models/ollama"));
        assert_eq!(locations.ollama_home, root.join("components/ollama/home"));
        assert_eq!(locations.receipts, root.join("components/receipts"));
        assert_eq!(
            locations.destination(Destination::LocalAiProgram),
            root.join("components/ollama")
        );
    }
}
