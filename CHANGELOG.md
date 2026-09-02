# Changelog

All notable changes to this project are documented here. This file is written by
[release-please](https://github.com/googleapis/release-please) when a release pull
request is opened, not by hand — see [`RELEASING.md`](RELEASING.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-28

### Features

* **boundary:** add dev-path isolation gate for one-way src/dev boundary ([43d7ab1](https://github.com/nevenincs/cadrumo/commit/43d7ab1e60a4901da41921ff2a7896aad533e3dc))
* **conformance:** gate the conformance backlog on a shrink-only ratchet ([a8bb255](https://github.com/nevenincs/cadrumo/commit/a8bb255c7ab399bed672a48ea0588f0c26cb8f23))
* **conformance:** gate the operator review backlog, not the pending backlog ([f0dbdca](https://github.com/nevenincs/cadrumo/commit/f0dbdcae8e3738900473f0a86a75b11f581622d8))
* **conformance:** give the stamp verb an injectable registry root ([3890dd6](https://github.com/nevenincs/cadrumo/commit/3890dd681377a68dbcc968ca0cad62fa357078cb))
* **conformance:** render the composed registry conformance facts without recomputing them ([27fe970](https://github.com/nevenincs/cadrumo/commit/27fe9701e973cbde0edd330ee93a2b6bbec75641))
* **core:** close the revision review-provenance value set ([8b0194f](https://github.com/nevenincs/cadrumo/commit/8b0194f88e12ff6a4a5e27ee52a44901b43001b6))
* **deploy:** bind the docs publish authority to the delivery environment ([b6a10f9](https://github.com/nevenincs/cadrumo/commit/b6a10f91050e3681376c8ce3d16d074bd181c636))
* **dev:** add audit-registry-conformance justfile recipe ([0158ac6](https://github.com/nevenincs/cadrumo/commit/0158ac6c3c88c70198efb3a12f733240dadcf6ff))
* **dev:** add conformance audit --check CI gate and enroll dev/tests in ci-full ([56a79c9](https://github.com/nevenincs/cadrumo/commit/56a79c9a9b7b214ce9694bd44b3044bcf9576dc2))
* **docs:** deliver documentation downstream of a release, never inside it ([ecf1fed](https://github.com/nevenincs/cadrumo/commit/ecf1fedc3dabc09dc0748b05148760366590de60))
* **gates:** measure and bound the tracked files whose disk bytes left their committed bytes ([71556fb](https://github.com/nevenincs/cadrumo/commit/71556fbd149cce47e52c75ec682cf65404bd758c))
* **packaging:** refuse a doomed version at seal time, not only at publication ([be0579d](https://github.com/nevenincs/cadrumo/commit/be0579d287e895b47f8214e033cc80057b8ec0cb))
* **packaging:** retire a superseded plugin identity by declaration, not delete authority ([ed2dd8a](https://github.com/nevenincs/cadrumo/commit/ed2dd8a33d72e4dce53a06e7bb775695ece390b7))
* **packaging:** verify the retirement on every release, not only the one that did it ([fd2e3bd](https://github.com/nevenincs/cadrumo/commit/fd2e3bdf83caca5809dc9b8cb7c247131d78f16e))
* **profile:** report a valid_to that ends nothing, and rule out clock expiry ([da8cba4](https://github.com/nevenincs/cadrumo/commit/da8cba464388056a3377749f8f46965926dafe2a))
* **registry:** add REVISION_REVIEW_DATE_FLOOR to close one-sided signoff horizon ([b55f2de](https://github.com/nevenincs/cadrumo/commit/b55f2def84692ec77fcad49f38b016dc123754ac))
* **registry:** attribute an oracle payload from what it declares, not only its name ([2572b37](https://github.com/nevenincs/cadrumo/commit/2572b379811bc9c48e1c1c32568aadc9f4c22568))
* **registry:** carry registry_validated onto ClassificationCoherenceFinding and ModeloClassificationRow ([8bec35a](https://github.com/nevenincs/cadrumo/commit/8bec35ac37497ce7597b675945cfeefad7de5b12))
* **registry:** declare the per-revision governance stamp ([b3986f4](https://github.com/nevenincs/cadrumo/commit/b3986f43de9a90d88361b676fd3b2b41b21f9df3))
* **registry:** derive the governance stamp field set from its field declarations ([0908c66](https://github.com/nevenincs/cadrumo/commit/0908c66c2de7e438a254565b6c332fc5a7bd0693))
* **registry:** enforce the AEAT manual prorrata percentage as an independent oracle ([d6547bc](https://github.com/nevenincs/cadrumo/commit/d6547bc71dd874a9688bf12df4262bf0c2b7cc00))
* **registry:** join every conformance axis onto one row per revision ([bba6f25](https://github.com/nevenincs/cadrumo/commit/bba6f259a769531f81b35a9fb8635c2744978bc0))
* **registry:** lift the external-oracle grounding fold into an importable library ([2b93b08](https://github.com/nevenincs/cadrumo/commit/2b93b08f080cb7f5fe7559c7f99d052b3133e3ee))
* **registry:** pin the legally load-bearing revision scalars to revision.toml ([abcfe53](https://github.com/nevenincs/cadrumo/commit/abcfe53fd8b8a7143a63dd9e9b70c8dd1c408119))
* **registry:** report classification-axis disagreements and census the dead axes ([bbc05fc](https://github.com/nevenincs/cadrumo/commit/bbc05fcdef4c866ec6a75d90842a7164beac35c4))
* **release:** add the burned-version ledger, seeded with the two deleted releases ([2f5d04e](https://github.com/nevenincs/cadrumo/commit/2f5d04ea826b3f4f99b8224c4ab0b9a069730a65))
* **release:** ask every destination whether it owns the version, not just the index ([84fe635](https://github.com/nevenincs/cadrumo/commit/84fe6350e0eea14e40f71ef1259b91858a90faaf))
* **release:** make every destination converge on a re-dispatch ([be185e7](https://github.com/nevenincs/cadrumo/commit/be185e77cf13b5b1955ba83f4548d65b03e25cb4))
* **release:** replace the partial destination guard at Gate 2 with the whole question ([5fe0555](https://github.com/nevenincs/cadrumo/commit/5fe05551e90e398d36bc9dec792b98bfdf111005))
* **release:** run the irreversible upload last, after every reversible write ([b75576b](https://github.com/nevenincs/cadrumo/commit/b75576bfd098a3a9943a636144d22930eb8f3ed8))
* **resources:** give the registry a scoped override, the analogue of override_settings ([7ef6c1f](https://github.com/nevenincs/cadrumo/commit/7ef6c1f0f8dbaeb0374ceadcba098443dc6268b1))
* **storage:** enroll the bucket manifest and wrapped DEK in the durability machinery ([4d12fc5](https://github.com/nevenincs/cadrumo/commit/4d12fc530b8774730d24a969e01bf5fa08fa67fa))


### Bug Fixes

* **aggregation:** hold the deductible evidence gate to the standard art. 97 sets ([b1aeff5](https://github.com/nevenincs/cadrumo/commit/b1aeff5f744cc4a0c1e09ba81a97c307f4e49c1c))
* **application:** commit the operator_output package HEAD already imports ([5ea737b](https://github.com/nevenincs/cadrumo/commit/5ea737b647ae04a2832076e51bf70600b8765623))
* **auth:** record only a reusable landing on a salvaged Clave session ([d0e2ca4](https://github.com/nevenincs/cadrumo/commit/d0e2ca4beaecf5dfe9ce02726e6661b8c57e0030))
* **auth:** refuse a live session when an active profile carries no fiscal identity ([db9af03](https://github.com/nevenincs/cadrumo/commit/db9af032608f506cf51c3b02501de7703a269255))
* **auth:** salvage the authenticated session a post-auth failure was discarding ([37e6e93](https://github.com/nevenincs/cadrumo/commit/37e6e931ba29e1a5a621636203b9c42d0e665dbb))
* **boundary:** detect the dev-path form a shipped module would actually use ([a28293c](https://github.com/nevenincs/cadrumo/commit/a28293ce0469878099c09bcc7ce001ab639cc5c7))
* **buckets:** a split into eight children could not record its own event ([beb1666](https://github.com/nevenincs/cadrumo/commit/beb166667b4154b216eb71651040411e733dc811))
* **censo:** a cleared fiscal identity is not a first read ([773ae75](https://github.com/nevenincs/cadrumo/commit/773ae75d5e8b655a93bc89f502ffa6f4c958ac04))
* **censo:** refuse a censal read when the profile records no fiscal identity ([3f7a460](https://github.com/nevenincs/cadrumo/commit/3f7a460971670cd64aa8b910c63ebee4fc6b67ab))
* **cli:** register the wizard profile schemas without eager-loading the wizard ([73f06fa](https://github.com/nevenincs/cadrumo/commit/73f06fa1f27cf727ab49ed9f8e291f000359a681))
* **cli:** stop a kwargs bag suppressing real errors on the wizard leaf registration ([c9568c2](https://github.com/nevenincs/cadrumo/commit/c9568c2e96e85657d957b92edebbfc90b4964c89))
* **cli:** stop the wizard leaf registration violating the help-source gate ([c9f021b](https://github.com/nevenincs/cadrumo/commit/c9f021bd699bb1779501f4d248f2fbd1d07f2e1f))
* **conf:** count the governance work done, not the work outstanding ([d6027f7](https://github.com/nevenincs/cadrumo/commit/d6027f7606d1ef795e29ee3162446e8d2779cfcb))
* **conf:** make a stamp write to the shipped registry impossible by accident ([d0f6a5e](https://github.com/nevenincs/cadrumo/commit/d0f6a5ecc91555f8c490368072806448107ec527))
* **conformance:** enforce the stamp writer's operator-signoff refusal at its boundary ([cdd8808](https://github.com/nevenincs/cadrumo/commit/cdd88080457c073de384e0d9ab1248360c03bbed))
* **conformance:** give the reviewer column one key name and one value ([aedd2e4](https://github.com/nevenincs/cadrumo/commit/aedd2e4a8a55789e6cd76357e5282ae7fe97511b))
* **conformance:** read the review-axis guard's status off the compiled revision ([3e95126](https://github.com/nevenincs/cadrumo/commit/3e95126d99b57ed250b3d06d24cfdc23a8e55564))
* **conformance:** refuse a baseline capture that weakens the ratchet ([85f6dcc](https://github.com/nevenincs/cadrumo/commit/85f6dcc6641dc76ee02e2920ea2ae5ee883967a4))
* **conformance:** refuse a new reviewer that does not restate the date ([bba7d9d](https://github.com/nevenincs/cadrumo/commit/bba7d9d13f13635177760ebeb0f658704d1fd976))
* **conformance:** refuse a provenance claim that names nobody ([be90c8c](https://github.com/nevenincs/cadrumo/commit/be90c8c30f0c815cf5c97632f404cc53a53f6b3a))
* **conformance:** refuse a review-axis write against a declared operator signoff ([0328d3e](https://github.com/nevenincs/cadrumo/commit/0328d3e912e4100b1142d5576a104b6694565b02))
* **conformance:** render a reviewer with the tier that claimed them ([a325b66](https://github.com/nevenincs/cadrumo/commit/a325b66a58a1183b44128f418fc56a5959659eeb))
* **conformance:** write and roll back the manifest through raw bytes ([41ae592](https://github.com/nevenincs/cadrumo/commit/41ae592b94c6827b28416662a0841d618e163de9))
* **conformance:** write the ratchet baseline through raw bytes ([5538b9b](https://github.com/nevenincs/cadrumo/commit/5538b9bcd88199b3324a05364f111f2183567a07))
* **core:** derive the enrollment reference set so the checkpoint deadlock cannot exist ([6853ba3](https://github.com/nevenincs/cadrumo/commit/6853ba36f59ae20688231aaef304fca3d225f58a))
* **declaracion:** anchor numeric_casilla on the printed box number, not record-design metadata ([55134ea](https://github.com/nevenincs/cadrumo/commit/55134eab3595e18f7bbed42bf30f2cc05344328c))
* **declaracion:** read a named_label amount from the line's words, so a box number printed over it stays separate ([28ac563](https://github.com/nevenincs/cadrumo/commit/28ac563e39a18ebf43d7b1d5fc0a0d614b35ba0c))
* **declaracion:** read the printed box number from form_number, not record-design metadata ([3f8a9ba](https://github.com/nevenincs/cadrumo/commit/3f8a9ba995ae7c6f7a4bc2fe7f92f996e1d7d711))
* **dev:** replace the operator real name with a fictional stand-in in the conformance CLI tests ([0624dc4](https://github.com/nevenincs/cadrumo/commit/0624dc421b2b791fa7f588466d7df899f3e0e56e))
* **docs-gate:** skip prose directives by rule, not by vocabulary coincidence ([32f5dc9](https://github.com/nevenincs/cadrumo/commit/32f5dc9dcd7d4440db872a266758f5ba26f19bee))
* **docs-preprocess:** stop the _data coverage gate demanding an index entry for empty files ([cc2f1f3](https://github.com/nevenincs/cadrumo/commit/cc2f1f302eb5923275ab985467e46f9d7278cac6))
* **docs-sequences:** evict logging handlers left bound to a dead capture buffer ([4a4a05b](https://github.com/nevenincs/cadrumo/commit/4a4a05b557823b3ed6799a2d940b99a19a918d9f))
* **docs:** derive the displayed version instead of freezing it into a golden ([749a44c](https://github.com/nevenincs/cadrumo/commit/749a44c20e24cb9ec81d7a0e47ffeab970b41d25))
* **errors:** give the reset lifecycle errors a registered next action ([49568d2](https://github.com/nevenincs/cadrumo/commit/49568d2b70c48ed59c94c79f932533ebf0da8a11))
* **fixtures:** declare both amount forms the Modelo 100 sanitiser actually rendered ([e59fa97](https://github.com/nevenincs/cadrumo/commit/e59fa978d319acfa6cd80650e961ea50b9bd3ff7))
* **fixtures:** drop the reversible PII hashes recorded beside the sanitised justificantes ([91ea74d](https://github.com/nevenincs/cadrumo/commit/91ea74d31d7b900fdb8cca800860d0f65c35fd85))
* **fixtures:** land the two generators the previous commit already imports ([5c9c22d](https://github.com/nevenincs/cadrumo/commit/5c9c22dbe6ad05ac4df72fb5c970fd02f2b1925a))
* **fixtures:** replace the two justificantes that still carried real identities ([cb551ae](https://github.com/nevenincs/cadrumo/commit/cb551ae6bb6aea61565b1a1c0d87684e1508b9eb))
* **gates:** make the stub drift check see the terminators its own writer translated ([9f59f32](https://github.com/nevenincs/cadrumo/commit/9f59f3259587d8fac042ac7cd1579f2d1676ea31))
* **iva:** resolve the mandatory-especial margin per filing year ([a4a5197](https://github.com/nevenincs/cadrumo/commit/a4a519745914f65dba3bef7388429fb995e4b8fd))
* **iva:** stop the 2009 M303 revision zeroing a blank prorrata declaration ([397541a](https://github.com/nevenincs/cadrumo/commit/397541a1b42efdecb22cd8e09a5721bf835ba816))
* **legal:** ground modelo 187 in the orden that actually approves it ([be41f12](https://github.com/nevenincs/cadrumo/commit/be41f12beb983a0cae0b10b9c0f3bab4bbadf81d))
* **legal:** ground modelo 296 in the article of its own bundled orden ([df2ca15](https://github.com/nevenincs/cadrumo/commit/df2ca15f1b4e649f45d3049ce8040156aff8790e))
* **legal:** ground modelos 188, 194 and 128 in the ordenes that approve them ([859cbec](https://github.com/nevenincs/cadrumo/commit/859cbec041a60aec050643ce7cb655a908a568e8))
* **legal:** pin modelo 345's approval to the form number its corpus states ([df26a6e](https://github.com/nevenincs/cadrumo/commit/df26a6e5927e28f72f1c272ffed341dd0f3d4715))
* **modelo:** block a deductible-IVA evidence gap at verify instead of at export ([d06f4e4](https://github.com/nevenincs/cadrumo/commit/d06f4e4402f1985d77296c0e85c6a8d94a5dc58d))
* **modelo:** land the half of the reconciliation-records split that HEAD was missing ([1d25593](https://github.com/nevenincs/cadrumo/commit/1d25593f48d87b3749dbb23a2ed2e16c04cde8aa))
* **modelo:** refuse to promote a ledger-derived revision without verifying it ([5d9fed5](https://github.com/nevenincs/cadrumo/commit/5d9fed5ec148b411630d00773b1b5aad5c0f78ca))
* **modelo:** repoint the reconcile tests at the split's new module ([b98bf1e](https://github.com/nevenincs/cadrumo/commit/b98bf1ed3eded5c9823a422f3ab4793728fb4f52))
* **modelo:** stop the enrolled-set docstring restating why each modelo is out ([fd0b5ef](https://github.com/nevenincs/cadrumo/commit/fd0b5efc7733316ff92893146d3b6f17a5ff4e5e))
* **modelo:** verify granted over a draft the ledger had moved under ([b68c274](https://github.com/nevenincs/cadrumo/commit/b68c274a24615f45ebdc8c413d16a53ed7bf42d3))
* **packaging:** re-pin the description digest after the surface moved again ([0dde3b1](https://github.com/nevenincs/cadrumo/commit/0dde3b135ef4d4cf450aaca1000d09133c2b172f))
* **packaging:** re-pin the model-facing description digest to committed state ([0fc412b](https://github.com/nevenincs/cadrumo/commit/0fc412bf41709a10b9b8e242602f92a7d8e13144))
* **packaging:** seal at seal scope, which unbreaks every build between releases ([82d132d](https://github.com/nevenincs/cadrumo/commit/82d132d5e9c4a38bcc5cc7ec0310a14c618403c7))
* **packaging:** sweep the generator tests onto the commit-defined build root ([9c3acdf](https://github.com/nevenincs/cadrumo/commit/9c3acdfd8ada6f7cc6099dae457f7d819ac6fce2))
* **profile:** a required field must carry a value, not merely carry a fact ([f07e0cc](https://github.com/nevenincs/cadrumo/commit/f07e0cc40bed79337994b533a133ac5fb190a8c0))
* **profile:** declare the lazy facade's exports so static analysis can see them ([c7101b0](https://github.com/nevenincs/cadrumo/commit/c7101b09789b02257d5966f279a30b900d692f57))
* **profile:** make required bind per row, so a valid profile stops reading as incomplete ([71c5a7b](https://github.com/nevenincs/cadrumo/commit/71c5a7bb997513ddbbca851246b8b54e46c1a443))
* **profile:** make the schema's declared enum sets actually bind ([dd4c5f9](https://github.com/nevenincs/cadrumo/commit/dd4c5f97a793ef8efd2e5050211d7bdd1ce9786d))
* **profile:** register the profile keys at the read, not by luck of import order ([6b2edc7](https://github.com/nevenincs/cadrumo/commit/6b2edc73018de41ae6bd6b2211f03502acc357bf))
* **profile:** render a failed login refusal in the target profile's language ([9448bd6](https://github.com/nevenincs/cadrumo/commit/9448bd61c97254356112b7b6979f551801e0be76))
* **profile:** stop every profile save resetting the absolute session expiry ([514ec04](https://github.com/nevenincs/cadrumo/commit/514ec04ca82c14a7502d7a0d0554c6ef69f3a6d3))
* **profile:** stop requiring a member role no form asks for, and correct the rule that would have kept it ([71daf23](https://github.com/nevenincs/cadrumo/commit/71daf23dceb92b2e65cad00687a20e89cc9761cb))
* **registry:** arm seven blank-box guards from AEAT's own published box numbers ([a2b0ae0](https://github.com/nevenincs/cadrumo/commit/a2b0ae06917c15aa733d7a0e22ad81b527f18fb2))
* **registry:** declare art. 94 on the M303 prorrata formula in both revisions ([215749f](https://github.com/nevenincs/cadrumo/commit/215749f8af5c7893ad4bddb5a7215f33e81ed1a7))
* **registry:** declare the ejercicio targets as text, since a tax year is not an amount ([713b895](https://github.com/nevenincs/cadrumo/commit/713b895b149449a3780f047ed6c2b512ed763872))
* **registry:** fold the review-status enum into the compiled cache key ([ee6c524](https://github.com/nevenincs/cadrumo/commit/ee6c524baf4d4bd22ab31f95866efdbca4ff8b9c))
* **registry:** keep the governance stamp readable in one place ([f1a1bac](https://github.com/nevenincs/cadrumo/commit/f1a1bacaedb9aab3a1aa7293978c877b2e74dd65))
* **registry:** read the classification detail bound from the field it must satisfy ([431e67d](https://github.com/nevenincs/cadrumo/commit/431e67d8010c5e6ab915a9b5e0758e8d8cf034bd))
* **registry:** restore the legal grounding the M100 2024 and 2025 profiles dropped ([8e7bac4](https://github.com/nevenincs/cadrumo/commit/8e7bac4e97d0361c865d9aee7dc157c617651091))
* **registry:** retract four real-corpus verification claims the fixtures cannot support ([4e8c4cd](https://github.com/nevenincs/cadrumo/commit/4e8c4cd0a1cec5a024fec75ceaf5bddcdea055ad))
* **registry:** round the M303 prorrata percentage to the unidad superior ([eaaeced](https://github.com/nevenincs/cadrumo/commit/eaaeced21d8d8957a7245100c581c27124fd39f1))
* **registry:** stop an unmeasured conformance axis reading as a clean one ([486c4c2](https://github.com/nevenincs/cadrumo/commit/486c4c2125bdabb8a0d5a88494e2129fba7e6fed))
* **registry:** stop the classification fold raising on the disagreement it must report ([70e1363](https://github.com/nevenincs/cadrumo/commit/70e13633b34f832c43b61a2ebc0b8a7b3e400384))
* **release:** derive the acquisition-evidence demand, and enforce the approval gate ([892655e](https://github.com/nevenincs/cadrumo/commit/892655e63f7baa2aba3de58bc4b41125355e5fbe))
* **release:** re-lock after the version reset, which left the lockfile at the old number ([01b2503](https://github.com/nevenincs/cadrumo/commit/01b250370c38898d1897427985546c08ef537b94))
* **release:** stop the operator instructions teaching the deadlock the gate retired ([89ec273](https://github.com/nevenincs/cadrumo/commit/89ec27374dd48aeb18ef13edf07f74d6006cbe5c))
* **sanitizer:** make the known-sanitised catalogue match the tree, and pin it ([f8a6eb8](https://github.com/nevenincs/cadrumo/commit/f8a6eb8d9c006541d07f26389e6d876b9848dbf0))
* **sede:** refuse a censal read the selector could not dispatch ([fff4a71](https://github.com/nevenincs/cadrumo/commit/fff4a715d1c71f3869e0b29401f364c2bf135536))
* **sede:** stop the dispatch wait reporting a false negative as fallback ([2646a87](https://github.com/nevenincs/cadrumo/commit/2646a87448b5bf594a8b6fc43abab7283f14f2b4))
* **storage:** validate the manifest at its write ingress, and restore the validated save ([9b0a504](https://github.com/nevenincs/cadrumo/commit/9b0a5040ca4d082e864e11d9bf10284c1033aaad))
* **terminology:** restore the Hungarian diacritics on the shipped prorrata-especial query ([c38daff](https://github.com/nevenincs/cadrumo/commit/c38daff6fea58c1125ecb0bb00ce6c54786e1d98))
* **terminology:** stop offering non-registry modelos as glossary concepts ([3d91f54](https://github.com/nevenincs/cadrumo/commit/3d91f54f28c445994a5194e01ece9f9d4bea3e2b))
* **terminology:** tighten the curation-backlog ratchet to the real 57-draft floor ([10ea5ce](https://github.com/nevenincs/cadrumo/commit/10ea5ce0ef34ec62e0fbbc3ee887e727db613161))
* **tests:** model the version-stance key my own config change broke ([2006d7d](https://github.com/nevenincs/cadrumo/commit/2006d7d64ec1ab6565ab2022b56cf49bc324be42))
* **tests:** stop a throwaway test schema poisoning the global registry ([91b6968](https://github.com/nevenincs/cadrumo/commit/91b6968682fcad9425f3ff9767a47cfe2f7dda41))
* **types:** clear all 18 ty and pyright diagnostics ([81f46eb](https://github.com/nevenincs/cadrumo/commit/81f46eba2ea81d453680b418ed6d1506d2c13633))
* **user-profile:** exporting a profile that had reconciled raised ([1584716](https://github.com/nevenincs/cadrumo/commit/158471685bfd27be923abefd8467653c3faa9a86))


### Performance Improvements

* **docs:** shard the cli-sequence checks across bounded child interpreters ([fdfa872](https://github.com/nevenincs/cadrumo/commit/fdfa872f081b101e136c5628e5bed9e1384f2fa9))
* **docs:** split the build gate per heavy build, authored by docs-build-speed ([820d819](https://github.com/nevenincs/cadrumo/commit/820d8192a053e45c2588d8b33636ee5210c0757e))


### Documentation

* **adr:** rule the three questions the reviews escalated ([c956f1e](https://github.com/nevenincs/cadrumo/commit/c956f1e2d77aa200539252bbbeb00edfa3cae7b4))
* **application:** cross-link the core structs eight modules had started using ([bcbb34d](https://github.com/nevenincs/cadrumo/commit/bcbb34d6cbd661940cfe8623be04d01fab07abe6))
* **censo:** say that the pull's safety property is the pair, not either test ([9eb0740](https://github.com/nevenincs/cadrumo/commit/9eb07400aca8958acd29b61db2fa1249650193fb))
* **censo:** stop promising the pull fills the fiscal ID, and bind the claim to the tuple ([1bf7884](https://github.com/nevenincs/cadrumo/commit/1bf78846a7a04a7cbda9c34f0bb322b19f7d9e58))
* clear the last cross-references, and the nitpicky gate goes green ([c36080e](https://github.com/nevenincs/cadrumo/commit/c36080e94fb3a8364d2e14db6e6b3e84e56c0941))
* clear the two red prose gates, one by fixing the prose and one by fixing the gate ([a9871b0](https://github.com/nevenincs/cadrumo/commit/a9871b039d3c9fdbebe7a81455206f64f1edb584))
* **conf:** give the registry conformance tool a written procedure ([cfc04a1](https://github.com/nevenincs/cadrumo/commit/cfc04a17c130bedea251751e888ee5210ef5c02d))
* **conf:** render Textual's Markdown code fences instead of erroring on them ([c55db15](https://github.com/nevenincs/cadrumo/commit/c55db15aa4579ce67fe7e925bc3a6ea9da9feb62))
* **conf:** resolve the first cross-reference the nitpicky build has ever reached ([a7ced9e](https://github.com/nevenincs/cadrumo/commit/a7ced9eb2ce3cad36f265f30e03bc2c4d1d987cc))
* **dev:** restate the conformance test docstrings as self-contained reasoning ([90234b3](https://github.com/nevenincs/cadrumo/commit/90234b3a6b71add12ccc615cffd49a59e1ceedea))
* **exec:** correct two step records that misstated their own state ([1b9d4ef](https://github.com/nevenincs/cadrumo/commit/1b9d4ef63478c03394945ff2d31bcb12c50dbf33))
* **exec:** record P04.S27 dev-path detector widening ([5aa9fba](https://github.com/nevenincs/cadrumo/commit/5aa9fba319024995308dc7307e6f5707afd79fcd))
* **exec:** record S50, the monkeypatch retirement and its defect-reintroduction proof ([36f636c](https://github.com/nevenincs/cadrumo/commit/36f636c16048d47895d584b8906f23f7613e6f34))
* **exec:** record S51, the sanitiser control rename and the facade reroute ([da97a61](https://github.com/nevenincs/cadrumo/commit/da97a61361187d374acd1ff609a5ae094016e440))
* **exec:** record S70, the operator-name privacy scrub in the conformance CLI tests ([f45213c](https://github.com/nevenincs/cadrumo/commit/f45213c8f53a40fe5d70a77fc14013fb16b773bd))
* **exec:** record S71, the development-record citations removed from source ([609587d](https://github.com/nevenincs/cadrumo/commit/609587d6dfdb057e2cf3ebd238299f5742ef4d9b))
* **exec:** record S75, the two step-record corrections ([34f52ed](https://github.com/nevenincs/cadrumo/commit/34f52ed343491bd325b15fd8c1711927c11713e9))
* **exec:** record the ADR ruling on boundary ownership, labelling and resolver exposure ([b8a419b](https://github.com/nevenincs/cadrumo/commit/b8a419bef71d924815a780f65858bad0fd4d2d05))
* **exec:** record the conformance CLI verbs and the operator-signoff ruling ([58b2ffd](https://github.com/nevenincs/cadrumo/commit/58b2ffdb55a28223adfd53fd84fe97009525c5ce))
* **exec:** record the conformance manager and the peer WIP moving its numbers ([230baea](https://github.com/nevenincs/cadrumo/commit/230baea8f9c45a8dffe2a577face859c0c1e2f9c))
* **exec:** record the conformance profile composer and its mutation-proved gate ([0b3d198](https://github.com/nevenincs/cadrumo/commit/0b3d19802281fb86bdbf054afc11e9d045227151))
* **exec:** record the derived compiled-cache key that stops trusting an author's memory ([e2f1388](https://github.com/nevenincs/cadrumo/commit/e2f13882f3a92b5c0e250a21370362275b9d0454))
* **exec:** record the derived detail bound and the 17-character margin behind it ([ec789b9](https://github.com/nevenincs/cadrumo/commit/ec789b92434a770fb3afde78b60a7b46beaacc5d))
* **exec:** record the M303 prorrata oracle repair and the casilla-44 deferral ([59aa706](https://github.com/nevenincs/cadrumo/commit/59aa706cd80fedc7e96a9cbb3389298640d0b33a))
* **exec:** record the operator-backlog ceiling and close Step S42 ([3eb92ed](https://github.com/nevenincs/cadrumo/commit/3eb92ed059f3439a7355e5f0ff26d1f83693dda7))
* **exec:** record the P01 declared-provenance schema execution ([01c4569](https://github.com/nevenincs/cadrumo/commit/01c4569996f6ebcf25931c7a7c95df3e56b605f3))
* **exec:** record the required-set oracle-collapse remediation ([28c7402](https://github.com/nevenincs/cadrumo/commit/28c740246545466f14b37cae6a22ce080688b062))
* **exec:** record the signoff horizon floor and the row-level degraded label ([b52d7de](https://github.com/nevenincs/cadrumo/commit/b52d7de9aa4889b00c9ba81902a519f7a0fd677f))
* **exec:** record the stamp writer boundary coercion and close Step S39 ([14568df](https://github.com/nevenincs/cadrumo/commit/14568df776e582ea68ab6876d08c2f12cd5867c2))
* **exec:** record the terminator-drift and conformance-runbook steps ([1598ad0](https://github.com/nevenincs/cadrumo/commit/1598ad07a5f05e8889161a671619447467daf028))
* **exec:** record the tier-qualified reviewer rendering and close Step S46 ([af8dfef](https://github.com/nevenincs/cadrumo/commit/af8dfef2cd937fe02386f9477c365a1b56de5575))
* **exec:** record the two governance stamp integrity gaps and close their rows ([9298c1c](https://github.com/nevenincs/cadrumo/commit/9298c1c07d2a786d5450e5e407084e90badcf948))
* **exec:** record the typed oracle payload boundary and its refusal proof ([940c54e](https://github.com/nevenincs/cadrumo/commit/940c54e85ebd62eb1dfcc1aa026fa5d9867df4b1))
* **filing:** record why the snapshot-freshness monkeypatch stays, and the trap in removing it ([d08b4ff](https://github.com/nevenincs/cadrumo/commit/d08b4ffe315f298b14cde83aa5212107d803e679))
* **iva:** cite the articles that actually carry the prorrata rules ([6c60d4d](https://github.com/nevenincs/cadrumo/commit/6c60d4d676855952bd5bb1daf4ae5f38875b6245))
* **modelo:** stop telling readers Modelo 202 has no extraction profile ([ff2475b](https://github.com/nevenincs/cadrumo/commit/ff2475b863883d0553fcab90e717332e8a81752b))
* **plan:** close the casilla-44 ruling and the predicate relocation ([8ee255d](https://github.com/nevenincs/cadrumo/commit/8ee255df685158d63af77dcc89bf7ce99e705bd6))
* **plan:** close the conformance CLI phase P03 rows ([2978b7c](https://github.com/nevenincs/cadrumo/commit/2978b7c7d048c49786cd0ff9c4a7468af9af647d))
* **plan:** close the conformance surface hardening rows ([e7d88f6](https://github.com/nevenincs/cadrumo/commit/e7d88f645f2f99bce77d95a180b81559be35fb28))
* **plan:** close the publication decision, made and executed by the operator ([c106173](https://github.com/nevenincs/cadrumo/commit/c10617386f920aaff538dae0b6461ca3971db079))
* **plan:** land the campaign's step closures and new rows ([1b8ae5e](https://github.com/nevenincs/cadrumo/commit/1b8ae5e646abd71a6aeeb21988ea8bcfd81b83b9))
* **plan:** land the campaign's step closures and the rows the reviews opened ([35ba920](https://github.com/nevenincs/cadrumo/commit/35ba920d44d42b1a73189c6d1cd9a1e32406a867))
* **registry:** correct the stale casilla-44 prorrata premise at its change site ([f13aff1](https://github.com/nevenincs/cadrumo/commit/f13aff17d36a3a00a936ca9dde8c361fec17bd3b))
* **registry:** record that the absent host-suffix widening is a decision ([f4ba0cf](https://github.com/nevenincs/cadrumo/commit/f4ba0cfa8377ffed9797036f36bb4be6ccc2f41c))
* **registry:** record the per-activity módulos precondition where the engine would be promoted ([ac82ea4](https://github.com/nevenincs/cadrumo/commit/ac82ea4830e81d4fe679481f3dd0771d09072411))
* **registry:** rule that value_kind is a parse directive and enum is a hint ([41db954](https://github.com/nevenincs/cadrumo/commit/41db95471669f1afc34c028a033b184efb5fb408))
* **registry:** state how the no-consumer claim was established, not just its conclusion ([9c9b938](https://github.com/nevenincs/cadrumo/commit/9c9b93840e5d4d4d343ad83a4d6f9b05052ac7cd))
* **release:** make the bump the first act and the docs publish a named tripwire ([0ca0727](https://github.com/nevenincs/cadrumo/commit/0ca07279d6fc86b8875756bc9771dc2cad1f814c))
* **release:** split the PyPI trusted-publisher path by whether the project exists ([2636b77](https://github.com/nevenincs/cadrumo/commit/2636b77b8ebaccc828cc41b37237f172cc3966fd))
* **sede:** name the censal host widening as a divergence, with its probe ([3c8126c](https://github.com/nevenincs/cadrumo/commit/3c8126c2685b416f5bca235313e6d2a22a719097))
* **sede:** name the declarations host constant as the policy lookup key ([01c7476](https://github.com/nevenincs/cadrumo/commit/01c74765127e6f291ce0895197af99b561c73b36))
* **sede:** record that the declarations host is also a registry lookup key ([cc0fafc](https://github.com/nevenincs/cadrumo/commit/cc0fafc0b6c39222a9e2463edf89a4eb1269ec9d))
* **sede:** record why the declarations reader still names a host ([e0292d0](https://github.com/nevenincs/cadrumo/commit/e0292d08115224aadc9d95aa2c58ccf6882f7875))
* **sede:** the selector's failure path now refuses rather than degrading ([e28b1eb](https://github.com/nevenincs/cadrumo/commit/e28b1eb28fbd88102ca7a4537d548ef163105d86))
* **sequences:** record the split and merge payloads my own fix changed ([7e54c78](https://github.com/nevenincs/cadrumo/commit/7e54c78bf429afc0582b35d51e2de288f2d3f3a0))
* **sequences:** teach the last four M130 walkthroughs to attach evidence ([2dbb956](https://github.com/nevenincs/cadrumo/commit/2dbb956088057f45a6bf39fdfcf3753da4f643be))
* **sequences:** teach the M303 walkthrough to attach evidence before verifying ([1805a56](https://github.com/nevenincs/cadrumo/commit/1805a56d731ed63dc71b727f29b1b59807f69aaf))
* **sequences:** teach the saved-review walkthrough to attach evidence too ([99a9eff](https://github.com/nevenincs/cadrumo/commit/99a9eff1804bdf0a01228bced4e86689ba0972bd))
* **terminology:** restructure four term-adjacent parentheticals the redeclaration gate reads as glosses ([695d466](https://github.com/nevenincs/cadrumo/commit/695d4669a2e0968a6d1aaffa10d383cbf1680f11))
* **vault:** add P02-S05 and P02-S06 exec records, close both steps ([5c2c7d3](https://github.com/nevenincs/cadrumo/commit/5c2c7d30643bb90f0bbf59427a2acb7e2b1d1783))
* **vault:** add P02-S07 and P02-S08 exec records, close both steps ([652c5cc](https://github.com/nevenincs/cadrumo/commit/652c5cc1bdb345d8ffd188d37f7aa86d59c51c0b))
* **vault:** assess the five pinned readers and confirm the regime deferral ([72f49c3](https://github.com/nevenincs/cadrumo/commit/72f49c3bc34bc3be0841d1490578131cb7f1b912))
* **vault:** close the prorrata parity step against the fix that already carried it ([f48b9f0](https://github.com/nevenincs/cadrumo/commit/f48b9f066142ad1c7b23d360d7e80d8c3602ed8b))
* **vault:** close the stub-scaffolding step on the drift check rather than a tree-wide run ([fc8c838](https://github.com/nevenincs/cadrumo/commit/fc8c838640fa4fe8312ef0c5fa1e9d95fea279d2))
* **vault:** correct the discovery-service diagnosis to peer contention ([a3836ef](https://github.com/nevenincs/cadrumo/commit/a3836ef0cea3a15d239f3de368be631a40f5979d))
* **vault:** correct three P16 records that described protections not present ([ca3591a](https://github.com/nevenincs/cadrumo/commit/ca3591a22a5a75f2d2c2215590375924bdc8cb86))
* **vault:** defer convergence with its named mechanism unmeasured ([95a096a](https://github.com/nevenincs/cadrumo/commit/95a096ae3f8801abca510762c26df6ac6e5bd3ee))
* **vault:** defer the degraded-state signal, re-measured on the local store ([060dfcb](https://github.com/nevenincs/cadrumo/commit/060dfcb2c1730fcb305b61dde4da619623c25e24))
* **vault:** exec record and step closure for conformance-cli P04.S18 ([563b8da](https://github.com/nevenincs/cadrumo/commit/563b8da214a7a22164fd5688ef3244c9acd92133))
* **vault:** exec records and step closures for P04.S19 and P04.S21 ([0b9ab3e](https://github.com/nevenincs/cadrumo/commit/0b9ab3e6dd669e17a4064042115bb94e17c26e93))
* **vault:** give the measured backlog an owner instead of a paragraph ([7cde038](https://github.com/nevenincs/cadrumo/commit/7cde038dc1e9a2161fde5d1a2a8ea9a968d64529))
* **vault:** govern the modelo schema conformance surface ([2607e2c](https://github.com/nevenincs/cadrumo/commit/2607e2c3fb355e89fae9ec46f68bdb9083523bce))
* **vault:** reconcile the retired PyPI lane rows against the tree ([76ca17b](https://github.com/nevenincs/cadrumo/commit/76ca17b14fc590e7208cd6af525af3dc6f358d86))
* **vault:** record and close the verified W05.P15 contract rows ([7b705fc](https://github.com/nevenincs/cadrumo/commit/7b705fc363fc4036e14d9e55a90eb7293c80a265))
* **vault:** record canonical-release-pipeline S14 and close the step ([8b8122a](https://github.com/nevenincs/cadrumo/commit/8b8122afa0a73f891536c9caff280b47e315c4b6))
* **vault:** record cli-authority-verb-conformance W05.P15.S137 and close the step ([2e764fd](https://github.com/nevenincs/cadrumo/commit/2e764fd6f6a0a63c8f5f554f999e802a6b4a2ccb))
* **vault:** record conformance-cli P02 classification-coherence steps S09 and S11 ([c996b4e](https://github.com/nevenincs/cadrumo/commit/c996b4e309762b43ec5fd17600ac6e108d8e9826))
* **vault:** record conformance-cli S53 to S57 and correct two overclaims ([27712aa](https://github.com/nevenincs/cadrumo/commit/27712aa1487b810231a5d688029bb2b83349a45e))
* **vault:** record conformance-cli S58 and close the step ([045655c](https://github.com/nevenincs/cadrumo/commit/045655c068b86905c61b62b53f15bf2d2f013c43))
* **vault:** record conformance-cli S59 and close the step ([7f37471](https://github.com/nevenincs/cadrumo/commit/7f37471e8c1d38fe738c90f46cd3e715d327f90a))
* **vault:** record conformance-cli S60 and close the step ([5f8cabe](https://github.com/nevenincs/cadrumo/commit/5f8cabe61ba3ad791c6d18284234121401cf242e))
* **vault:** record declaracion-real-render-verification P04 S15 S21 S25 S28 S30 ([fd2f2d4](https://github.com/nevenincs/cadrumo/commit/fd2f2d4fb2c77b4ccdd669b20ed83ace880d643d))
* **vault:** record the attribution widening and the manifest-only extension ([d2c1268](https://github.com/nevenincs/cadrumo/commit/d2c12683cac2b65447565d08fee4a0b154f3f685))
* **vault:** record the boundary-detector consolidation and close Step S41 ([100cd00](https://github.com/nevenincs/cadrumo/commit/100cd0030ebe5fee4936c968c6c54f9547c4ce72))
* **vault:** record the branch-coverage self-review in the Step S41 record ([f476676](https://github.com/nevenincs/cadrumo/commit/f476676ee4eb8bbefcca397c7116c8be89f723db))
* **vault:** record the campaign-close honesty review and the decisions it forced ([fccacb9](https://github.com/nevenincs/cadrumo/commit/fccacb9f3ed1de690cf7c1ee9656cb9538446c99))
* **vault:** record the casilla-44 ruling and the predicate-concern relocation ([dce8d71](https://github.com/nevenincs/cadrumo/commit/dce8d7150137d8608fcae63a2b3313b5ccb9ceb5))
* **vault:** record the classification-fold overflow fix in the S09 and S11 records ([2fc5ceb](https://github.com/nevenincs/cadrumo/commit/2fc5ceb0d22af6086ad4eae92b3bae83df294f09))
* **vault:** record the conformance-cli review and the Steps it opened ([936deb6](https://github.com/nevenincs/cadrumo/commit/936deb693cec43cd3b8329a02903e24069077f17))
* **vault:** record the conformance-surface steps S67, S77, S79 and S80 ([7397394](https://github.com/nevenincs/cadrumo/commit/73973942111a7860639f06abd53fe120e0d84bdd))
* **vault:** record the fifth-hole remediation and the drift class it exposed ([3fc2925](https://github.com/nevenincs/cadrumo/commit/3fc292590257e896f81471d44e32e70a6bbcfee1))
* **vault:** record the first conformance measurement and the gate triage ([807e0f1](https://github.com/nevenincs/cadrumo/commit/807e0f11ef8e741595069299a9471fdb97901943))
* **vault:** record the governance stamp review and its residual gaps ([6205e90](https://github.com/nevenincs/cadrumo/commit/6205e90505898cf3e7108ea3c33dbb11e473dc42))
* **vault:** record the grounding-resolver placement ruling and close Step S40 ([50fa8d6](https://github.com/nevenincs/cadrumo/commit/50fa8d6b1a3e5c92c2f1e41118b5b004a3e73490))
* **vault:** record the M303 prorrata grounding declaration and close Step S38 ([905484a](https://github.com/nevenincs/cadrumo/commit/905484a83647874039318337dc15e5ff9261823d))
* **vault:** record the M303 prorrata rounding correction and close Step S31 ([cf34a4d](https://github.com/nevenincs/cadrumo/commit/cf34a4d2eb0db8497c331c91802ab19a93bd4082))
* **vault:** record the prorrata zero-volume and citation Steps and close them ([0cb4200](https://github.com/nevenincs/cadrumo/commit/0cb4200df38168b665dc039b11ac8273284afb01))
* **vault:** record the registry schema verification extraction and close S61 ([6817442](https://github.com/nevenincs/cadrumo/commit/6817442218b3861f9859465fe846c6374dd4e96c))
* **vault:** record the S49 gate-regression absorption ([81c1738](https://github.com/nevenincs/cadrumo/commit/81c1738c9cdbfdb4d2a9ea565229f69fa2c39a4b))
* **vault:** record the S52 diff re-anchoring and the unwitnessed rounding dimension ([2b4f5c0](https://github.com/nevenincs/cadrumo/commit/2b4f5c01f9380274d2067f242b251ba4461cbb7e))
* **vault:** record the S56 detector-branch pinning and redundancy rulings ([f612114](https://github.com/nevenincs/cadrumo/commit/f612114ac927e87c349ba4c9cfec5500fcd1309f))
* **vault:** record why the discovery service refuses to start under fleet load ([6956651](https://github.com/nevenincs/cadrumo/commit/695665136735f968a78e134baa56b8033e928a7e))
* **verification:** declare verify_declaracion's reference-implementation role ([994faca](https://github.com/nevenincs/cadrumo/commit/994faca38628b4cee8b4ff6c32b3c9314dafc2ca))


### Code Refactoring

* **boundary:** put both dev-boundary detectors under one authority ([6ed41c7](https://github.com/nevenincs/cadrumo/commit/6ed41c74b712423ef8a0b7243a92e7733ed0a2ed))
* **bundle:** separate reading the stamped version from judging it ([98fd6b5](https://github.com/nevenincs/cadrumo/commit/98fd6b5598c89909fef6ea04d0666f32664b19a8))
* **bundle:** split the export command, and re-green the export-format types ([3ddd20f](https://github.com/nevenincs/cadrumo/commit/3ddd20f0438977790329903b6e2c99c88ec73ee8))
* **censo:** split the pull verb and its notice builder ([0d5f228](https://github.com/nevenincs/cadrumo/commit/0d5f228d454fdce557b937eaa575a86cb50a6f04))
* **cli:** extract the wizard manager dispatch out of the config facade ([a722ecc](https://github.com/nevenincs/cadrumo/commit/a722ecc2cc99eb353231a4d1273e9dc67ab6204f))
* **cli:** make the parse-failure recognisers four named functions ([a6d65e9](https://github.com/nevenincs/cadrumo/commit/a6d65e9a1473f210accbeaf4ac49964b8dc753ff))
* **cli:** split the three config-command complexity hotspots ([6e34f45](https://github.com/nevenincs/cadrumo/commit/6e34f4504dc654a8414392064083b6c84c659462))
* **conformance:** read the governance field set from the shipped authority ([b76af2d](https://github.com/nevenincs/cadrumo/commit/b76af2d1113cec25687dd37118cd8cfc5ab9028b))
* **conf:** retire the forked dev registry capability matrix ([e8a95ae](https://github.com/nevenincs/cadrumo/commit/e8a95ae23a3e5817f7cfc4162a4423fb4343da50))
* **core:** relocation:ExportLayoutFormat lift the export-format closed set into core ([914c59a](https://github.com/nevenincs/cadrumo/commit/914c59ad07772368c857dc80e2d2e99083645855))
* **core:** relocation:NIST_PASSPHRASE_MIN_LENGTH, and restore green import contracts ([494ff45](https://github.com/nevenincs/cadrumo/commit/494ff453c59df426e9be15d6f4a7b3160a56f801))
* **declaracion:** split the parser's three complexity hotspots ([c1460d7](https://github.com/nevenincs/cadrumo/commit/c1460d7a15f74075159c12775eb881118d677abe))
* **diagnostics:** split the not-ready profile row out of _profile_check ([7853e57](https://github.com/nevenincs/cadrumo/commit/7853e57e39cb9a3cfac6951276cf7100d047c1ba))
* **filing:** extract required-applicable casilla derivation into shared public function ([9c64ec0](https://github.com/nevenincs/cadrumo/commit/9c64ec0d99420f46f674ad40e0cd78b572502315))
* **filing:** relocation:assert_export_mirrors_manifest into a parity sibling ([de1f9ec](https://github.com/nevenincs/cadrumo/commit/de1f9ec600fe6e48ecaef80444356fd688059d44))
* **flows:** split the engine, resume, and scripted-driver hotspots ([bc52432](https://github.com/nevenincs/cadrumo/commit/bc52432a7d59fc187c9270b5068b47a8263c9183))
* **flows:** split the line frontend's three complexity hotspots ([8edc9a0](https://github.com/nevenincs/cadrumo/commit/8edc9a0cb4ca9b95de71e6773b49e28c9c239fe7))
* **imports:** promote three deferrals to module scope, enrol the one real cycle ([bee3d16](https://github.com/nevenincs/cadrumo/commit/bee3d16928dca11484012ca8d8db1ab8a3963b3e))
* **imports:** route three cross-package reaches onto the owning facade ([7193519](https://github.com/nevenincs/cadrumo/commit/7193519ec74c17d4789ebf8414efb2e57b67f78e))
* **ledger:** lift the evidence-bytes resolution out of _resolve_evidence ([af1e803](https://github.com/nevenincs/cadrumo/commit/af1e8030c42290e64b243b7877445141c7e1a3b5))
* **locales:** split the five locale-surface complexity hotspots ([a8dbc4f](https://github.com/nevenincs/cadrumo/commit/a8dbc4f91ac3ae359415e6cc717f3be76f55e28e))
* **modelo:** give the ledger-drift gate its own module ([b70fa09](https://github.com/nevenincs/cadrumo/commit/b70fa094a497e9cb6e95e48afeb52a94e7884ab9))
* **overview:** split the multi-profile calendar scan ([4123b84](https://github.com/nevenincs/cadrumo/commit/4123b84eff0da2b647c252bf0c2dd2b1b6be2f90))
* **parsers:** table the PDF header spellings, split the numeric fast path ([d96d130](https://github.com/nevenincs/cadrumo/commit/d96d130ff59bc77204de578afcc4d9037074bf1f))
* **profile:** make the manifest projection a copy-and-update, not a rebuild ([69c03b8](https://github.com/nevenincs/cadrumo/commit/69c03b837243e4281d16317536fb8840b1aca082))
* **profile:** split the completeness and wizard-emit hotspots ([4cdcb90](https://github.com/nevenincs/cadrumo/commit/4cdcb9046ca9bd481e5151c0a9898c0432742817))
* **registry:** give the impatriado ledger family its own module ([c6899e6](https://github.com/nevenincs/cadrumo/commit/c6899e6ad95a5db67b76a84c2aa24d3b626ebfba))
* **registry:** read bundled oracle payloads through the shared UTF-8 constant ([23a09e8](https://github.com/nevenincs/cadrumo/commit/23a09e8a1d418501955cff563b27e2ccec870a12))
* **registry:** relocation:validate_governance_stamp_coherence into a governance sibling ([5f98762](https://github.com/nevenincs/cadrumo/commit/5f98762e3e5ea7ae9512fded37c19282323137a8))
* **registry:** relocation:VerificationExpectationDefinition into a verification sibling ([80909cc](https://github.com/nevenincs/cadrumo/commit/80909cc71fa2a1a0c8feb64902f46392bf32fd9a))
* **registry:** resolve each grounding filing year once per modelo ([623d925](https://github.com/nevenincs/cadrumo/commit/623d925b0e77d5f4628e10493a8f4eafa907dc1f))
* **registry:** take the filing-year grounding resolver off the public facade ([9fb3458](https://github.com/nevenincs/cadrumo/commit/9fb34585b39fe476e26b79024d38d920899bb5eb))
* **sede:** split the declarations fetch primitives out of the register session ([01fdd55](https://github.com/nevenincs/cadrumo/commit/01fdd557b09d6ac03fee36d0b6a472b33cccc151))
* **sede:** type the censal dispatch reader's page and session ([c4a077c](https://github.com/nevenincs/cadrumo/commit/c4a077c298de7bae41a3a0d7056b1c009e50a029))
* **storage:** collapse the six identical unreadable-row constructions ([5ac5fd4](https://github.com/nevenincs/cadrumo/commit/5ac5fd411cb840ecf047c7e397e75a439e9b1125))
* **storage:** give the namespace vocabulary its own home ([b0d267f](https://github.com/nevenincs/cadrumo/commit/b0d267f616fc2ad38935e62ad6317433eb46431e))
* **storage:** lift the payload upgrade hop out of the row decoder ([605463f](https://github.com/nevenincs/cadrumo/commit/605463f6a8161285fb8df86fcbca0e429cccc69c))
* **wizard:** clear the last three wizard complexity hotspots ([dda3013](https://github.com/nevenincs/cadrumo/commit/dda3013e2477f487ca9d0b880d7b68df559ddfb0))


### Miscellaneous Chores

* **imports:** register the five TUI test reaches whoever landed them left undocumented ([ed0bdc9](https://github.com/nevenincs/cadrumo/commit/ed0bdc975a259bc2cb810855e6ad0f4e036500d0))
* **profile:** commit the residual worktree edits before retirement ([c1466a7](https://github.com/nevenincs/cadrumo/commit/c1466a73bfaf90598d13fbbf4e9d2b728277814a))
* **quality:** restore green ruff style and format gates ([8267296](https://github.com/nevenincs/cadrumo/commit/8267296c4319dd37a53b85b1f6e87dc6b0836858))
* **release:** reset every version declaration to 0.0.0 ([d89c58a](https://github.com/nevenincs/cadrumo/commit/d89c58aca05a064959f4135e089553115ce89a68))
* **release:** retire the second PyPI lane, its premise is void ([e9e5acc](https://github.com/nevenincs/cadrumo/commit/e9e5acceb96875c71e21049b0dc9980e68abdf06))
* **vault:** land the tree-wide stamp refresh and the three reopened records ([6f44575](https://github.com/nevenincs/cadrumo/commit/6f44575c1f54d6aac148de92a3664332cbd3e975))
* **vault:** rebuild the conformance-cli feature index over the two closed steps ([c36ef97](https://github.com/nevenincs/cadrumo/commit/c36ef97629e0019e28ae1a857b1472f502b8eaa7))
* **worktree:** operator-directed bulk commit of all in-flight work ([8f1cb4f](https://github.com/nevenincs/cadrumo/commit/8f1cb4fc83a91598deebda3635d1730e75ce4a78))
* **worktree:** operator-directed commit of all in-flight work ([33129cc](https://github.com/nevenincs/cadrumo/commit/33129cc83f0dbbdd1c83a153e23d40294de2c9e0))


### Tests

* annotate two helpers with the types they already return ([9fc6735](https://github.com/nevenincs/cadrumo/commit/9fc673517cb5bf92f0e4649a2df46e39493ec8b9))
* **auth:** construct the unreachable credential store the custody test names ([6a17c89](https://github.com/nevenincs/cadrumo/commit/6a17c89ba1a36ef71ddcfb737b35cb1aefc62b8b))
* **auth:** pin the comparison the certificate provider's fail-closed rests on ([c16607c](https://github.com/nevenincs/cadrumo/commit/c16607cad492e93d0e188d2806fa441dd4b7e34c))
* **auth:** pin the persistence half of a Cl@ve session, and name the half that cannot be ([6c602ba](https://github.com/nevenincs/cadrumo/commit/6c602ba89eaa5385cd9eec43f3534ff478ec09c9))
* **boundary:** pin the three detector branches that no test could flip ([3357998](https://github.com/nevenincs/cadrumo/commit/3357998d7fe38e67e6b14725fd77ae0bdacc1392))
* bring two gates back onto the enforcement that now applies ([458e3f6](https://github.com/nevenincs/cadrumo/commit/458e3f68725221ca9b1769d9caaa8f2a03bd1e35))
* **calculations:** put the module marker above the type-checking block ([cbef1df](https://github.com/nevenincs/cadrumo/commit/cbef1df27e87e0ad2ae24285428db1afd11b867a))
* **censo:** put the module marker back above the constants ([bb5775e](https://github.com/nevenincs/cadrumo/commit/bb5775e44db19f7240ab0c8d0cc6da5a30d922d8))
* **censo:** state the docstring guard as a present rule, not campaign history ([9b7835d](https://github.com/nevenincs/cadrumo/commit/9b7835d0efa71b9422805d7fae2ae4bc49bcc0c3))
* **cli:** fail when a risk row outlives the command it classifies ([83f5098](https://github.com/nevenincs/cadrumo/commit/83f5098ab5e9be0b42e3c175af81e65c20bf06f9))
* **cli:** gate custody schema keys, exclusivity, and secret-free results ([3539f2c](https://github.com/nevenincs/cadrumo/commit/3539f2c413d452fb9fc3d7b6c50748e895adb886))
* **cli:** narrow the reconcile envelope rows instead of subscripting object ([a791860](https://github.com/nevenincs/cadrumo/commit/a7918604a1d38e9a3d3535558bdd850f05026c8e))
* **command-search:** reject retired keys and drop a tautological assertion ([a58bee2](https://github.com/nevenincs/cadrumo/commit/a58bee2c1f8e75b1e1307bc211d65b3a264828ab))
* **conformance:** prove every verb, both ratchet directions, and the stamp rollback ([a23a323](https://github.com/nevenincs/cadrumo/commit/a23a323e1560f408afbae5a623c11fb2d419288e))
* **constants:** assemble the last four AEAT route literals from the declarations ([c42c12c](https://github.com/nevenincs/cadrumo/commit/c42c12ceb251b745b5270bf31b8a83ff4c5aecf2))
* **core:** allowlist the reconciliation-record fixture's justificante filename ([16bbb12](https://github.com/nevenincs/cadrumo/commit/16bbb1206f371665311bbb4e56dda52355c9676e))
* **core:** allowlist the source-digest test's justificante filename ([a33d077](https://github.com/nevenincs/cadrumo/commit/a33d07755803f16108bfa72dcbac59fb924d3936))
* **coverage:** fail an exemption whose module no longer exists ([3051151](https://github.com/nevenincs/cadrumo/commit/3051151a2b45b92b389b055b6ead3986272ff8f7))
* **declaracion:** assert the Modelo 100 exclusion instead of only describing it ([c3f99eb](https://github.com/nevenincs/cadrumo/commit/c3f99eb75efdd38285fd1616cc737a219466611e))
* **declaracion:** make the real-render gate select the profile production selects ([c8da7ab](https://github.com/nevenincs/cadrumo/commit/c8da7ab6816131fc86d594e22809ca9d06880e9c))
* **declaracion:** pin that extraction reads position on the page, not position in the list ([ab57d3f](https://github.com/nevenincs/cadrumo/commit/ab57d3f44c00ea6a6ec765497c0d50d6289bee39))
* **declaracion:** pin which monetary targets the blank-box guard is armed on ([4df0e35](https://github.com/nevenincs/cadrumo/commit/4df0e35d525e36542ab1ef60425bb149b35f1255))
* **declaracion:** read the real filed declarations, and widen M390 to the language AEAT printed ([af72a04](https://github.com/nevenincs/cadrumo/commit/af72a043e5198b6877128b086c5a3c2a19ce9069))
* **dev:** pin the two f-string tail branches no fixture could distinguish ([3c55196](https://github.com/nevenincs/cadrumo/commit/3c55196e76af80c7cd8c1be280819627724bea66))
* **dev:** retire the last bare utf-8 literal and the publication monkeypatch ([772be20](https://github.com/nevenincs/cadrumo/commit/772be20c70ebc66551d43d90d510d6b0c001ecb1))
* **filing:** assert the snapshot carries a filing period before reading it ([41698ae](https://github.com/nevenincs/cadrumo/commit/41698aecb48bba65eb0bee86ab69c8c23cec0a78))
* **filing:** name the registry slots for what they hold, not for a double ([54bd7da](https://github.com/nevenincs/cadrumo/commit/54bd7dac103e9d32dd801936031c55d0eb235560))
* **filing:** put the module marker above the type-checking block ([c94dd65](https://github.com/nevenincs/cadrumo/commit/c94dd651d4c050e45eb18312266381ebb5f3945a))
* **filing:** restore an independent oracle for the fichero-BOE required-casilla set ([075aacb](https://github.com/nevenincs/cadrumo/commit/075aacb0419c8d64ee67646ceb5378436c50e1ba))
* **fixtures:** add the generators that reproduce the seven withdrawn renders ([761660a](https://github.com/nevenincs/cadrumo/commit/761660a76d7fca4d3c7d7739e3f60efbf06c3db2))
* **fixtures:** bring the borrador and n26 corpora under provenance discipline ([e647e46](https://github.com/nevenincs/cadrumo/commit/e647e46e128e35b96eaaee97db233a8dd28f31e9))
* **fixtures:** give the synthetic sanitiser version a declared home ([c116b21](https://github.com/nevenincs/cadrumo/commit/c116b21dd5650dc4bce0c4dd2cdc0b406f7b0811))
* **fixtures:** replace the last seven real renders, and repair the split HEAD ([156765e](https://github.com/nevenincs/cadrumo/commit/156765eb429ac338b147cec3e78a314349895238))
* **gates:** close the corpus-walking worklist, and credit a guard at its source ([5980621](https://github.com/nevenincs/cadrumo/commit/5980621d774673a897d74df575927faed8bbd0ec))
* **gates:** guard five more corpus walks, and let an attribute prove the scan ([c07ddd8](https://github.com/nevenincs/cadrumo/commit/c07ddd80727a356254f84014f14f7e95acfc8eff))
* **gates:** make a fixture bind its version constant instead of restating it ([7a5ccc3](https://github.com/nevenincs/cadrumo/commit/7a5ccc30406548951b53e54b2441e17258e85d74))
* **gates:** make nine gates prove they scanned, and triage the rest of the worklist ([b07635c](https://github.com/nevenincs/cadrumo/commit/b07635c4ab886a9044f5744d9c6fd0af40f4631a))
* **gates:** name the residual-identity control for what it is and route it through the facade ([63b357f](https://github.com/nevenincs/cadrumo/commit/63b357fc668ac7f21abf3a43373ef75b337c1cde))
* **harness:** give the ten unreachable dev/ test directories a lane ([071601e](https://github.com/nevenincs/cadrumo/commit/071601e271fc3b691726227fa90d34f9a4904634))
* **harness:** let tests that need a resident search service declare it ([71b63fb](https://github.com/nevenincs/cadrumo/commit/71b63fbe0604f01a089ae487ac84636b3bb5bf56))
* **infra:** give the held-serial reporter a stated writer contract ([9f255e5](https://github.com/nevenincs/cadrumo/commit/9f255e5c50f9297e3652683ed21b66942efc0a4f))
* **markers:** put back the five lines my marker comment took over budget ([e2dd1d3](https://github.com/nevenincs/cadrumo/commit/e2dd1d32b3cb83b021288ec3540aac8bc200f9e0))
* **modelo:** pin that the drift anchor stays out of revision identity ([05280af](https://github.com/nevenincs/cadrumo/commit/05280af8ae90b0d4910d83f495cd0a243ac74916))
* **modelo:** pin why an evidence-less amendment is not an export refusal ([af36241](https://github.com/nevenincs/cadrumo/commit/af362411d9ce1b3d8f42cece2327bb22e9a9ff67))
* **modelo:** put the module marker above the repository type alias ([de15d0c](https://github.com/nevenincs/cadrumo/commit/de15d0c8d4daa80d848783c3ab8a36d6f88239fa))
* **privacy:** ban cross-project identifiers, and scan the untracked files too ([042dd75](https://github.com/nevenincs/cadrumo/commit/042dd7522297c684aed6b992ec51c07588e6aff1))
* **profile:** drop a word from a docstring that the marker gate reads as process metadata ([6904137](https://github.com/nevenincs/cadrumo/commit/6904137de5f65f04be69cde201fdbcf7aef2fd64))
* **profile:** give the schema-valid filler one definition and a guard ([e873b8e](https://github.com/nevenincs/cadrumo/commit/e873b8ef7bc176917b7dae1a5b1db084ab1b7a7d))
* **profile:** hold the minimal-profile filler table to the schema ([12d27df](https://github.com/nevenincs/cadrumo/commit/12d27df2c9e3d18479ce8e820f6e9faf5abcbc1b))
* **registry:** declare the module marker before the module constant ([29c518d](https://github.com/nevenincs/cadrumo/commit/29c518dab29161338f5b6dab45e68abe89b8353c))
* **registry:** give the governance stamp gates real teeth ([5ec1f98](https://github.com/nevenincs/cadrumo/commit/5ec1f98f1a2ace2724d674fb8497482cec05d9c5))
* **registry:** hold the classification fold's behaviour, not the tree's census ([1758aa9](https://github.com/nevenincs/cadrumo/commit/1758aa967102666ea7510d1136da55e270b735c1))
* **registry:** prove the conformance composer reads its inputs, not its defaults ([4f96f74](https://github.com/nevenincs/cadrumo/commit/4f96f74899f343a62f85546b3e1d7598b2993eb2))
* **registry:** prove the export-format lift at the registry boundary ([a368a3f](https://github.com/nevenincs/cadrumo/commit/a368a3fa615ac3f9b47782cf7a8547b4c985c56d))
* **registry:** re-anchor the revision diff on differences that cannot converge ([00ebdd3](https://github.com/nevenincs/cadrumo/commit/00ebdd3f741a5c32d51054e1492f168ca6d97d71))
* **registry:** retire the single-revision no-volume prorrata regression ([47a6487](https://github.com/nevenincs/cadrumo/commit/47a6487742505744af8b6aaf2725df159d932676))
* **registry:** state the degraded-read rule without citing a development record ([d85c0df](https://github.com/nevenincs/cadrumo/commit/d85c0df37f40c413fbe5a6147c49a959317ca4a6))
* **registry:** stop reading an empty default as an unresolvable source_ref ([2e222b4](https://github.com/nevenincs/cadrumo/commit/2e222b4f96b004e7e0b0424bdbff014fd0ffdece))
* **release,filing:** retire the last two monkeypatch sites without weakening either proof ([bdf6061](https://github.com/nevenincs/cadrumo/commit/bdf6061d0774152075809000d0d5c2744dfdffd6))
* retarget three gates onto the contracts that now hold ([2408f37](https://github.com/nevenincs/cadrumo/commit/2408f3703025c2fbecccf72983d55d10f9dd7e39))
* **sanitizer:** gate on identities the sanitiser was never told about ([5ba159c](https://github.com/nevenincs/cadrumo/commit/5ba159c02968a21cc12f5866196ec769afc73f33))
* **sanitizer:** restore a live positive control for the residual-identity gate ([cf761f5](https://github.com/nevenincs/cadrumo/commit/cf761f5dcb6c1b7f14dbfcaa16f85a0a723bf3e3))
* **sanitizer:** scan every real-provenance artefact, not one directory ([b19addf](https://github.com/nevenincs/cadrumo/commit/b19addf66137b3dde8af7bf51ed6431b91116e57))
* **storage:** pin the rotation cipher-envelope carry, non-vacuously ([e883937](https://github.com/nevenincs/cadrumo/commit/e8839373dbc443a77ca7f8609e6c514f35e7ca73))
* **storage:** stop two fixtures writing a manifest the read path refuses ([d6de762](https://github.com/nevenincs/cadrumo/commit/d6de762ead179ecde7b51e48ff8f8d07b755c0d2))
* **tui:** put the module marker above the type-checking block ([b24cd30](https://github.com/nevenincs/cadrumo/commit/b24cd30f3d958896533fe251f55b66ac55837bdd))
* **verification:** retract the AEAT-grounding claims these fixtures cannot support ([7810d39](https://github.com/nevenincs/cadrumo/commit/7810d3992f4eb9ec65d6770e557632db8042dad9))
* **verification:** split parse-fidelity from arithmetic, and make the arithmetic discriminating ([a1806ce](https://github.com/nevenincs/cadrumo/commit/a1806ceff46e1899a62f3ae08b1e35678a18a821))

## [0.2.1] - 2026-07-19

First public release cohort of **Cadrumo** — the product's first distribution
under its product name (renamed from the internal `aeat` working name) — built
once into one immutable, hash-bound cross-platform cohort and promoted without
rebuild to every channel, so PyPI, the GitHub release, Scoop, and Homebrew all
serve identical bytes. No `v0.2.0` distribution was ever published;
the `v0.2.0` tag predates the work below.

### Added

- **Distribution channels:** Cadrumo installs from PyPI
  (`cadrumo`, `cadrumo-data-manuals`, `cadrumo-data-official` via Trusted
  Publishing), the GitHub release, a Scoop bucket, and a Homebrew tap. Every artefact is
  digest-verified against the one tested cohort; each channel's installed
  behaviour is proven by a grounded tax-work oracle before release.

### Changed

- **Product identity:** the Python package imports as `cadrumo`, while the human
  CLI executable is `aeat`.
- **User documentation:** the installation surfaces address end users
  installing a released package; developer-checkout setup moved to
  `CONTRIBUTING.md`.

### Fixed

- **Packaging:** `click` is now a declared direct dependency; `typer>=0.26`
  stopped pulling it in, so a clean wheel install crashed on import
  (`ModuleNotFoundError: click`). Caught by the split-install packaging
  smoke; `uv.lock` reconciled to the committed `pyproject.toml`.
- **Publish lane:** one GitHub environment per distribution
  (`pypi`, `pypi-data-manuals`, `pypi-data-official`) so all three pending
  Trusted Publishers can register from the one publish workflow.
- **`just doctor`** invoked a nonexistent `cadrumo` console script; the
  human CLI is `aeat`.

## [0.2.0] - 2026-07-04

Prepared per issue #382. No `v0.1.0` git tag exists on the remote, so this
section is a hand-curated summary of the work landed on `main` since the
0.1.0 baseline (2026-04-12) rather than a `release-please`-generated
per-commit log; `just release` should still be run by the operator at cut
time to let release-please walk the full commit history and reconcile this
summary against its own changelog delta. The interval spans thousands of
commits — dominated by a large registry/calculation-grounding hardening
campaign and a hexagonal-architecture restructure (#476) — so entries below
are grouped by domain rather than enumerated per commit. No breaking changes
to released data: the project remains pre-beta with zero released versions,
so there is no upgrade path to document (see `no-legacy-compatibility`).

### Highlights

- **Modelo calculation coverage:** extended registry-grounded calc-verify
  roundtrips across Modelos 100 (RENTA, full-form), 111, 115, 123, 130, 131,
  180, 190, 200, 303, 347, 349, 390, 720, and others, each grounded in BOE /
  AEAT workbooks and cross-checked against the legal-citation registry.
- **CLI surface:** typed `--json` output contract with a shared envelope
  spine, `ErrorCode` registry, exit-code table, and a uniform `Notice`
  diagnostics channel replacing ad hoc advisory fields.
- **Ledger hardening:** absolute-magnitude transaction amounts with
  direction as the sole flow authority, idempotent-guarded single-subject
  mutations, evidence-bundled ledger-derived calculation revisions, and a
  rebuildable transaction-to-revision participation index.
- **Secure persistence:** encrypted secure-object storage foundation for
  sensitive financial data (invoices, bank statements, evidence bytes),
  content-addressed attachment storage, and profile-bucket scoping.
- **Registry authority:** consolidated the modelo registry into a single
  deterministic TOML-authoring → loader/compiler → validated-authority →
  snapshot pipeline, with binding/resolver taxonomy hardening (source kinds,
  aggregation ops, provenance parity with casilla observations).
- **Architecture restructure (#476):** relocated the codebase onto a
  hexagonal layout (`core` / `domain` / `application` / `adapters` /
  `entrypoints`), removed compatibility shims and dead code, and enforced
  import-linter boundary contracts.
- **Documentation:** generated CLI reference and API-doc scaffolding tied to
  the live Typer tree, a Terminology Handbook glossary, and locale-catalogue
  CLI tooling for `en`/`es`/`ca`/`hu`.

### Notes

- Live AEAT submission remains permanently forbidden; this release only
  extends build / validate / verify / export capability outside the
  application (see `aeat-safety-legal-gates`).
- Version bump applied at cut time: `pyproject.toml [project].version`,
  `src/aeat/__init__.py __version__`, and `.release-please-manifest.json`
  now read `0.2.0` (per the `2026-04-12-release-please-adr` human-gated cut).

## [0.1.1] - 2026-07-04

### Fixed

- `corpus-sources` extra now resolves: the published 0.1.0 metadata pinned the
  never-published single `aeat-data` companion; 0.1.1 pins the two sub-cap
  companions (`aeat-data-manuals`, `aeat-data-official`) that actually ship.

Run `just release` to preview the next release. Run `just release-apply`
to land the version bump and CHANGELOG entries on `main` (human-gated,
no push).

## [0.1.0] - 2026-04-12

Initial scaffolding release. Backfilled from conventional-commit history
on `main` through 2026-04-12. Merge commits and non-conventional messages
are omitted.

### Features

- **auth:** PKCS#12 client certificate authentication for AEAT (#8, #58)
- **testing:** synthetic filing-history fixtures + loader (#14, #56)
- **inbox:** AEAT notifications inbox (#46, #55)
- **normatives:** typed BOE-linked Spanish tax normatives catalogue (#45, #53)
- **status:** AEAT live status reader (#43)
- **google-fixtures:** Google Workspace test fixture surface (#13, #29)
- **submission:** dry-run-default filing submission engine (#42, #49)
- **filing:** typed `FilingDraft` + `Modelo130Builder` PoC + CLI (#39)
- **deadlines:** filing-deadline computation engine (#38, #47)
- **manuals:** Manual práctico schema, loader, CLI skeleton, raw-PDF manifests (#25, #35)
- **sync:** self-healing live-to-local sync runner (#11, #37)
- **storage:** scaffold SQLite + SQLAlchemy + Alembic storage layer (#10, #28)
- **browser:** Playwright anti-bot evasion (#16, #26)

### Bug Fixes

- **status:** apply code-review and round-2 findings (#43)
- address review feedback: NFC normalization, type safety, fallback config

### Documentation

- **audit:** PR #28 storage retrospective + reviewer hardening (#32, #40)

### Miscellaneous Chores

- **ci:** add GitHub Actions workflow for Ubuntu/Windows parity (#31, #34) — later superseded when GitHub Actions was permanently disabled on the repo
- **dev-scaffolding:** full `gsuite-bootstrap` pipeline + CLI + doctor (#4, #18)
- base module structure scaffolding (#19)
