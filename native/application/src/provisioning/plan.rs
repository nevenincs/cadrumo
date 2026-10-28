//! The setup plan a person approves before any byte moves, and the digest the approval
//! binds.
//!
//! A plan lists, per item, how much it downloads, from which hosts and to where. The local
//! AI's entry is made of ordered parts, the program and then one per role the person
//! selected a local model for, and is exactly their sum; roles that share one model count
//! its download once. A model part is the selection triple itself: its id is the role,
//! its target version the model's name and its size the size the selected catalogue
//! entry states. A plan carries no licence or fit notice: the person saw the catalogue
//! entry's licence and facts when they selected the model. The digest covers the contract
//! version and every entry in order, spelled as the product's canonical JSON, so a changed role,
//! model name, size, host, destination, version or item set needs a new approval while a
//! re-measured free space does not.

use super::items::{Destination, ItemId};
use crate::{
    canonical_json::canonical_json,
    error::Error,
    value::{HostName, Sha256Digest},
};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::BTreeSet;

/// Folded into every digest so a plan-shape change can never reuse an approval.
pub const PLAN_CONTRACT_VERSION: u32 = 3;

/// Fixed free space kept beyond the planned download, on top of the 20 % margin.
pub const SPACE_HEADROOM_BYTES: u64 = 1024 * 1024 * 1024;

/// The free space a download needs: its size plus 20 %, rounded up, plus 1 GiB.
pub fn required_free_bytes(download_bytes: u64) -> u64 {
    let margin = (u128::from(download_bytes) * 6).div_ceil(5);
    u64::try_from(margin)
        .unwrap_or(u64::MAX)
        .saturating_add(SPACE_HEADROOM_BYTES)
}

/// One piece of an item's plan: the local AI program, or the model the person selected for
/// one role. `download_bytes` is `None` when the source does not say in advance.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PlanPart {
    pub part_id: String,
    pub download_bytes: Option<u64>,
    pub source_hosts: Vec<HostName>,
    pub destination: Option<Destination>,
    pub installs_outside_program: bool,
    pub target_version: Option<String>,
}

impl PlanPart {
    fn download_key(&self) -> Option<(Destination, &str)> {
        Some((self.destination?, self.target_version.as_deref()?))
    }

    fn value(&self) -> Value {
        json!({
            "part_id": self.part_id,
            "download_bytes": self.download_bytes,
            "source_hosts": self.source_hosts,
            "destination": self.destination,
            "installs_outside_program": self.installs_outside_program,
            "target_version": self.target_version,
        })
    }
}

/// What setting up one item will do.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PlanEntry {
    pub item: ItemId,
    pub download_bytes: Option<u64>,
    pub source_hosts: Vec<HostName>,
    pub destination: Option<Destination>,
    pub installs_outside_program: bool,
    pub target_version: Option<String>,
    pub parts: Vec<PlanPart>,
}

fn unique_hosts(hosts: &[HostName]) -> bool {
    hosts.iter().collect::<BTreeSet<_>>().len() == hosts.len()
}

fn invalid(what: &str) -> Error {
    Error::Invalid(format!("setup plan: {what}"))
}

impl PlanEntry {
    /// An entry planned as one download.
    pub fn whole(
        item: ItemId,
        download_bytes: Option<u64>,
        source_hosts: Vec<HostName>,
        destination: Destination,
        target_version: Option<String>,
    ) -> Result<Self, Error> {
        if source_hosts.is_empty() || !unique_hosts(&source_hosts) {
            return Err(invalid("an entry names each source host once"));
        }
        Ok(Self {
            item,
            download_bytes,
            source_hosts,
            destination: Some(destination),
            installs_outside_program: false,
            target_version,
            parts: Vec::new(),
        })
    }

