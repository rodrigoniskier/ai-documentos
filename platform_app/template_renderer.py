import io
import re
import unicodedata
from copy import deepcopy

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph


DOCUMENT_LABEL_ALIASES = {
    "titulo": ("titulo", "nome do documento", "documento"),
    "curso": ("curso", "area", "curso ou area"),
    "contexto": ("contexto", "contexto institucional", "instituicao"),
    "tipo_documento": ("tipo", "tipo de documento"),
    "disciplina": ("disciplina", "componente curricular", "unidade curricular"),
    "carga_horaria": ("carga horaria", "carga horaria total", "ch"),
    "periodo": ("periodo", "semestre", "etapa"),
    "objetivo_geral": ("objetivo geral",),
    "objetivos": ("objetivos", "objetivos especificos"),
    "metodologia": ("metodologia", "estrategias metodologicas"),
    "avaliacao": ("avaliacao", "processo avaliativo", "estrategia avaliativa"),
    "bibliografia": ("bibliografia", "referencias", "referencias bibliograficas"),
    "observacoes": ("observacoes", "observacao"),
    "datas": ("datas", "data", "semanas"),
    "atividades": ("atividades", "atividades previstas"),
    "tema": ("tema", "assunto"),
    "duracao": ("duracao", "tempo previsto"),
    "recursos": ("recursos", "recursos didaticos"),
    "nivel": ("nivel", "nivel de dificuldade"),
    "quantidade_itens": ("quantidade de itens", "numero de itens"),
    "tipo_questoes": ("tipos de questoes", "tipo de questoes"),
    "criterios": ("criterios", "criterios de avaliacao"),
    "objetivo": ("objetivo",),
    "resultados": ("resultados",),
    "recomendacoes": ("recomendacoes",),
    "publico_alvo": ("publico alvo",),
    "cronograma": ("cronograma",),
    "resultados_esperados": ("resultados esperados",),
}


def normalize_label(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"^[\s\dIVXLCDM.\-–—()]+", "", value, flags=re.I)
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", value)


def _read_docx(file_field):
    file_field.open("rb")
    try:
        payload = file_field.read()
    finally:
        file_field.close()
    return Document(io.BytesIO(payload))


def _common_prefix_length(left, right):
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def replace_paragraph_text(paragraph, value):
    """Substitui texto preservando estilo do parágrafo e o máximo possível dos runs."""
    new_text = str(value or "")
    old_text = paragraph.text
    if old_text == new_text:
        return False

    runs = paragraph.runs
    if not runs:
        paragraph.add_run(new_text)
        return True

    prefix_length = _common_prefix_length(old_text, new_text)
    if prefix_length == 0:
        runs[0].text = new_text
        for run in runs[1:]:
            run.text = ""
        return True

    cursor = 0
    inserted = False
    for run in runs:
        original = run.text
        end = cursor + len(original)
        if end <= prefix_length:
            cursor = end
            continue
        if cursor < prefix_length:
            keep = prefix_length - cursor
            run.text = original[:keep] + new_text[prefix_length:]
            inserted = True
        elif not inserted:
            run.text = new_text[prefix_length:]
            inserted = True
        else:
            run.text = ""
        cursor = end

    if not inserted:
        runs[-1].text += new_text[prefix_length:]
    return True


def _append_paragraph_after(paragraph, text):
    new_element = OxmlElement("w:p")
    paragraph._p.addnext(new_element)
    new_paragraph = Paragraph(new_element, paragraph._parent)
    try:
        new_paragraph.style = paragraph.style
    except Exception:
        pass
    new_paragraph.add_run(str(text or ""))
    return new_paragraph


def _project_values(project):
    values = {
        normalize_label(key): str(value)
        for key, value in (project.field_values or {}).items()
        if value not in (None, "")
    }
    values.update(
        {
            "titulo": project.content.get("title") or project.title,
            "curso": project.course_context,
            "contexto": project.institution_context,
            "tipo documento": project.get_document_type_display(),
        }
    )
    return {key: value for key, value in values.items() if str(value).strip()}


def _section_values(project):
    result = {}
    for section in (project.content or {}).get("sections", []):
        heading = normalize_label(section.get("heading"))
        body = str(section.get("body") or "").strip()
        if heading and body:
            result[heading] = body
    return result


def _canonical_field(label):
    normalized = normalize_label(label)
    if not normalized:
        return None
    for field, aliases in DOCUMENT_LABEL_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_label(alias)
            if normalized == normalized_alias:
                return normalize_label(field)
            if len(normalized_alias) >= 4 and (
                normalized_alias in normalized or normalized in normalized_alias
            ):
                return normalize_label(field)
    return normalized


def _best_match(label, project_values, section_values):
    normalized = normalize_label(label)
    if not normalized:
        return None

    canonical = _canonical_field(normalized)
    if canonical in project_values:
        return project_values[canonical]
    if normalized in project_values:
        return project_values[normalized]
    if normalized in section_values:
        return section_values[normalized]

    candidates = {**project_values, **section_values}
    best = None
    best_score = 0
    for key, value in candidates.items():
        if len(key) < 3:
            continue
        score = 0
        if key == normalized:
            score = 100
        elif key in normalized:
            score = 80 + min(len(key), 20)
        elif normalized in key:
            score = 65 + min(len(normalized), 20)
        else:
            left = set(key.split())
            right = set(normalized.split())
            overlap = len(left & right)
            if overlap:
                score = overlap * 20
        if score > best_score:
            best_score = score
            best = value
    return best if best_score >= 40 else None


