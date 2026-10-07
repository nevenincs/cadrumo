"""Assemble a calculation summary: drawn, tagged, certified, embedded, archival.

The writer the application's summary port names. It draws the pages the
presentation describes, tags them, measures the finished page layer and asks the
application to sign a statement binding that measurement, then embeds the
report, its CSV, the statement and the signature as associated files and writes
the document metadata and colour output intent PDF/A-3 requires.

The container is PDF 1.7 claiming PDF/A-3 level ``a`` and PDF/UA-1. It carries
no document information dictionary: every descriptive fact is in the XMP packet,
and that packet holds only content-addressed identifiers, digests, codes, the
software-identity grade, the export instant and the public key -- never the
taxpayer's name or tax identifier, which appear on the page and in the embedded
data only. Every product property in the packet is declared in its extension
schema, as archival conformance requires.

Output is deterministic: the page writer runs in its invariant mode, every date
is the report's export instant, the document identifiers are derived from the
content, and the file identifier is computed from the content when it is saved.
Two writes of one report with one key produce the same bytes.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Final
from xml.sax.saxutils import escape

from ....application.modelo.calculation_report_certification import (
    CALCULATION_SUMMARY_PDF_RENDER_PROFILE,
    CERTIFICATION_XMP_PROPERTIES,
)
from ....application.modelo.calculation_summary_pdf_ports import (
    CALCULATION_SUMMARY_ATTACHMENTS,
    CALCULATION_SUMMARY_XMP_NAMESPACE,
    CALCULATION_SUMMARY_XMP_PREFIX,
    CSV_ATTACHMENT_NAME,
    REPORT_ATTACHMENT_NAME,
    SIGNATURE_ATTACHMENT_NAME,
    STATEMENT_ATTACHMENT_NAME,
    CalculationSummaryCertifier,
    CalculationSummaryPdfRequest,
)
from ....core.optional_extras import PDF_EXTRA, require_optional_extra
from ....core.product_identity import PRODUCT_IDENTITY
from ....core.resources.bundled_data import packaged_data

if TYPE_CHECKING:
    import pikepdf

OUTPUT_INTENT_PROFILE: Final[tuple[str, ...]] = ("calculation_summary_pdf", "color", "sRGB-IEC61966-2.1.icc")
"""The fixed sRGB profile every summary declares as its output intent.

