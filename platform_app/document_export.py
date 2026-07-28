import io

from django.core.files.base import ContentFile
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from .template_renderer import render_project_in_template


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
    else:
        document = Document()
        _append_generated_content(document, project)

    if watermark:
        _add_free_watermark(document)

    output = io.BytesIO()
    document.save(output)
    return ContentFile(output.getvalue())
