//! Composing a page from its stored structure and one language's strings.
//!
//! The package holds one structure per page and, for each language, the text
//! that language reads in it. `dev/docs/shared_structure.py` writes both; this
//! is the reader's half of that format.

/// The private-use characters that delimit a slot number in a structure. A
/// page containing either is refused when the structure is written, so a
/// delimiter is never content.
pub const SLOT_OPEN: char = '\u{e000}';
pub const SLOT_CLOSE: char = '\u{e001}';

const DIGITS: usize = 36;

/// The page a structure reads as in the language `strings` belongs to.
///
/// `None` means the stored form is broken: a malformed slot, or a slot the
/// language has no string for. A caller must then serve nothing, because half
/// a composed page is not a page.
pub fn page(structure: &str, strings: &[String]) -> Option<String> {
    let mut composed = String::with_capacity(structure.len());
    let mut rest = structure;
    while let Some(open) = rest.find(SLOT_OPEN) {
        let (literal, slot) = (&rest[..open], &rest[open + SLOT_OPEN.len_utf8()..]);
        let close = slot.find(SLOT_CLOSE)?;
        if literal.contains(SLOT_CLOSE) {
            return None;
        }
        composed.push_str(literal);
        composed.push_str(strings.get(number(&slot[..close])?)?);
        rest = &slot[close + SLOT_CLOSE.len_utf8()..];
    }
    if rest.contains(SLOT_CLOSE) {
        return None;
    }
    composed.push_str(rest);
    Some(composed)
}

/// A slot number: lowercase base 36, no sign and no padding, so one number
/// has one spelling and a structure cannot hide a different one.
fn number(digits: &str) -> Option<usize> {
    if digits.is_empty() || (digits.len() > 1 && digits.starts_with('0')) {
        return None;
    }
    digits.bytes().try_fold(0usize, |value, byte| {
        let digit = match byte {
            b'0'..=b'9' => usize::from(byte - b'0'),
            b'a'..=b'z' => usize::from(byte - b'a') + 10,
            _ => return None,
        };
        value.checked_mul(DIGITS)?.checked_add(digit)
    })
}
