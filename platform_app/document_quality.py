import base64
import io
import json
import zipfile
from dataclasses import dataclass, field

import fitz
from django.conf import settings
from docx import Document
from PIL import Image, ImageDraw


@dataclass
class FidelityReport:
    passed: bool
    score: int
    issues: list[str] = field(default_factory=list)
    summary: str = ""
    template_pages: int = 0
    output_pages: int = 0


def _document_from_bytes(payload):
    return Document(io.BytesIO(bytes(payload)))


def _unique_cells(row):
    seen = set()
    result = []
    for cell in row.cells:
        identity = id(cell._tc)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(cell)
    return result


def _structural_header_text(cell):
    """Retorna somente rótulos visuais que definem a geometria da tabela."""

    text = " ".join(cell.text.split()).strip()
    if not text or "{{" in text or len(text) > 160:
        return ""
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return ""
    uppercase_ratio = sum(character.isupper() for character in letters) / len(letters)
    return text if uppercase_ratio >= 0.88 else ""


def _table_signature(document):
    signatures = []
    for table in document.tables:
        first_row = _unique_cells(table.rows[0]) if table.rows else []
        signatures.append(
            {
                "rows": len(table.rows),
                "columns": len(first_row),
                "structural_header": [
                    _structural_header_text(cell) for cell in first_row
                ],
            }
        )
    return signatures


def _package_counts(payload):
    with zipfile.ZipFile(io.BytesIO(bytes(payload))) as package:
        names = package.namelist()
    return {
        "headers": len(
            [
                name
                for name in names
                if name.startswith("word/header") and name.endswith(".xml")
            ]
        ),
        "footers": len(
            [
                name
                for name in names
                if name.startswith("word/footer") and name.endswith(".xml")
            ]
        ),
        "media": len([name for name in names if name.startswith("word/media/")]),
        "styles": int("word/styles.xml" in names),
        "numbering": int("word/numbering.xml" in names),
    }


def audit_docx_structure(
    template_bytes, output_bytes, *, allow_footer_addition=False
):
    template = _document_from_bytes(template_bytes)
    output = _document_from_bytes(output_bytes)
    issues = []

    if len(template.sections) != len(output.sections):
        issues.append("A quantidade de seções de página foi alterada.")

    template_tables = _table_signature(template)
    output_tables = _table_signature(output)
    if len(template_tables) != len(output_tables):
        issues.append("A quantidade de tabelas foi alterada.")
    else:
        for index, (expected, actual) in enumerate(
            zip(template_tables, output_tables)
        ):
            if (
                expected["rows"] != actual["rows"]
                or expected["columns"] != actual["columns"]
            ):
                issues.append(f"A geometria da tabela {index + 1} foi alterada.")
            if expected["structural_header"] != actual["structural_header"]:
                issues.append(
                    f"O cabeçalho estrutural da tabela {index + 1} foi alterado."
                )

    expected_package = _package_counts(template_bytes)
    actual_package = _package_counts(output_bytes)
    for key, label in {
        "headers": "cabeçalhos",
        "media": "imagens incorporadas",
        "styles": "estilos",
        "numbering": "numeração e marcadores",
    }.items():
        if expected_package[key] != actual_package[key]:
            issues.append(f"A estrutura de {label} não foi preservada.")

    expected_footers = expected_package["footers"]
    actual_footers = actual_package["footers"]
    footer_is_allowed = allow_footer_addition and actual_footers in {
        expected_footers,
        expected_footers + 1,
    }
    if actual_footers != expected_footers and not footer_is_allowed:
        issues.append("A estrutura de rodapés não foi preservada.")

    return FidelityReport(
        passed=not issues,
        score=max(0, 100 - 18 * len(issues)),
        issues=issues,
        summary=(
            "Estrutura DOCX preservada."
            if not issues
            else "Foram detectadas alterações estruturais."
        ),
    )


def _render_pdf_pages(pdf_bytes, *, dpi=110, max_pages=8):
    document = fitz.open(stream=bytes(pdf_bytes), filetype="pdf")
    images = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for page in list(document)[:max_pages]:
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        images.append(
            Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        )
    return images, document.page_count


