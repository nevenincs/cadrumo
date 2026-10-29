"""Registry-prepared setup questions for family sections."""

from __future__ import annotations

from ...core.i18n.translatable import Translatable as tr
from ...domain.contribuyente.renta_codes import RentaMaritalStatus
from .models import WizardChoice, WizardCondition, WizardQuestion, WizardSection, WizardWidget
from .setup_questions import confirmation_question


def build_family_section(
    _eu_eea_resident: WizardCondition,
    _joint_declaration: WizardCondition,
    _natural_person: WizardCondition,
    _non_resident_irpf: WizardCondition,
    wizard_declaration_type_choices: tuple[WizardChoice, ...],
    wizard_disability_grade_choices: tuple[WizardChoice, ...],
    wizard_marital_status_choices: tuple[WizardChoice, ...],
    wizard_sex_choices: tuple[WizardChoice, ...],
    wizard_situacion_familiar_choices: tuple[WizardChoice, ...],
) -> WizardSection:
    """Build the familia section under the caller's prepared choices."""
    return WizardSection(
        id="familia",
        title=tr("wizard.setup.familia.title"),
        questions=(
            WizardQuestion(
                id="taxation-type",
                profile_key="renta_filing.declaration_type",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.profile.taxation-type.prompt"),
                choices=wizard_declaration_type_choices,
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                id="taxpayer-sex",
                profile_key="renta_taxpayer.sex",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.taxpayer.taxpayer-sex.prompt"),
                choices=wizard_sex_choices,
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                id="taxpayer-marital-status",
                profile_key="renta_taxpayer.marital_status",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.taxpayer.taxpayer-marital-status.prompt"),
                choices=wizard_marital_status_choices,
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                # Art. 82 LIRPF: situación familiar determines whether conjunta
                # (joint) taxation is available and which unidad-familiar variant
                # applies. Distinct from the Modelo 100 marital-status code
                # (which maps to form rows); this axis drives the verifier check
                # and future casilla routing.
                id="situacion-familiar",
                profile_key="renta_family.situacion_familiar",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.taxpayer.situacion-familiar.prompt"),
                help=tr("wizard.setup.taxpayer.situacion-familiar.help"),
                choices=wizard_situacion_familiar_choices,
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                # Art. 82.1 LIRPF: matrimonio sobrevenido — records the date the
                # current marriage began.  Drives casillas 0245 (vigente todo el año),
                # 0246 (primer mes), and 0247 (último mes completo).  Only asked when
                # the taxpayer is married (marital_status = "2").
                id="taxpayer-marriage-date",
                profile_key="renta_taxpayer.marriage_date",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.taxpayer.taxpayer-marriage-date.prompt"),
                required=False,
                visible_when=WizardCondition(
                    question_id="taxpayer-marital-status", equals=RentaMaritalStatus.CASADO.value
                ),
                answer_type=str,
            ),
            WizardQuestion(
                id="taxpayer-birth-date",
                profile_key="renta_taxpayer.birth_date",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.taxpayer.taxpayer-birth-date.prompt"),
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                id="taxpayer-disability-grade",
                profile_key="renta_taxpayer.disability_grade",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.taxpayer.taxpayer-disability-grade.prompt"),
                choices=wizard_disability_grade_choices,
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                id="taxpayer-death-date",
                profile_key="renta_taxpayer.death_date",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.taxpayer.taxpayer-death-date.prompt"),
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            *_spouse_questions(
                _eu_eea_resident,
                _joint_declaration,
                _non_resident_irpf,
                wizard_sex_choices,
                wizard_disability_grade_choices,
            ),
            confirmation_question(
                "family-descendants-eu-eea-deduction",
                "renta_family.descendants_eu_eea_deduction",
                suffix="family",
                visible_when=_natural_person,
            ),
            confirmation_question(
                "family-minor-children-in-unit",
                "renta_family.minor_children_in_unit",
                suffix="family",
                visible_when=_natural_person,
            ),
        ),
    )


def _spouse_questions(
    _eu_eea_resident: WizardCondition,
    _joint_declaration: WizardCondition,
    _non_resident_irpf: WizardCondition,
    wizard_sex_choices: tuple[WizardChoice, ...],
    wizard_disability_grade_choices: tuple[WizardChoice, ...],
) -> tuple[WizardQuestion, ...]:
    return (
        WizardQuestion(
            # Required *when visible*: a joint declaration is invalid
            # without the spouse NIF (SetupAnswers enforces the same
            # invariant). The widget validator still accepts a blank
            # answer for a gated question; the conditional requirement
            # is enforced at `validate_profile_values` via the compiled
            # `required_when_*` pair.
            id="spouse-tax-id",
            profile_key="renta_spouse.tax_id",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-tax-id.prompt"),
            required=True,
            visible_when=_joint_declaration,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-name",
            profile_key="renta_spouse.name",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-name.prompt"),
            required=False,
            visible_when=_joint_declaration,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-surnames",
            profile_key="renta_spouse.surnames",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-surnames.prompt"),
            required=False,
            visible_when=_joint_declaration,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-birth-date",
            profile_key="renta_spouse.birth_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-birth-date.prompt"),
            required=False,
            visible_when=_joint_declaration,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-sex",
            profile_key="renta_spouse.sex",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-sex.prompt"),
            choices=wizard_sex_choices,
            required=False,
            visible_when=_joint_declaration,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-disability-grade",
            profile_key="renta_spouse.disability_grade",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-disability-grade.prompt"),
            choices=wizard_disability_grade_choices,
            required=False,
            visible_when=_joint_declaration,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-non-resident-irpf",
            profile_key="renta_spouse.non_resident_irpf",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.spouse.spouse-non-resident-irpf.prompt"),
            required=False,
            default="false",
            visible_when=_joint_declaration,
            answer_type=bool,
        ),
        WizardQuestion(
            id="spouse-eu-eea-resident",
            profile_key="renta_spouse.eu_eea_resident",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.spouse.spouse-eu-eea-resident.prompt"),
            required=False,
            default="false",
            visible_when=_non_resident_irpf,
            answer_type=bool,
        ),
        WizardQuestion(
            # Required *when visible*: an EU/EEA-resident spouse must
            # name the residence country (SetupAnswers enforces the
            # same invariant). The conditional requirement is compiled
            # into the `required_when_*` pair.
            id="spouse-eu-eea-country",
            profile_key="renta_spouse.eu_eea_country",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-eu-eea-country.prompt"),
            required=True,
            visible_when=_eu_eea_resident,
            answer_type=str,
        ),
    )
