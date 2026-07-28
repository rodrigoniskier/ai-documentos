import io
import re
import unicodedata

from django.core.files.base import ContentFile
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from .template_renderer import render_project_in_template, replace_paragraph_text


def _slug(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


def _template_values(project):
    values = {
        str(key): value
        for key, value in (project.field_values or {}).items()
        if value not in (None, "")
    }
    values.update(
        {
            "titulo": project.content.get("title") or project.title,
            "curso": project.course_context,
            "contexto": project.institution_context,
            "tipo_documento": project.get_document_type_display(),
        }
    )
    full_text = []
    for section in project.content.get("sections", []):
        heading = str(section.get("heading") or "Seção")
        body = str(section.get("body") or "")
        values[_slug(heading)] = body
        full_text.append(f"{heading}\n{body}")
    values["conteudo_gerado"] = "\n\n".join(full_text)
    return values


def _replace_placeholders_in_paragraph(paragraph, values):
    original = paragraph.text
    updated = original
    for key, value in values.items():
        updated = re.sub(
            r"\{\{\s*" + re.escape(str(key)) + r"\s*\}\}",
            str(value),
            updated,
            flags=re.I,
        )
    if updated == original:
        return False
    return replace_paragraph_text(paragraph, updated)


def _replace_placeholders(document, project):
    values = _template_values(project)
    changes = 0
    for paragraph in document.paragraphs:
        changes += int(_replace_placeholders_in_paragraph(paragraph, values))
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    changes += int(
                        _replace_placeholders_in_paragraph(paragraph, values)
                    )
    return changes


def _append_generated_content(document, project):
    styles = document.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(11)
    if project.logo:
        try:
            project.logo.open("rb")
            document.add_picture(project.logo, width=Cm(3))
            document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        finally:
            project.logo.close()
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run(project.content.get("title") or project.title).bold = True
    for warning in project.content.get("warnings", []):
        paragraph = document.add_paragraph()
        paragraph.add_run(f"Atenção: {warning}").italic = True
    for section in project.content.get("sections", []):
        document.add_heading(section.get("heading") or "Seção", level=2)
        body = str(section.get("body") or "—")
        for line in body.splitlines() or ["—"]:
            document.add_paragraph(line or " ")


def _add_free_watermark(document):
    for section in document.sections:
        footer = section.footer
        existing = " ".join(paragraph.text for paragraph in footer.paragraphs)
        if "AjudAI Docente — Plano Gratuito" in existing:
            continue
        paragraph = footer.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run("AjudAI Docente — Plano Gratuito").italic = True


def build_project_docx(project, watermark=False):
    is_docx_template = project.template.file.name.lower().endswith(".docx")
    if is_docx_template:
        document, _ = render_project_in_template(project)
        _replace_placeholders(document, project)
    else:
        document = Document()
        _append_generated_content(document, project)

    if watermark:
        _add_free_watermark(document)

    output = io.BytesIO()
    document.save(output)
    return ContentFile(output.getvalue())
