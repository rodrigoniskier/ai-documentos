import json

from django import forms

from .document_models import DOCUMENT_TYPE_CHOICES


DOCUMENT_FIELDS = {
    "EMENTA": ["curso", "disciplina", "carga_horaria", "periodo", "objetivo_geral", "observacoes"],
    "PLANO_ENSINO": [
        "curso",
        "disciplina",
        "carga_horaria",
        "periodo",
        "objetivo_geral",
        "metodologia",
        "avaliacao",
        "bibliografia",
        "observacoes",
    ],
    "CRONOGRAMA": ["curso", "disciplina", "periodo", "datas", "carga_horaria", "atividades", "observacoes"],
    "PLANO_AULA": ["curso", "disciplina", "tema", "duracao", "objetivos", "metodologia", "recursos", "avaliacao"],
    "AVALIACAO": ["curso", "disciplina", "tema", "nivel", "quantidade_itens", "tipo_questoes", "criterios", "observacoes"],
    "RELATORIO": ["curso", "instituicao", "periodo", "objetivo", "resultados", "recomendacoes", "observacoes"],
    "PROJETO": ["curso", "instituicao", "tema", "objetivo", "publico_alvo", "cronograma", "resultados_esperados"],
    "OUTRO": ["curso", "instituicao", "tema", "objetivo", "observacoes"],
}

FIELD_LABELS = {
    "curso": "Curso",
    "disciplina": "Disciplina ou componente curricular",
    "instituicao": "Instituição",
    "carga_horaria": "Carga horária",
    "periodo": "Período",
    "objetivo_geral": "Objetivo geral",
    "objetivos": "Objetivos",
    "metodologia": "Metodologia",
    "avaliacao": "Avaliação",
    "bibliografia": "Bibliografia",
    "observacoes": "Observações",
    "datas": "Datas ou semanas",
    "atividades": "Atividades previstas",
    "tema": "Tema",
    "duracao": "Duração",
    "recursos": "Recursos",
    "nivel": "Nível de dificuldade",
    "quantidade_itens": "Quantidade de itens",
    "tipo_questoes": "Tipos de questões",
    "criterios": "Critérios de avaliação",
    "objetivo": "Objetivo",
    "resultados": "Resultados",
    "recomendacoes": "Recomendações",
    "publico_alvo": "Público-alvo",
    "cronograma": "Cronograma",
    "resultados_esperados": "Resultados esperados",
}


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)] if data else []


class NewDocumentProjectForm(forms.Form):
    document_type = forms.ChoiceField(label="Tipo de documento", choices=DOCUMENT_TYPE_CHOICES)
    title = forms.CharField(label="Título do documento", max_length=220)
    template_title = forms.CharField(label="Nome do modelo", max_length=180, required=False)
    template_file = forms.FileField(
        label="Modelo do documento",
        help_text="Envie DOCX para melhor aproveitamento do layout ou PDF para usar sua estrutura como referência.",
    )
    reference_files = MultipleFileField(
        label="Documentos de referência",
        required=False,
        help_text="Você pode enviar vários arquivos PDF, DOCX ou TXT.",
    )
    course_context = forms.CharField(
        label="Curso ou área",
        max_length=220,
        required=False,
        help_text="Obrigatório quando nenhuma referência for anexada.",
    )
    institution_context = forms.CharField(
        label="Contexto que a IA deve considerar",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Explique instituição, público, período, regras e limitações relevantes.",
    )
    logo = forms.ImageField(label="Logomarca da instituição", required=False)
    extra_fields_json = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_template_file(self):
        uploaded = self.cleaned_data["template_file"]
        extension = uploaded.name.lower().rsplit(".", 1)[-1]
        if extension not in {"docx", "pdf"}:
            raise forms.ValidationError("O modelo deve estar em DOCX ou PDF.")
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError("O modelo deve ter no máximo 10 MB.")
        return uploaded

    def clean_reference_files(self):
        files = self.cleaned_data.get("reference_files") or []
        for uploaded in files:
            extension = uploaded.name.lower().rsplit(".", 1)[-1]
            if extension not in {"docx", "pdf", "txt"}:
                raise forms.ValidationError("As referências devem estar em PDF, DOCX ou TXT.")
            if uploaded.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Cada referência deve ter no máximo 10 MB.")
        return files

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and logo.size > 3 * 1024 * 1024:
            raise forms.ValidationError("A logomarca deve ter no máximo 3 MB.")
        return logo

    def clean_extra_fields_json(self):
        value = self.cleaned_data.get("extra_fields_json") or "{}"
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Os campos personalizados não puderam ser interpretados.") from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Os campos personalizados são inválidos.")
        return {str(key)[:100]: str(item)[:5000] for key, item in parsed.items() if str(item).strip()}

    def clean(self):
        cleaned = super().clean()
        references = cleaned.get("reference_files") or []
        if not references and not (cleaned.get("course_context") and cleaned.get("institution_context")):
            message = (
                "Sem documentos de referência, informe o curso ou área e o contexto. "
                "O resultado será mais limitado e exigirá revisão humana rigorosa."
            )
            if not cleaned.get("course_context"):
                self.add_error("course_context", message)
            if not cleaned.get("institution_context"):
                self.add_error("institution_context", message)
        return cleaned

    @property
    def field_configuration_json(self):
        return json.dumps(
            {key: [{"name": item, "label": FIELD_LABELS[item]} for item in values] for key, values in DOCUMENT_FIELDS.items()},
            ensure_ascii=False,
        )
