from django.conf import settings
from django.db import models


DOCUMENT_TYPE_CHOICES = [
    ("EMENTA", "Ementa"),
    ("PLANO_ENSINO", "Plano de ensino"),
    ("CRONOGRAMA", "Cronograma"),
    ("PLANO_AULA", "Plano de aula"),
    ("AVALIACAO", "Avaliação"),
    ("RELATORIO", "Relatório acadêmico"),
    ("PROJETO", "Projeto acadêmico"),
    ("OUTRO", "Outro documento"),
]


class DocumentTemplate(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="document_templates",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=180)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField(upload_to="document_templates/%Y/%m/")
    extracted_text = models.TextField(blank=True)
    placeholders = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ReferenceDocument(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reference_documents",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to="reference_documents/%Y/%m/")
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class DocumentProject(models.Model):
    STATUS_CHOICES = [
        ("draft", "Rascunho"),
        ("processing", "Processando"),
        ("ready", "Pronto para revisão"),
        ("failed", "Falhou"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="document_projects",
        on_delete=models.CASCADE,
    )
    template = models.ForeignKey(
        DocumentTemplate,
        related_name="projects",
        on_delete=models.PROTECT,
    )
    references = models.ManyToManyField(ReferenceDocument, blank=True)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=220)
    course_context = models.CharField(max_length=220, blank=True)
    institution_context = models.TextField(blank=True)
    field_values = models.JSONField(default=dict, blank=True)
    content = models.JSONField(default=dict, blank=True)
    logo = models.ImageField(upload_to="project_logos/%Y/%m/", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    error = models.CharField(max_length=500, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title
