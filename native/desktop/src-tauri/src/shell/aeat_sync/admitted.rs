//! The registered operations the AEAT sync commands may submit: closed and
//! owned by the host. Every one reads AEAT or the local profile; none submits
//! a return. A definition outside this list is refused before it reaches the
//! relay, and adding one is a decision of its own.
//!
//! The tests pin the list to the shipped operation contract manifest.

/// What an admitted definition may do to the profile's records.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Kind {
    /// Declares no effect that changes records.
    Read,
    /// Reads AEAT and stores what it read in the profile: an outcome that was
    /// not observed is unknown.
    Capture,
    /// Establishes the AEAT session the captures read through.
    Session,
}

/// The areas a run brings, in the fixed order they run.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum Area {
    Census,
    Identity,
    Notifications,
    Vat,
    Filed,
}
impl Area {
    pub(crate) const ORDER: [Area; 5] = [
        Area::Census,
        Area::Identity,
        Area::Notifications,
        Area::Vat,
        Area::Filed,
    ];
    /// The definitions the area's items submit, in the order they run. The
    /// census runs through the existing census session, which has its own
    /// host commands.
    pub(super) fn definitions(self) -> &'static [&'static str] {
        match self {
            Area::Census => &[],
            Area::Identity => &["live.verify.nif-iva", "live.verify.tgvi"],
            Area::Notifications => &["live.notifications.capture"],
            Area::Vat => &["live.iva-wallet.history-capture"],
            Area::Filed => &["live.filed-discover", "live.filed-capture.bulk"],
        }
    }
}

/// Every definition the commands may submit, with what it may do. Sorted, so
/// a duplicate or a missing entry is visible.
pub(super) const ADMITTED: [(&str, Kind); 11] = [
    ("auth.session.acquire", Kind::Session),
    ("live.borrador.100.import", Kind::Capture),
    ("live.filed-capture.bulk", Kind::Capture),
    ("live.filed-discover", Kind::Capture),
    ("live.iva-wallet.history-capture", Kind::Capture),
    ("live.notifications.capture", Kind::Capture),
    ("live.notifications.latest", Kind::Read),
    ("live.notifications.show", Kind::Read),
    ("live.sync.status", Kind::Read),
    ("live.verify.nif-iva", Kind::Capture),
    ("live.verify.tgvi", Kind::Capture),
];

/// The admitted definition named `id`, or none.
pub(super) fn admitted(id: &str) -> Option<(&'static str, Kind)> {
    ADMITTED.iter().copied().find(|(known, _)| *known == id)
}