def _heading_match(text, section_values):
    normalized = normalize_label(text)
    if not normalized:
        return None
    if normalized in section_values:
        return normalized
    best = None
    best_score = 0
    for heading in section_values:
        if heading == normalized:
            return heading
        score = 0
        if heading in normalized:
            score = 80 + min(len(heading), 20)
        elif normalized in heading:
            score = 60 + min(len(normalized), 20)
        else:
            overlap = len(set(heading.split()) & set(normalized.split()))
            score = overlap * 20
        if score > best_score:
            best = heading
            best_score = score
    return best if best_score >= 60 else None


def _replace_inline_label(paragraph, project_values, section_values):
    text = paragraph.text.strip()
    if not text or ":" not in text:
        return False
    label, _, current = text.partition(":")
    value = _best_match(label, project_values, section_values)
    if value is None:
        return False
    replacement = f"{label.strip()}: {value}"
    return replace_paragraph_text(paragraph, replacement)


def _replace_cell_content(cell, value):
    paragraphs = list(cell.paragraphs)
    if not paragraphs:
        paragraph = cell.add_paragraph()
        replace_paragraph_text(paragraph, value)
        return 1
    lines = str(value or "").splitlines() or [""]
    replace_paragraph_text(paragraphs[0], lines[0])
    for index, paragraph in enumerate(paragraphs[1:], start=1):
        replace_paragraph_text(paragraph, lines[index] if index < len(lines) else "")
    if len(lines) > len(paragraphs):
        remaining = "\n".join(lines[len(paragraphs) :])
        if remaining:
            paragraphs[-1].add_run(("\n" if paragraphs[-1].text else "") + remaining)
    return 1


def _fill_tables(document, project_values, section_values):
    changes = 0
    for table in document.tables:
        rows = table.rows
        for row_index, row in enumerate(rows):
            cells = row.cells
            for cell in cells:
                for paragraph in cell.paragraphs:
                    changes += int(
                        _replace_inline_label(paragraph, project_values, section_values)
                    )

            for cell_index, cell in enumerate(cells):
                label = cell.text.strip()
                value = _best_match(label, project_values, section_values)
                if value is None:
                    continue

                if cell_index + 1 < len(cells):
                    target = cells[cell_index + 1]
                    if target._tc is not cell._tc:
                        changes += _replace_cell_content(target, value)
                        continue

                if row_index + 1 < len(rows):
                    next_cells = rows[row_index + 1].cells
                    target_index = min(cell_index, len(next_cells) - 1)
                    target = next_cells[target_index]
                    if target._tc is not cell._tc:
                        changes += _replace_cell_content(target, value)

        if len(rows) >= 2:
            header = rows[0]
            first_data = rows[1]
            for index, header_cell in enumerate(header.cells):
                value = _best_match(header_cell.text, project_values, section_values)
                if value is not None and index < len(first_data.cells):
                    changes += _replace_cell_content(first_data.cells[index], value)
    return changes


def _fill_paragraph_sections(document, project_values, section_values, project):
    changes = 0
    paragraphs = list(document.paragraphs)
    heading_positions = []

    for index, paragraph in enumerate(paragraphs):
        if _replace_inline_label(paragraph, project_values, section_values):
            changes += 1
        heading = _heading_match(paragraph.text, section_values)
        if heading:
            heading_positions.append((index, heading))

    for position, (heading_index, heading) in enumerate(heading_positions):
        body = section_values[heading]
        end = (
            heading_positions[position + 1][0]
            if position + 1 < len(heading_positions)
            else len(paragraphs)
        )
        candidates = [
            paragraph
            for paragraph in paragraphs[heading_index + 1 : end]
            if normalize_label(paragraph.text)
        ]
        if not candidates:
            _append_paragraph_after(paragraphs[heading_index], body)
            changes += 1
            continue

        body_lines = body.splitlines() or [body]
        for candidate_index, candidate in enumerate(candidates):
            if candidate_index < len(body_lines) - 1:
                replacement = body_lines[candidate_index]
            elif candidate_index == len(body_lines) - 1:
                replacement = "\n".join(body_lines[candidate_index:])
            else:
                replacement = ""
            changes += int(replace_paragraph_text(candidate, replacement))

    document_type = normalize_label(project.get_document_type_display())
    for paragraph in paragraphs:
        style_name = normalize_label(getattr(paragraph.style, "name", ""))
        paragraph_text = normalize_label(paragraph.text)
        if (
            "title" in style_name
            or "titulo" in style_name
            or (document_type and document_type in paragraph_text)
        ):
            if len(paragraph_text) <= 100:
                changes += int(
                    replace_paragraph_text(
                        paragraph, project.content.get("title") or project.title
                    )
                )
                break
    return changes


def _append_generated_content(document, project):
    document.add_page_break()
    document.add_heading(project.content.get("title") or project.title, level=1)
    for warning in project.content.get("warnings", []):
        paragraph = document.add_paragraph()
        paragraph.add_run(f"Atenção: {warning}").italic = True
    for section in project.content.get("sections", []):
        document.add_heading(section.get("heading") or "Seção", level=2)
        body = str(section.get("body") or "—")
        for line in body.splitlines() or ["—"]:
            document.add_paragraph(line or " ")


def render_project_in_template(project):
    """Preenche o DOCX original sem reconstruir sua estrutura visual."""
    document = _read_docx(project.template.file)
    project_values = _project_values(project)
    section_values = _section_values(project)

    changes = 0
    changes += _fill_tables(document, project_values, section_values)
    changes += _fill_paragraph_sections(
        document, project_values, section_values, project
    )

    if changes == 0:
        _append_generated_content(document, project)

    return document, changes


def clone_paragraph_format(source, target):
    """Utilitário de teste e futuras expansões de blocos dinâmicos."""
    target._p.get_or_add_pPr().clear_content()
    if source._p.pPr is not None:
        target._p.insert(0, deepcopy(source._p.pPr))
