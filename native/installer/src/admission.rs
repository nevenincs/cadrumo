//! Scope policy over a complete native inventory; no registry-name heuristics.
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const MAX_DATA_BYTES: usize = 8192;
pub const MAX_PRODUCTS: usize = 32768;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Scope {
    User,
    Machine,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub schema: u32,
    pub scope: Scope,
    /// Both immutable-version and stable-registration families in this scope.
    pub permitted_families: [String; 2],
    /// Opposite-scope version/registration and the unreleased legacy combined family.
    pub conflicting_families: [String; 3],
}

#[derive(Clone, Debug)]
pub struct Product {
    pub code: String,
    pub family: Option<String>,
    pub scope: Scope,
    /// Machine products have no SID. User products must identify an account.
    pub sid: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Refusal {
    InvalidRequest,
    IncompleteInventory,
    ConflictingScope,
    AmbiguousOwnership,
    NativeFailure,
    InUse,
}

impl Refusal {
    pub fn message(self) -> &'static str {
        match self {
            Self::InvalidRequest => "Invalid installer maintenance request.",
            Self::IncompleteInventory => {
                "Native installation inventory could not be proved complete."
            }
            Self::ConflictingScope => {
                "A conflicting installation scope or legacy product is present."
            }
            Self::AmbiguousOwnership => "Native product ownership is ambiguous.",
            Self::NativeFailure => "Native installer maintenance failed.",
            Self::InUse => "Program files are in use; native removal must be deferred.",
        }
    }
}

pub fn canonical_guid(value: &str) -> Result<String, Refusal> {
    let value = value
        .strip_prefix('{')
        .and_then(|v| v.strip_suffix('}'))
        .unwrap_or(value);
    if value.len() != 36
        || value.bytes().enumerate().any(|(i, b)| {
            if [8, 13, 18, 23].contains(&i) {
                b != b'-'
            } else {
                !b.is_ascii_hexdigit()
            }
        })
    {
        return Err(Refusal::InvalidRequest);
    }
    Ok(value.to_ascii_uppercase())
}

impl Request {
    pub fn parse(value: &str) -> Result<Self, Refusal> {
        if value.len() > MAX_DATA_BYTES || value.contains('\0') {
            return Err(Refusal::InvalidRequest);
        }
        let mut request: Self = serde_json::from_str(value).map_err(|_| Refusal::InvalidRequest)?;
        if request.schema != 1 {
            return Err(Refusal::InvalidRequest);
        }
        let mut seen = BTreeSet::new();
        for family in request
            .permitted_families
            .iter_mut()
            .chain(request.conflicting_families.iter_mut())
        {
            *family = canonical_guid(family)?;
            if !seen.insert(family.clone()) {
                return Err(Refusal::InvalidRequest);
            }
        }
        Ok(request)
    }

    /// Call only after the native enumerator reaches ERROR_NO_MORE_ITEMS. Failure,
    /// truncation and inaccessible cached ownership are never an empty inventory.
    pub fn admit(&self, products: &[Product]) -> Result<(), Refusal> {
        if products.len() > MAX_PRODUCTS {
            return Err(Refusal::IncompleteInventory);
        }
        let mut seen = BTreeSet::new();
        for product in products {
            let code = canonical_guid(&product.code).map_err(|_| Refusal::AmbiguousOwnership)?;
            match (product.scope, product.sid.as_deref()) {
                (Scope::Machine, None) => {}
                (Scope::User, Some(sid)) if sid.starts_with("S-1-") && sid.len() <= 184 => {}
                _ => return Err(Refusal::AmbiguousOwnership),
            }
            if !seen.insert((code, product.sid.clone())) {
                return Err(Refusal::AmbiguousOwnership);
            }
            let Some(family) = &product.family else {
                continue;
            };
            let family = canonical_guid(family).map_err(|_| Refusal::AmbiguousOwnership)?;
            if self.conflicting_families.contains(&family) {
                return Err(Refusal::ConflictingScope);
            }
            if self.permitted_families.contains(&family) && product.scope != self.scope {
                return Err(Refusal::AmbiguousOwnership);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn request() -> Request {
        Request::parse(r#"{"schema":1,"scope":"user","permitted_families":["10000000-0000-0000-0000-000000000000","20000000-0000-0000-0000-000000000000"],"conflicting_families":["30000000-0000-0000-0000-000000000000","40000000-0000-0000-0000-000000000000","50000000-0000-0000-0000-000000000000"]}"#).unwrap()
    }
    fn product(family: String, scope: Scope) -> Product {
        Product {
            code: "a0000000-0000-0000-0000-000000000000".into(),
            family: Some(family),
            scope,
            sid: if scope == Scope::User {
                Some("S-1-5-21-1000".into())
            } else {
                None
            },
        }
    }
    #[test]
    fn admits_empty_and_same_scope_but_refuses_each_conflicting_family() {
        let request = request();
        assert_eq!(request.admit(&[]), Ok(()));
        assert_eq!(
            request.admit(&[product(request.permitted_families[0].clone(), Scope::User)]),
            Ok(())
        );
        for family in &request.conflicting_families {
            assert_eq!(
                request.admit(&[product(family.clone(), Scope::Machine)]),
                Err(Refusal::ConflictingScope)
            );
        }
    }
    #[test]
    fn rejects_context_drift_duplicate_records_and_missing_account() {
        let request = request();
        let mut item = product(request.permitted_families[0].clone(), Scope::Machine);
        assert_eq!(
            request.admit(&[item.clone()]),
            Err(Refusal::AmbiguousOwnership)
        );
        item.scope = Scope::User;
        assert_eq!(
            request.admit(&[item.clone()]),
            Err(Refusal::AmbiguousOwnership)
        );
        item.sid = Some("S-1-5-21-1000".into());
        assert_eq!(
            request.admit(&[item.clone(), item]),
            Err(Refusal::AmbiguousOwnership)
        );
    }
    #[test]
    fn rejects_unbounded_unknown_duplicate_or_malformed_fields() {
        assert!(Request::parse(&"x".repeat(MAX_DATA_BYTES + 1)).is_err());
        let value = serde_json::to_string(&request()).unwrap();
        assert!(
            Request::parse(&value.replace("\"schema\":1", "\"schema\":1,\"extra\":0")).is_err()
        );
        assert!(
            Request::parse(&value.replace("\"schema\":1", "\"schema\":1,\"schema\":1")).is_err()
        );
        assert!(Request::parse(&value.replace("20000000", "10000000")).is_err());
        assert!(Request::parse(&value.replace("10000000", "no_guid_")).is_err());
    }
}