    /// The local AI's entry: exactly the sum of its ordered parts.
    pub fn of_parts(
        item: ItemId,
        parts: Vec<PlanPart>,
        destination: Destination,
    ) -> Result<Self, Error> {
        if item != ItemId::LocalAi {
            return Err(invalid("only the local AI is planned in parts"));
        }
        let mut ids = BTreeSet::new();
        for part in &parts {
            if !ids.insert(part.part_id.as_str())
                || part.source_hosts.is_empty()
                || !unique_hosts(&part.source_hosts)
                || (part.destination.is_none() && !part.installs_outside_program)
            {
                return Err(invalid("a part names its id, hosts and destination once"));
            }
        }
        if parts.is_empty() {
            return Err(invalid("an entry in parts has at least one part"));
        }
        let mut hosts: Vec<HostName> = Vec::new();
        for host in parts.iter().flat_map(|part| &part.source_hosts) {
            if !hosts.contains(host) {
                hosts.push(host.clone());
            }
        }
        Ok(Self {
            item,
            download_bytes: Some(known_part_bytes(&parts)),
            source_hosts: hosts,
            destination: Some(destination),
            installs_outside_program: parts.iter().any(|part| part.installs_outside_program),
            target_version: None,
            parts,
        })
    }

    /// Whether the entry, or any of its parts, downloads an amount its source does not
    /// state in advance.
    pub fn has_unknown_size(&self) -> bool {
        self.download_bytes.is_none() || self.parts.iter().any(|part| part.download_bytes.is_none())
    }

    fn download_key(&self) -> Option<(Destination, &str)> {
        Some((self.destination?, self.target_version.as_deref()?))
    }

    fn value(&self) -> Value {
        json!({
            "item_id": self.item,
            "download_bytes": self.download_bytes,
            "source_hosts": self.source_hosts,
            "destination": self.destination,
            "installs_outside_program": self.installs_outside_program,
            "target_version": self.target_version,
            "parts": self.parts.iter().map(PlanPart::value).collect::<Vec<_>>(),
        })
    }
}

/// The known sizes of `parts`, counting each shared download once.
fn known_part_bytes(parts: &[PlanPart]) -> u64 {
    let mut seen = BTreeSet::new();
    parts
        .iter()
        .filter(|part| part.download_key().is_none_or(|key| seen.insert(key)))
        .filter_map(|part| part.download_bytes)
        .fold(0, u64::saturating_add)
}

/// Free space measured on the storage volume against what the plan needs. A volume that
/// could not be measured is never read as enough. What setups of other items running now
/// have yet to download to the volume is `reserved_bytes`, and is needed on top of the
/// plan's own download.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub struct SpaceCheck {
    pub free_bytes: Option<u64>,
    pub reserved_bytes: u64,
    pub required_bytes: u64,
}

impl SpaceCheck {
    pub fn sufficient(&self) -> bool {
        self.free_bytes
            .is_some_and(|free| free >= self.required_bytes)
    }
}

/// The ordered plan a person approves.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SetupPlan {
    pub entries: Vec<PlanEntry>,
    pub space: SpaceCheck,
}

impl SetupPlan {
    /// Assembles the plan from each item's entry, the measured free space and the bytes
    /// other running setups have reserved on the volume.
    pub fn new(
        entries: Vec<PlanEntry>,
        free_bytes: Option<u64>,
        reserved_bytes: u64,
    ) -> Result<Self, Error> {
        let items: BTreeSet<ItemId> = entries.iter().map(|entry| entry.item).collect();
        if entries.is_empty() || items.len() != entries.len() {
            return Err(invalid("a plan names each item once"));
        }
        let space = SpaceCheck {
            free_bytes,
            reserved_bytes,
            required_bytes: required_free_bytes(
                known_download_bytes(&entries).saturating_add(reserved_bytes),
            ),
        };
        Ok(Self { entries, space })
    }

    /// Bytes the known-size entries download, counting each shared download once.
    pub fn known_download_bytes(&self) -> u64 {
        known_download_bytes(&self.entries)
    }

    pub fn has_unknown_size(&self) -> bool {
        self.entries.iter().any(PlanEntry::has_unknown_size)
    }