Shipped as data rather than generated: a freshly generated profile stamps its
creation time into its header, and every summary would then differ.
"""

_OUTPUT_CONDITION: Final[str] = "sRGB IEC61966-2.1"
_PDF_VERSION: Final[str] = "1.7"
_PDFA_NAMESPACE: Final[str] = "http://www.aiim.org/pdfa/ns/id/"
_PDFUA_NAMESPACE: Final[str] = "http://www.aiim.org/pdfua/ns/id/"
_DOCUMENT_ID_NAMESPACE: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_URL, CALCULATION_SUMMARY_XMP_NAMESPACE)


def _pdf_date(request: CalculationSummaryPdfRequest) -> str:
    return "D:" + request.exported_at.strftime("%Y%m%d%H%M%S") + "Z"


def _xmp_date(request: CalculationSummaryPdfRequest) -> str:
    return request.exported_at.strftime("%Y-%m-%dT%H:%M:%SZ")


def _schema_description(
    *,
    namespace: str,
    prefix: str,
    label: str,
    properties: Iterable[tuple[str, str]],
    value_type: str,
    category: str,
) -> str:
    rows = "".join(
        '<rdf:li rdf:parseType="Resource">'
        f"<pdfaProperty:name>{escape(name)}</pdfaProperty:name>"
        f"<pdfaProperty:valueType>{value_type}</pdfaProperty:valueType>"
        f"<pdfaProperty:category>{category}</pdfaProperty:category>"
        f"<pdfaProperty:description>{escape(description)}</pdfaProperty:description>"
        "</rdf:li>"
        for name, description in properties
    )
    return (
        '<rdf:li rdf:parseType="Resource">'
        f"<pdfaSchema:schema>{escape(label)}</pdfaSchema:schema>"
        f"<pdfaSchema:namespaceURI>{escape(namespace)}</pdfaSchema:namespaceURI>"
        f"<pdfaSchema:prefix>{prefix}</pdfaSchema:prefix>"
        f"<pdfaSchema:property><rdf:Seq>{rows}</rdf:Seq></pdfaSchema:property>"
        "</rdf:li>"
    )


def build_summary_xmp(
    request: CalculationSummaryPdfRequest,
    *,
    product_properties: Mapping[str, str],
    statement_sha256: str,
) -> bytes:
    """Return the summary's XMP packet.

    Title and description are in the report language; the description is the
    local-calculation statement. The document identifier is derived from the
    report digest and the instance identifier from the statement digest, so both
    are content addresses rather than random values.
    """
    presentation = request.presentation
    language = presentation.language.value
    date = _xmp_date(request)
    product = "".join(
        f"<{CALCULATION_SUMMARY_XMP_PREFIX}:{name}>{escape(value)}</{CALCULATION_SUMMARY_XMP_PREFIX}:{name}>"
        for name, value in product_properties.items()
    )
    schemas = _schema_description(
        namespace=CALCULATION_SUMMARY_XMP_NAMESPACE,
        prefix=CALCULATION_SUMMARY_XMP_PREFIX,
        label="Cadrumo calculation summary certification",
        properties=CERTIFICATION_XMP_PROPERTIES,
        value_type="Text",
        category="external",
    ) + _schema_description(
        namespace=_PDFUA_NAMESPACE,
        prefix="pdfuaid",
        label="PDF/UA identification schema",
        properties=(("part", "Part of the PDF/UA standard the document conforms to"),),
        value_type="Integer",
        category="internal",
    )
    document_id = uuid.uuid5(_DOCUMENT_ID_NAMESPACE, request.report_sha256)
    instance_id = uuid.uuid5(_DOCUMENT_ID_NAMESPACE, statement_sha256)
    packet = (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        f'<rdf:Description rdf:about="" xmlns:pdfaid="{_PDFA_NAMESPACE}">'
        "<pdfaid:part>3</pdfaid:part><pdfaid:conformance>A</pdfaid:conformance></rdf:Description>\n"
        f'<rdf:Description rdf:about="" xmlns:pdfuaid="{_PDFUA_NAMESPACE}"><pdfuaid:part>1</pdfuaid:part>'
        "</rdf:Description>\n"
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:format>application/pdf</dc:format>"
        "<dc:title><rdf:Alt>"
        f'<rdf:li xml:lang="x-default">{escape(presentation.title)}</rdf:li>'
        f'<rdf:li xml:lang="{language}">{escape(presentation.title)}</rdf:li>'
        "</rdf:Alt></dc:title>"
        "<dc:description><rdf:Alt>"
        f'<rdf:li xml:lang="x-default">{escape(presentation.notice_body)}</rdf:li>'
        "</rdf:Alt></dc:description>"
        f"<dc:language><rdf:Bag><rdf:li>{language}</rdf:li></rdf:Bag></dc:language>"
        "</rdf:Description>\n"
        '<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
        f"<xmp:CreateDate>{date}</xmp:CreateDate><xmp:ModifyDate>{date}</xmp:ModifyDate>"
        f"<xmp:MetadataDate>{date}</xmp:MetadataDate>"
        f"<xmp:CreatorTool>{escape(PRODUCT_IDENTITY.display_name)} {CALCULATION_SUMMARY_PDF_RENDER_PROFILE}"
        "</xmp:CreatorTool></rdf:Description>\n"
        '<rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        f"<pdf:Producer>{escape(PRODUCT_IDENTITY.display_name)}</pdf:Producer></rdf:Description>\n"
        '<rdf:Description rdf:about="" xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">'
        f"<xmpMM:DocumentID>uuid:{document_id}</xmpMM:DocumentID>"
        f"<xmpMM:InstanceID>uuid:{instance_id}</xmpMM:InstanceID></rdf:Description>\n"
        f'<rdf:Description rdf:about="" xmlns:{CALCULATION_SUMMARY_XMP_PREFIX}="{CALCULATION_SUMMARY_XMP_NAMESPACE}">'
        f"{product}</rdf:Description>\n"
        '<rdf:Description rdf:about="" xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/" '
        'xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#" '
        'xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">'
        f"<pdfaExtension:schemas><rdf:Bag>{schemas}</rdf:Bag></pdfaExtension:schemas></rdf:Description>\n"
        "</rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    )
    return packet.encode("utf-8")


def _attach(pdf: pikepdf.Pdf, files: Mapping[str, bytes], *, date: str) -> None:
    import pikepdf
    from pikepdf import Array, Name

    associated = Array()
    for attachment in CALCULATION_SUMMARY_ATTACHMENTS:
        specification = pikepdf.AttachedFileSpec(
            pdf,
            files[attachment.name],
            description=attachment.description,
            filename=attachment.name,
            mime_type=attachment.mime_type,
            creation_date=date,
            mod_date=date,
        )
        specification.obj.AFRelationship = Name("/" + attachment.relationship)
        pdf.attachments[attachment.name] = specification
        associated.append(specification.obj)
    pdf.Root.AF = associated


def _output_intent(pdf: pikepdf.Pdf) -> None:
    from pikepdf import Array, Dictionary, Name, String

    profile = pdf.make_stream(packaged_data(*OUTPUT_INTENT_PROFILE).read_bytes())
    profile.N = 3
    pdf.Root.OutputIntents = Array(
        [
            Dictionary(
                Type=Name.OutputIntent,
                S=Name.GTS_PDFA1,
                OutputConditionIdentifier=String(_OUTPUT_CONDITION),
                Info=String(_OUTPUT_CONDITION),
                DestOutputProfile=profile,
            ),
        ],
    )


def _prepare_pages(pdf: pikepdf.Pdf) -> None:
    """Drop what the page writer adds that a summary must not carry.

    The information dictionary duplicates metadata the XMP packet owns and would
    carry the page writer's own creator strings; the procedure-set resource is an
    obsolete hint every reader ignores, and a page may hold no resource but fonts.
    """
    if "/Info" in pdf.trailer:
        del pdf.trailer.Info
    for page in pdf.pages:
        resources = page.obj.get("/Resources")
        if resources is not None and "/ProcSet" in resources:
            del resources.ProcSet


def write_calculation_summary_pdf(
    request: CalculationSummaryPdfRequest,
    /,
    *,
    certify: CalculationSummaryCertifier,
) -> bytes:
    """Write one calculation summary and return its bytes.

    Raises:
        MissingOptionalExtraError: The optional ``pdf`` extra is not installed.
        SummaryTagPlanMismatchError: The drawn pages cannot be tagged from the
            layout's plan.
    """
    require_optional_extra(PDF_EXTRA)
    import pikepdf
    from pikepdf import Name

    from .structure_tagging import tag_summary_pages
    from .summary_layout import draw_summary_pages, lay_out_summary
    from .summary_reading import visible_layer_digest

    presentation = request.presentation
    drawn = draw_summary_pages(lay_out_summary(presentation), language=presentation.language.value)
    with pikepdf.open(io.BytesIO(drawn.payload)) as pdf:
        _prepare_pages(pdf)
        tag_summary_pages(pdf, drawn.plans, language=presentation.language.value)
        page_digest, _overlays = visible_layer_digest(pdf)
        certification = certify(page_digest)
        date = _pdf_date(request)
        _attach(
            pdf,
            {
                REPORT_ATTACHMENT_NAME: request.report_bytes,
                CSV_ATTACHMENT_NAME: request.csv_bytes,
                STATEMENT_ATTACHMENT_NAME: certification.statement_bytes,
                SIGNATURE_ATTACHMENT_NAME: certification.signature,
            },
            date=date,
        )
        metadata = pdf.make_stream(
            build_summary_xmp(
                request,
                product_properties=certification.xmp_properties,
                statement_sha256=certification.statement.statement_sha256,
            ),
        )
        metadata.Type = Name.Metadata
        metadata.Subtype = Name.XML
        pdf.Root.Metadata = metadata
        _output_intent(pdf)
        output = io.BytesIO()
        pdf.save(
            output,
            min_version=_PDF_VERSION,
            deterministic_id=True,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.disable,
        )
    return output.getvalue()


__all__ = ["OUTPUT_INTENT_PROFILE", "build_summary_xmp", "write_calculation_summary_pdf"]
