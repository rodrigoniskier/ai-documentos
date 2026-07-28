import json
import os
import re
from contextlib import contextmanager

from django.conf import settings
from docx import Document
from openai import AuthenticationError, OpenAI
from pypdf import PdfReader

from .template_renderer import inspect_template_layout


DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "resolved_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["label", "value"],
                "additionalProperties": False,
            },
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["heading", "body"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "warnings", "resolved_fields", "sections"],
    "additionalProperties": False,
}


@contextmanager
def _without_implicit_openai_scope():
    """Impede que variáveis antigas vinculem a requisição a outra organização."""

    removed = {}
    for name in ("OPENAI_ORG_ID", "OPENAI_PROJECT_ID"):
        if name in os.environ:
            removed[name] = os.environ.pop(name)
    try:
        yield
    finally:
        os.environ.update(removed)


def create_openai_client():
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("A chave da OpenAI ainda não foi configurada no servidor.")
    with _without_implicit_openai_scope():
        return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=120, max_retries=2)


def _read_docx(file_obj):
    document = Document(file_obj)
    lines = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        seen = set()
        for row in table.rows:
            values = []
            for cell in row.cells:
                identity = id(cell._tc)
                if identity in seen:
                    continue
                seen.add(identity)
                values.append(cell.text.strip())
            if any(values):
                lines.append(" | ".join(values))
    return "\n".join(lines)


def extract_uploaded_text(file_field, max_chars=100_000):
    file_field.open("rb")
    try:
        name = file_field.name.lower()
        if name.endswith(".pdf"):
            text = "\n".join((page.extract_text() or "") for page in PdfReader(file_field).pages)
        elif name.endswith(".docx"):
            text = _read_docx(file_field)
        else:
            text = file_field.read().decode("utf-8", errors="ignore")
        return text[:max_chars]
    finally:
        file_field.close()


def extract_placeholders(text):
    return sorted(
        {
            item.strip()
            for item in re.findall(r"\{\{\s*([^{}]+?)\s*\}\}", text)
            if item.strip()
        }
    )


def process_template(template):
    template.extracted_text = extract_uploaded_text(template.file)
    template.placeholders = extract_placeholders(template.extracted_text)
    template.save(update_fields=["extracted_text", "placeholders"])


def process_reference(reference):
    try:
        reference.extracted_text = extract_uploaded_text(reference.file)
        reference.status = "done"
    except Exception:
        reference.extracted_text = ""
        reference.status = "failed"
    reference.save(update_fields=["extracted_text", "status"])


def _truncate_sources(references, total_limit=120_000):
    result = []
    remaining = total_limit
    for reference in references:
        if remaining <= 0:
            break
        text = (reference.extracted_text or "")[:remaining]
        result.append({"title": reference.title, "text": text})
        remaining -= len(text)
    return result


def generate_project_content(project):
    references = list(project.references.filter(status="done"))
    no_reference_warning = not references
    layout = inspect_template_layout(project.template.file)
    payload = {
        "document_type": project.get_document_type_display(),
        "requested_title": project.title,
        "template_structure": project.template.extracted_text[:60_000],
        "template_placeholders": project.template.placeholders,
        "template_layout": layout,
        "optional_fields": project.field_values,
        "course_context": project.course_context,
        "institution_context": project.institution_context,
        "references": _truncate_sources(references),
        "reference_limitation": (
            "Nenhuma referência foi anexada. Use apenas o contexto informado, declare a limitação e recomende revisão humana rigorosa."
            if no_reference_warning
            else "Use as referências como fonte prioritária e não invente dados ausentes."
        ),
    }
    system_prompt = (
        "Você personaliza documentos acadêmicos dentro do modelo fornecido pelo usuário. "
        "O modelo é uma restrição estrutural, não apenas uma referência textual. Preserve exatamente "
        "os títulos das seções, a ordem, a quantidade de unidades, a função das colunas e a hierarquia "
        "dos blocos descritos em template_layout. Gere cada seção uma única vez e nunca repita o "
        "conteúdo completo em células diferentes. Em resolved_fields, informe os valores finais que "
        "devem substituir rótulos como Curso, Componente, Período, Turno, Modalidade, Semestre, "
        "Professor responsável e cargas horárias. Quando campos opcionais conflitarem com o modelo "
        "ou com referências mais confiáveis, resolva o conflito e registre o valor final; não deixe a "
        "decisão para o renderizador. Em seções com subtítulos, como Cognitivos, Habilidades e Atitudes, "
        "mantenha esses subtítulos em linhas isoladas. Em CONTEÚDO, escreva cada unidade no padrão "
        "'UNIDADE I: Nome | C/H: 15h/a', seguida somente de seus tópicos. Respeite a capacidade "
        "aproximada dos blocos para evitar expansão desnecessária da paginação. Preencha apenas com "
        "informações sustentadas pelos campos ou referências. Não invente normas, datas, bibliografias "
        "ou dados institucionais. Quando faltarem referências, inclua aviso explícito sobre a limitação "
        "e a revisão humana."
    )
    try:
        client = create_openai_client()
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            store=False,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "documento_academico_editavel",
                    "strict": True,
                    "schema": DOCUMENT_SCHEMA,
                }
            },
        )
    except AuthenticationError as exc:
        code = getattr(exc, "code", "") or ""
        if code == "invalid_organization" or "organization" in str(exc).lower():
            raise RuntimeError(
                "A credencial da OpenAI está vinculada a uma organização ou projeto sem acesso. "
                "Remova OPENAI_ORG_ID e OPENAI_PROJECT_ID do Render ou substitua OPENAI_API_KEY por uma chave ativa do projeto correto."
            ) from exc
        raise
    usage = getattr(response, "usage", None)
    return (
        json.loads(response.output_text),
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
    )