    pub fn installs_outside_program(&self) -> bool {
        self.entries
            .iter()
            .any(|entry| entry.installs_outside_program)
    }

    /// Replaces the free-space reading and the other setups' reservation, as setup does
    /// again before the transfer starts; the digest does not change.
    pub fn remeasure(&mut self, free_bytes: Option<u64>, reserved_bytes: u64) {
        self.space = SpaceCheck {
            free_bytes,
            reserved_bytes,
            required_bytes: required_free_bytes(
                self.known_download_bytes().saturating_add(reserved_bytes),
            ),
        };
    }

    /// The document the digest is taken of.
    pub fn digest_document(&self) -> Value {
        json!({
            "contract_version": PLAN_CONTRACT_VERSION,
            "entries": self.entries.iter().map(PlanEntry::value).collect::<Vec<_>>(),
        })
    }

    /// The digest an approval of this plan binds.
    pub fn digest(&self) -> Sha256Digest {
        Sha256Digest::of(canonical_json(&self.digest_document()))
    }
}

fn known_download_bytes(entries: &[PlanEntry]) -> u64 {
    let mut seen = BTreeSet::new();
    entries
        .iter()
        .filter(|entry| entry.download_key().is_none_or(|key| seen.insert(key)))
        .filter_map(|entry| entry.download_bytes)
        .fold(0, u64::saturating_add)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hosts(names: &[&str]) -> Vec<HostName> {
        names
            .iter()
            .map(|name| HostName::new(*name).unwrap())
            .collect()
    }

    fn model(role: &str, bytes: Option<u64>, version: Option<&str>) -> PlanPart {
        PlanPart {
            part_id: role.into(),
            download_bytes: bytes,
            source_hosts: hosts(&["registry.ollama.ai"]),
            destination: Some(Destination::OllamaModels),
            installs_outside_program: false,
            target_version: version.map(str::to_owned),
        }
    }

    /// Obviously synthetic names: the engine knows no model, so its tests name none.
    const TEXT: &str = "synthetic-text:test";
    const VISION: &str = "synthetic-vision:test";

    fn sample() -> SetupPlan {
        let browser = PlanEntry::whole(
            ItemId::Browser,
            Some(325_461_569),
            hosts(&["cdn.playwright.dev"]),
            Destination::PlaywrightBrowsers,
            Some("chromium-1248".into()),
        )
        .unwrap();
        let program = PlanPart {
            part_id: "program".into(),
            download_bytes: Some(1_586_229_413),
            source_hosts: hosts(&["github.com", "release-assets.githubusercontent.com"]),
            destination: None,
            installs_outside_program: true,
            target_version: Some("0.40.10".into()),
        };
        let local = PlanEntry::of_parts(
            ItemId::LocalAi,
            vec![
                program,
                model("column_role_mapping", Some(5_000), Some(TEXT)),
                model("supply_nature_proposal", None, None),
                model("text_extraction", Some(5_000), Some(TEXT)),
                model("vision_transcription", Some(7_000), Some(VISION)),
            ],
            Destination::OllamaModels,
        )
        .unwrap();
        SetupPlan::new(vec![browser, local], Some(10), 0).unwrap()
    }

    #[test]
    fn the_digest_is_the_products_digest_of_the_same_plan() {
        let plan = sample();
        // The SHA-256 of this plan's document, written out by hand and serialised by the
        // product's Python canonical JSON (`content_hash_hex`), not by this crate.
        assert_eq!(
            plan.digest().as_str(),
            "4d8d19a2ea5da69c0ebc4275ae72a0ac56b086218a0c61230afa4da5a9ffe546"
        );
        assert_eq!(plan.entries[1].download_bytes, Some(1_586_241_413));
        assert_eq!(plan.space.required_bytes, 3_367_785_403);
        assert!(plan.has_unknown_size());
        assert!(!plan.space.sufficient());
    }

    #[test]
    fn the_digest_binds_what_is_downloaded_and_not_the_volume_reading() {
        let plan = sample();
        let mut remeasured = plan.clone();
        remeasured.remeasure(Some(u64::MAX), 0);
        assert!(remeasured.space.sufficient());
        assert_eq!(remeasured.digest(), plan.digest());
        // Another setup's reservation is needed on top, yet asks for no new approval.
        let enough = plan.space.required_bytes;
        remeasured.remeasure(Some(enough), 0);
        assert!(remeasured.space.sufficient());
        remeasured.remeasure(Some(enough), 1_000);
        assert_eq!(
            remeasured.space.required_bytes,
            required_free_bytes(plan.known_download_bytes() + 1_000)
        );
        assert!(!remeasured.space.sufficient());
        assert_eq!(remeasured.digest(), plan.digest());
        let mut resized = plan.clone();
        resized.entries[0].download_bytes = Some(1);
        assert_ne!(resized.digest(), plan.digest());
        let mut rehosted = plan.clone();
        rehosted.entries[0].source_hosts = hosts(&["storage.googleapis.com"]);
        assert_ne!(rehosted.digest(), plan.digest());
        // Each part of a selection triple: the model's name, its size and its role.
        let mut renamed = plan.clone();
        renamed.entries[1].parts[3].target_version = Some("synthetic-text:other".into());
        assert_ne!(renamed.digest(), plan.digest());
        let mut model_resized = plan.clone();
        model_resized.entries[1].parts[4].download_bytes = Some(7_001);
        assert_ne!(model_resized.digest(), plan.digest());
        let mut reassigned = plan.clone();
        reassigned.entries[1].parts[3].part_id = "statement_reading".into();
        assert_ne!(reassigned.digest(), plan.digest());
        let browser_only = SetupPlan::new(vec![plan.entries[0].clone()], None, 0).unwrap();
        assert_ne!(browser_only.digest(), plan.digest());
        assert!(
            !browser_only.space.sufficient(),
            "an unmeasured volume is never enough"
        );
    }

    #[test]
    fn free_space_is_the_plan_size_plus_a_fifth_plus_one_gibibyte() {
        assert_eq!(required_free_bytes(0), SPACE_HEADROOM_BYTES);
        assert_eq!(required_free_bytes(5), 6 + SPACE_HEADROOM_BYTES);
        assert_eq!(required_free_bytes(1), 2 + SPACE_HEADROOM_BYTES);
        assert_eq!(required_free_bytes(u64::MAX), u64::MAX);
        let check = SpaceCheck {
            free_bytes: Some(required_free_bytes(100)),
            reserved_bytes: 0,
            required_bytes: required_free_bytes(100),
        };
        assert!(check.sufficient());
    }

    #[test]
    fn malformed_plans_are_refused() {
        let browser = sample().entries[0].clone();
        assert!(SetupPlan::new(vec![browser.clone(), browser.clone()], None, 0).is_err());
        assert!(SetupPlan::new(Vec::new(), None, 0).is_err());
        assert!(
            PlanEntry::whole(
                ItemId::Browser,
                None,
                hosts(&["cdn.playwright.dev", "cdn.playwright.dev"]),
                Destination::PlaywrightBrowsers,
                None,
            )
            .is_err()
        );
        assert!(
            PlanEntry::of_parts(
                ItemId::Browser,
                vec![model("a", None, None)],
                Destination::OllamaModels
            )
            .is_err()
        );
        assert!(
            PlanEntry::of_parts(
                ItemId::LocalAi,
                vec![model("a", None, None), model("a", None, None)],
                Destination::OllamaModels,
            )
            .is_err()
        );
        let mut nowhere = model("a", None, None);
        nowhere.destination = None;
        assert!(
            PlanEntry::of_parts(ItemId::LocalAi, vec![nowhere], Destination::OllamaModels).is_err()
        );
        assert!(
            PlanEntry::of_parts(ItemId::LocalAi, Vec::new(), Destination::OllamaModels).is_err()
        );
    }
}