def _contact_sheet(images, title):
    if not images:
        return Image.new("RGB", (800, 200), "white")
    thumb_width = 620
    prepared = []
    for index, image in enumerate(images, start=1):
        height = round(image.height * thumb_width / image.width)
        thumbnail = image.resize((thumb_width, height))
        canvas = Image.new("RGB", (thumb_width, height + 42), "white")
        canvas.paste(thumbnail, (0, 42))
        ImageDraw.Draw(canvas).text(
            (12, 12), f"{title} - página {index}", fill="black"
        )
        prepared.append(canvas)
    sheet_height = sum(image.height for image in prepared)
    sheet = Image.new("RGB", (thumb_width, sheet_height), "white")
    cursor = 0
    for image in prepared:
        sheet.paste(image, (0, cursor))
        cursor += image.height
    return sheet


def _data_url(image):
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=82, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _local_pdf_report(template_pdf, output_pdf):
    _, template_pages = _render_pdf_pages(template_pdf, dpi=72, max_pages=1)
    _, output_pages = _render_pdf_pages(output_pdf, dpi=72, max_pages=1)
    issues = []
    if template_pages >= 2 and output_pages != template_pages:
        issues.append(
            f"A paginação mudou de {template_pages} para {output_pages} páginas."
        )
    elif template_pages == 1 and output_pages > 2:
        issues.append(
            f"A paginação cresceu de 1 para {output_pages} páginas, acima da tolerância."
        )
    return FidelityReport(
        passed=not issues,
        score=100 if not issues else 65,
        issues=issues,
        summary=(
            "Paginação compatível."
            if not issues
            else "Paginação incompatível com o modelo."
        ),
        template_pages=template_pages,
        output_pages=output_pages,
    )


def inspect_visual_fidelity(template_pdf, output_pdf):
    """Realiza inspeção visual final, priorizando estrutura e diagramação."""

    local = _local_pdf_report(template_pdf, output_pdf)
    if not getattr(settings, "DOCUMENT_VISUAL_QA_ENABLED", True):
        return local

    try:
        template_images, template_pages = _render_pdf_pages(template_pdf)
        output_images, output_pages = _render_pdf_pages(output_pdf)
        template_sheet = _contact_sheet(template_images, "MODELO")
        output_sheet = _contact_sheet(output_images, "DOCUMENTO GERADO")

        from .document_services import create_openai_client

        client = create_openai_client()
        schema = {
            "type": "object",
            "properties": {
                "passed": {"type": "boolean"},
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "issues": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
            "required": ["passed", "score", "issues", "summary"],
            "additionalProperties": False,
        }
        response = client.responses.create(
            model=getattr(
                settings, "DOCUMENT_VISUAL_QA_MODEL", settings.OPENAI_MODEL
            ),
            store=False,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Compare visualmente um modelo DOCX e o documento personalizado. "
                        "Ignore mudanças esperadas no conteúdo textual. Avalie fidelidade de "
                        "logo, cabeçalho, rodapé, cores, fontes, hierarquia, tabelas, larguras "
                        "de colunas, alinhamentos, espaçamentos, quebras de página e ausência "
                        "de duplicações. Reprove se a estrutura foi reconstruída, se uma seção "
                        "apareceu em células erradas ou se o PDF deixou de reproduzir o DOCX."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Modelo: {template_pages} página(s). Documento: "
                                f"{output_pages} página(s). A primeira imagem contém o "
                                "modelo e a segunda o documento gerado."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": _data_url(template_sheet),
                            "detail": "high",
                        },
                        {
                            "type": "input_image",
                            "image_url": _data_url(output_sheet),
                            "detail": "high",
                        },
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "inspecao_visual_documento",
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        data = json.loads(response.output_text)
        issues = list(local.issues) + list(data.get("issues") or [])
        passed = bool(data.get("passed")) and local.passed
        score = min(int(data.get("score", 0)), local.score)
        return FidelityReport(
            passed=passed,
            score=score,
            issues=issues,
            summary=str(data.get("summary") or local.summary),
            template_pages=template_pages,
            output_pages=output_pages,
        )
    except Exception as exc:
        local.issues.append(
            f"Inspeção visual por IA indisponível: {str(exc)[:180]}"
        )
        local.summary += " A verificação estrutural e de paginação foi mantida."
        return local
