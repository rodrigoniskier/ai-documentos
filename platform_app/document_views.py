import io
import uuid
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from .document_forms import NewDocumentProjectForm
from .document_models import DocumentProject, DocumentTemplate, ReferenceDocument
from .document_services import (
    build_project_docx,
    build_project_pdf,
    generate_project_content,
    process_reference,
    process_template,
)
from .models import GeneratedDocument
from .services import refund_credits, reserve_credits


GENERATION_COST = 2


def _upload_count(user):
    return user.document_templates.count() + user.reference_documents.count()


def _safe_filename(value):
    cleaned = "".join(character for character in value if character.isalnum() or character in "-_ ").strip()
    return cleaned[:80] or "documento"


@login_required
def workspace(request):
    projects = request.user.document_projects.all()
    plan = request.user.subscription.plan
    return render(
        request,
        "workspace.html",
        {
            "projects": projects[:6],
            "project_count": projects.count(),
            "template_count": request.user.document_templates.count(),
            "reference_count": request.user.reference_documents.count(),
            "upload_limit": plan.source_limit,
            "upload_count": _upload_count(request.user),
        },
    )


@login_required
def project_new(request):
    form = NewDocumentProjectForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        reference_files = form.cleaned_data["reference_files"]
        required_slots = 1 + len(reference_files)
        if _upload_count(request.user) + required_slots > request.user.subscription.plan.source_limit:
            form.add_error(
                None,
                "O envio ultrapassa o limite de modelos e referências do seu plano.",
            )
        else:
            template_file = form.cleaned_data["template_file"]
            template = DocumentTemplate.objects.create(
                owner=request.user,
                title=form.cleaned_data["template_title"] or Path(template_file.name).stem,
                document_type=form.cleaned_data["document_type"],
                file=template_file,
            )
            process_template(template)
            project = DocumentProject.objects.create(
                owner=request.user,
                template=template,
                document_type=form.cleaned_data["document_type"],
                title=form.cleaned_data["title"],
                course_context=form.cleaned_data["course_context"],
                institution_context=form.cleaned_data["institution_context"],
                field_values=form.cleaned_data["extra_fields_json"],
                logo=form.cleaned_data.get("logo"),
                status="processing",
            )
            for uploaded in reference_files:
                reference = ReferenceDocument.objects.create(
                    owner=request.user,
                    title=Path(uploaded.name).stem,
                    file=uploaded,
                )
                process_reference(reference)
                project.references.add(reference)

            key = str(uuid.uuid4())
            reserved = False
            try:
                reserve_credits(
                    request.user,
                    GENERATION_COST,
                    idempotency_key=f"document-project-reserve:{key}",
                    reference=f"project:{project.pk}",
                )
                reserved = True
                content, input_tokens, output_tokens = generate_project_content(project)
                project.content = content
                project.title = content.get("title") or project.title
                project.input_tokens = input_tokens
                project.output_tokens = output_tokens
                project.status = "ready"
                project.error = ""
                project.save(
                    update_fields=[
                        "content",
                        "title",
                        "input_tokens",
                        "output_tokens",
                        "status",
                        "error",
                        "updated_at",
                    ]
                )
                messages.success(
                    request,
                    "Documento preparado. Revise, edite e acrescente seções antes de exportar.",
                )
                return redirect("project_edit", pk=project.pk)
            except Exception as exc:
                project.status = "failed"
                project.error = str(exc)[:500]
                project.save(update_fields=["status", "error", "updated_at"])
                if reserved:
                    refund_credits(
                        request.user,
                        GENERATION_COST,
                        idempotency_key=f"document-project-refund:{key}",
                        reference=f"project:{project.pk}",
                    )
                messages.error(request, f"Não foi possível gerar o documento: {exc}")
    return render(
        request,
        "document_new.html",
        {
            "form": form,
            "field_configuration_json": form.field_configuration_json,
            "generation_cost": GENERATION_COST,
        },
    )


@login_required
def project_edit(request, pk):
    project = get_object_or_404(DocumentProject, pk=pk, owner=request.user)
    content = project.content if isinstance(project.content, dict) else {}
    if request.method == "POST":
        headings = request.POST.getlist("section_heading")
        bodies = request.POST.getlist("section_body")
        sections = []
        for heading, body in zip(headings, bodies):
            heading = heading.strip()
            body = body.strip()
            if heading or body:
                sections.append({"heading": heading or "Nova seção", "body": body})
        warnings = [item.strip() for item in request.POST.get("warnings", "").splitlines() if item.strip()]
        project.title = request.POST.get("title", project.title).strip() or project.title
        project.content = {
            "title": project.title,
            "warnings": warnings,
            "sections": sections,
        }
        project.status = "ready"
        project.save(update_fields=["title", "content", "status", "updated_at"])
        messages.success(request, "Revisões salvas.")
        return redirect("project_edit", pk=project.pk)
    return render(
        request,
        "document_edit.html",
        {
            "project": project,
            "warnings_text": "\n".join(content.get("warnings", [])),
            "sections": content.get("sections", []),
        },
    )


@login_required
def project_download_docx(request, pk):
    project = get_object_or_404(DocumentProject, pk=pk, owner=request.user, status="ready")
    content = build_project_docx(project, watermark=request.user.subscription.plan.watermark)
    content.seek(0)
    return FileResponse(
        io.BytesIO(content.read()),
        as_attachment=True,
        filename=f"{_safe_filename(project.title)}.docx",
    )


@login_required
def project_download_pdf(request, pk):
    project = get_object_or_404(DocumentProject, pk=pk, owner=request.user, status="ready")
    content = build_project_pdf(project, watermark=request.user.subscription.plan.watermark)
    content.seek(0)
    return FileResponse(
        io.BytesIO(content.read()),
        as_attachment=True,
        filename=f"{_safe_filename(project.title)}.pdf",
    )


@login_required
def project_history(request):
    return render(
        request,
        "document_history_new.html",
        {
            "projects": request.user.document_projects.all(),
            "templates": request.user.document_templates.all(),
            "references": request.user.reference_documents.all(),
            "legacy_documents": GeneratedDocument.objects.filter(owner=request.user),
        },
    )
