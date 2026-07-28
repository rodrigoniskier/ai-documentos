from .template_renderer import (
    _canonical_field,
    _compact_paragraph,
    _metadata_values,
    _project_values,
    _section_values,
    _unique_cells,
    replace_paragraph_text,
)


def fill_exact_adjacent_fields(document, project, *, compact=False):
    """Preenche padrões ``Rótulo | Valor`` sem usar semelhança textual.

    Só há alteração quando a célula de rótulo corresponde exatamente a um campo
    conhecido e a célula seguinte é fisicamente distinta. Cabeçalhos de seção e
    células sem rótulo permanecem intocados.
    """

    metadata = _metadata_values(_project_values(project), _section_values(project))
    changes = 0
    for table in document.tables:
        for row in table.rows:
            cells = _unique_cells(row)
            for index, label_cell in enumerate(cells[:-1]):
                label_text = label_cell.text.strip()
                if not label_text or ":" in label_text or "\n" in label_text:
                    continue
                canonical = _canonical_field(label_text)
                if not canonical or canonical not in metadata:
                    continue
                target = cells[index + 1]
                if target._tc is label_cell._tc:
                    continue
                paragraphs = list(target.paragraphs)
                paragraph = next(
                    (item for item in paragraphs if item.text.strip()),
                    paragraphs[0] if paragraphs else target.add_paragraph(),
                )
                changes += int(replace_paragraph_text(paragraph, metadata[canonical]))
                if compact:
                    _compact_paragraph(paragraph)
    return changes
