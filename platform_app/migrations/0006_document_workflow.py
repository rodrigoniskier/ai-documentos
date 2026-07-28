from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("platform_app", "0005_billing_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("document_type", models.CharField(choices=[("EMENTA", "Ementa"), ("PLANO_ENSINO", "Plano de ensino"), ("CRONOGRAMA", "Cronograma"), ("PLANO_AULA", "Plano de aula"), ("AVALIACAO", "Avaliação"), ("RELATORIO", "Relatório acadêmico"), ("PROJETO", "Projeto acadêmico"), ("OUTRO", "Outro documento")], max_length=30)),
                ("file", models.FileField(upload_to="document_templates/%Y/%m/")),
                ("extracted_text", models.TextField(blank=True)),
                ("placeholders", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="document_templates", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReferenceDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("file", models.FileField(upload_to="reference_documents/%Y/%m/")),
                ("extracted_text", models.TextField(blank=True)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reference_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="DocumentProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_type", models.CharField(choices=[("EMENTA", "Ementa"), ("PLANO_ENSINO", "Plano de ensino"), ("CRONOGRAMA", "Cronograma"), ("PLANO_AULA", "Plano de aula"), ("AVALIACAO", "Avaliação"), ("RELATORIO", "Relatório acadêmico"), ("PROJETO", "Projeto acadêmico"), ("OUTRO", "Outro documento")], max_length=30)),
                ("title", models.CharField(max_length=220)),
                ("course_context", models.CharField(blank=True, max_length=220)),
                ("institution_context", models.TextField(blank=True)),
                ("field_values", models.JSONField(blank=True, default=dict)),
                ("content", models.JSONField(blank=True, default=dict)),
                ("logo", models.ImageField(blank=True, upload_to="project_logos/%Y/%m/")),
                ("status", models.CharField(choices=[("draft", "Rascunho"), ("processing", "Processando"), ("ready", "Pronto para revisão"), ("failed", "Falhou")], default="draft", max_length=20)),
                ("error", models.CharField(blank=True, max_length=500)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="document_projects", to=settings.AUTH_USER_MODEL)),
                ("references", models.ManyToManyField(blank=True, to="platform_app.referencedocument")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="projects", to="platform_app.documenttemplate")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
    ]
