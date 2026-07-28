from django.db import migrations


def cleanup_failed_uploads(apps, schema_editor):
    DocumentProject = apps.get_model("platform_app", "DocumentProject")
    DocumentTemplate = apps.get_model("platform_app", "DocumentTemplate")
    ReferenceDocument = apps.get_model("platform_app", "ReferenceDocument")
    through = DocumentProject.references.through

    failed_ids = list(
        DocumentProject.objects.filter(status="failed").values_list("id", flat=True)
    )
    if not failed_ids:
        return

    template_ids = list(
        DocumentProject.objects.filter(id__in=failed_ids).values_list(
            "template_id", flat=True
        )
    )
    reference_ids = list(
        through.objects.filter(documentproject_id__in=failed_ids).values_list(
            "referencedocument_id", flat=True
        )
    )

    DocumentProject.objects.filter(id__in=failed_ids).delete()

    used_template_ids = set(
        DocumentProject.objects.filter(template_id__in=template_ids).values_list(
            "template_id", flat=True
        )
    )
    DocumentTemplate.objects.filter(
        id__in=set(template_ids) - used_template_ids
    ).delete()

    used_reference_ids = set(
        through.objects.filter(referencedocument_id__in=reference_ids).values_list(
            "referencedocument_id", flat=True
        )
    )
    ReferenceDocument.objects.filter(
        id__in=set(reference_ids) - used_reference_ids
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("platform_app", "0008_moderate_paid_plan_limits")]
    operations = [
        migrations.RunPython(cleanup_failed_uploads, migrations.RunPython.noop)
    ]
