---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:ba37d9720d490819e2ee52c301ff7e2e30a17237b9a7cc38e0665b9143a473fd'
step_id: 'S45'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
## Description

- Author the Art. 81.2 annual cap as a money parameter on the 2024 revision.
- Author the legal entry grounding the 1.000 figure itself.
- Author a second legal entry grounding the proration, the simultaneity
  requirement, and the per-child spend limit.
- Enrol the parameter in the orphan-parameter allow-list with its removal
  condition named.

## Outcome

The 1.000 figure now has a home the calculation can resolve. It previously
existed only as an inline literal inside the 0613 formula expression -- valid
registry data, and unreadable from the application layer, which is where the
per-child proration is computed. The figure had no address the code could ask
for.

Declared for the 2024 revision alone. It is the only revision that declares
casilla 0613 and the only one where the casilla is computed rather than a
manual form-native entry. This differs from the fallecimiento parameter, which
was authored across all six because all six genuinely served the casilla;
authoring where no consumer is declared would add orphan parameters carrying a
regulatory value nothing resolves.

## Notes

A CORRECTION TO THIS CAMPAIGN'S OWN EARLIER READING, and the substantive result
of the Step. The increment's proration was recorded as stated by the AEAT
manual alone. It is statutory. LIRPF art. 81.3, third paragraph, says the
apartado 2 increment "se calculara de forma proporcional al numero de meses en
que se cumplan de forma simultanea los requisitos de los apartados 1 y 2" and
caps it at the non-subsidised spend "en relacion con ESE HIJO".

So the simultaneity intersection and the per-child bound -- both implemented in
the preceding piece on the manual's authority -- are carried by the statute in
terms. The per-child cap in particular is not an inference from the manual's
"Limite del incremento: 166,67 euros"; the law says "ese hijo". Two legal
entries were authored rather than one so the proration clause has its own
home, and its notes name the misattribution so a later reader meets the
correction rather than repeating it.

This is the second time in this campaign that a rule recorded as manual-only
turned out to be statutory. The bias runs one way -- toward weaker grounding
than the law actually offers -- and is worth suspecting whenever a manual
sentence reads as a gloss.

CORPUS CHOICE. Both entries cite the bundled CONSOLIDATED ley-35-2006.html
rather than the per-article ley-35-2006-art-81.html excerpt the parent entry
uses. That excerpt is a two-vintage hybrid tracked as its own open defect, and
grounding new figures on it would inherit the problem. The parent entry was
left alone: correcting it is that defect's own work, not this Step's.

The parent art-81 entry does not pin the 1.000 figure and could not be reused.
Its required_text covers the 1.200-euro maternidad cap of apartado 1 -- a
different figure for a different concept, which is exactly the coincidence trap
the fallecimiento parameter was kept clear of.

VERIFICATION WAS NOT A BARE GREEN. The parameter's citations and both legal
entries were driven through the production validators with a positive control
substituting an absent sentinel phrase. The control failed on all three, so
none of the probes is vacuous. Drift gate nine passed; legal and catalogue
gates twenty-eight passed.

A TREE OBSERVATION, reported because it was raised earlier in this campaign and
would otherwise sit as open. The production legal-ref literal gate was red on a
pending grounding when it was first reported here; it is green now, so the
sequencing failure has been resolved by whoever owned it.
