//! Strict reading of one flat JSON object for the protocol and the boot record.
//!
//! Both grammars hold only scalar members, so a repeated member name, a nested value or a
//! leftover member is a refusal. Members are taken by name and the rest must be empty.

use serde::de::{self, Deserialize, Deserializer, MapAccess, Visitor};
use serde_json::Value;
use std::fmt;

/// Members of one JSON object in document order.
pub(crate) struct FlatObject(Vec<(String, Value)>);

impl FlatObject {
    /// Parse `bytes` as exactly one flat object; surrounding JSON whitespace is allowed.
    pub(crate) fn parse(bytes: &[u8]) -> Option<Self> {
        serde_json::from_slice(bytes).ok()
    }

    /// Remove and return the member called `name`.
    pub(crate) fn take(&mut self, name: &str) -> Option<Value> {
        let index = self.0.iter().position(|(key, _)| key == name)?;
        Some(self.0.swap_remove(index).1)
    }

    /// Whether every member has been taken.
    pub(crate) fn is_exhausted(&self) -> bool {
        self.0.is_empty()
    }
}

impl<'de> Deserialize<'de> for FlatObject {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        deserializer.deserialize_map(FlatObjectVisitor)
    }
}

struct FlatObjectVisitor;

impl<'de> Visitor<'de> for FlatObjectVisitor {
    type Value = FlatObject;

    fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
        formatter.write_str("one JSON object with scalar members")
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<FlatObject, A::Error> {
        let mut members: Vec<(String, Value)> = Vec::new();
        while let Some(name) = map.next_key::<String>()? {
            if members.iter().any(|(existing, _)| *existing == name) {
                return Err(de::Error::custom("repeated member"));
            }
            let value: Value = map.next_value()?;
            if value.is_object() || value.is_array() {
                return Err(de::Error::custom("nested member"));
            }
            members.push((name, value));
        }
        Ok(FlatObject(members))
    }
}

/// An unsigned integer in `minimum..=maximum`; floats, booleans and strings are refused.
pub(crate) fn unsigned(value: &Value, minimum: u64, maximum: u64) -> Option<u64> {
    value
        .as_u64()
        .filter(|number| (minimum..=maximum).contains(number))
}

/// A string of `1..=maximum` Unicode scalar values.
pub(crate) fn text(value: &Value, maximum: usize) -> Option<&str> {
    value
        .as_str()
        .filter(|text| (1..=maximum).contains(&text.chars().count()))
}

/// A UUID in the canonical lowercase hyphenated form the runtime writes.
pub(crate) fn canonical_uuid(value: &Value) -> Option<&str> {
    let text = value.as_str()?;
    let canonical = text.len() == 36
        && text.bytes().enumerate().all(|(index, byte)| match index {
            8 | 13 | 18 | 23 => byte == b'-',
            _ => byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte),
        });
    canonical.then_some(text)
}

/// Whether `text` is 64 lowercase hexadecimal digits.
pub(crate) fn is_hex64(text: &str) -> bool {
    text.len() == 64
        && text
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repeated_and_nested_members_are_refused() {
        assert!(FlatObject::parse(br#"{"a":1,"a":1}"#).is_none());
        assert!(FlatObject::parse(br#"{"a":{"b":1}}"#).is_none());
        assert!(FlatObject::parse(br#"{"a":[1]}"#).is_none());
        assert!(FlatObject::parse(br#"[1]"#).is_none());
        assert!(FlatObject::parse(br#"{"a":1} x"#).is_none());
        assert!(FlatObject::parse(b" {\"a\":1}\r\n").is_some());
    }

    #[test]
    fn integers_are_exact_unsigned_values_within_bounds() {
        let parse = |text: &str| serde_json::from_str::<Value>(text).expect("JSON");
        assert_eq!(unsigned(&parse("0"), 0, 5), Some(0));
        // Python reads `-0` as the integer 0; the runtime never writes it, and this reader
        // refuses the spelling.
        assert_eq!(unsigned(&parse("-0"), 0, 5), None);
        assert_eq!(unsigned(&parse("6"), 0, 5), None);
        assert_eq!(unsigned(&parse("1.0"), 0, 5), None);
        assert_eq!(unsigned(&parse("1e0"), 0, 5), None);
        assert_eq!(unsigned(&parse("true"), 0, 5), None);
        assert_eq!(unsigned(&parse("-1"), 0, 5), None);
        assert_eq!(unsigned(&parse("18446744073709551616"), 0, u64::MAX), None);
    }

    #[test]
    fn identifiers_take_only_their_canonical_form() {
        let uuid = Value::from("0f8fad5b-d9cb-469f-a165-70867728950e");
        assert!(canonical_uuid(&uuid).is_some());
        for refused in [
            "0F8FAD5B-D9CB-469F-A165-70867728950E",
            "0f8fad5bd9cb469fa16570867728950e",
            "{0f8fad5b-d9cb-469f-a165-70867728950e}",
        ] {
            assert!(canonical_uuid(&Value::from(refused)).is_none(), "{refused}");
        }
        assert!(is_hex64(&"a".repeat(64)));
        assert!(!is_hex64(&"A".repeat(64)));
        assert!(!is_hex64(&"a".repeat(63)));
    }
}
