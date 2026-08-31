# AEAT registry bindings

- Each relationship family has a typed declaration, a typed validator enrolled in the canonical dispatch table, and a resolver at its owning public module.
- Validation rejects unknown family names, invalid selectors, ambiguous targets, incompatible revisions, missing provenance, and unresolvable legal references. Do not accept a generic mapping and defer interpretation to callers.
- Aggregation source families use the canonical typed aggregation enum and resolver. A binding must not introduce a private summation path.
- Source taxonomy distinguishes filing-grade, advisory, deferred, unsupported, and absent states. Consumers preserve that classification instead of converting it to a boolean or zero.
- Binding provenance identifies the registry declaration and governing authority and survives into the resolved result and explanation.
- Relation prefill is derived from the validated relationship and active filing context. User-supplied or imported values never silently override a higher-authority binding.
- New binding families follow the existing defining-module pattern and are exercised through registry validation, positive resolution, ambiguity/refusal, and consumer parity tests.
