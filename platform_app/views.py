import io
import uuid

from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import patch_cache_control
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import cache_page

from .forms import (
    CourseForm,
    DisciplineForm,
    EmailAuthenticationForm,
    GenerationForm,
    InstitutionForm,
    RegistrationForm,
    SourceForm,
)
from .models import GeneratedDocument, Generation, Plan
from .services import (
    build_plan_docx,
    extract_source_text,
    generate_plan_with_openai,
    new_document_code,
    refund_credits,
    reserve_credits,
)


DOCUMENT_SECTION_SPECS = (
    ("Ementa", "ementa", "text"),
    ("Objetivo geral", "objetivo_geral", "text"),
    ("Objetivos específicos", "objetivos_especificos", "list"),
    ("Competências e habilidades", "competencias", "list"),
    ("Conteúdo programático", "conteudo", "units"),
    ("Metodologia", "metodologia", "list"),
    ("Avaliação", "avaliacao", "list"),
    ("Recursos", "recursos", "list"),
    ("Bibliografia básica", "bibliografia_basica", "list"),
    ("Bibliografia complementar", "bibliografia_complementar", "list"),
    ("Observações", "observacoes", "text"),
)


def _public_base_url(request) -> str:
    return settings.PUBLIC_BASE_URL or request.build_absolute_uri("/").rstrip("/")


def _document_sections(content):
    content = content if isinstance(content, dict) else {}
    sections = []
    for title, key, kind in DOCUMENT_SECTION_SPECS:
        value = content.get(key)
        if kind == "units":
            units = []
            for unit in value if isinstance(value, list) else []:
                if not isinstance(unit, dict):
                    continue
                unit_title = str(unit.get("unidade") or "Unidade")
                workload = str(unit.get("carga") or "").strip()
                units.append(
                    {
                        "title": unit_title,
                        "workload": workload,
                        "items": [
                            str(item)
                            for item in unit.get("topicos", [])
                            if str(item).strip()
                        ],
                    }
                )
            sections.append({"title": title, "kind": kind, "units": units})
        elif kind == "list":
            items = (
                [str(item) for item in value if str(item).strip()]
                if isinstance(value, list)
                else ([str(value)] if value else [])
            )
            sections.append({"title": title, "kind": kind, "items": items})
        else:
            sections.append(
                {
                    "title": title,
                    "kind": kind,
                    "text": str(value).strip() if value else "—",
                }
            )
    return sections


def home(request):
    return render(
        request,
        "home.html",
        {"plans": Plan.objects.filter(active=True).order_by("display_order")},
    )


def health(request):
    return JsonResponse({"status": "ok"})


def robots(request):
    base_url = _public_base_url(request)
    private_paths = (
        reverse("admin:index"),
        reverse("dashboard"),
        reverse("academics"),
        reverse("document_history"),
        reverse("generate_document"),
        reverse("subscription"),
    )
    lines = ["User-agent: *", "Allow: /"]
    lines.extend(f"Disallow: {path}" for path in private_paths)
    lines.extend(
        [
            f"Sitemap: {base_url}{reverse('sitemap')}",
            "",
        ]
    )
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def sitemap(request):
    route_names = ("home", "pricing", "register", "terms", "privacy")
    base_url = _public_base_url(request)
    urls = [f"{base_url}{reverse(name)}" for name in route_names]
    return render(
        request,
        "sitemap.xml",
        {"urls": urls},
        content_type="application/xml",
    )


def _social_font(size: int, bold: bool = False):
    suffix = "Bold" if bold else ""
    candidates = (
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans-{suffix}.ttf"
        if suffix
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        f"/usr/share/fonts/truetype/liberation2/LiberationSans-{suffix}.ttf"
        if suffix
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


@cache_page(60 * 60 * 24)
def social_card(request):
    image = Image.new("RGB", (1200, 630), "#0B1F3A")
    draw = ImageDraw.Draw(image)
    for x in range(-200, 1400, 110):
        draw.line((x, 0, x + 360, 630), fill="#123154", width=2)

    draw.rounded_rectangle((70, 55, 380, 110), radius=24, fill="#FFC107")
    draw.text(
        (94, 65),
        "RN DocumentAI",
        font=_social_font(30, bold=True),
        fill="#0B1F3A",
    )
    draw.text(
        (68, 164),
        "PLANOS DE ENSINO",
        font=_social_font(63, bold=True),
        fill="#FFFFFF",
    )
    draw.text(
        (68, 244),
        "COM INTELIGÊNCIA",
        font=_social_font(43, bold=True),
        fill="#FFC107",
    )
    draw.text(
        (68, 298),
        "ARTIFICIAL",
        font=_social_font(43, bold=True),
        fill="#FFC107",
    )
    draw.rounded_rectangle((70, 382, 588, 452), radius=32, fill="#FFFFFF")
    draw.text(
        (101, 400),
        "5 CRÉDITOS GRATUITOS",
        font=_social_font(30, bold=True),
        fill="#0B1F3A",
    )
    draw.text(
        (72, 498),
        "Contexto acadêmico · DOCX editável",
        font=_social_font(23),
        fill="#DCE7F3",
    )
    draw.text(
        (72, 532),
        "Revisão docente obrigatória",
        font=_social_font(23),
        fill="#DCE7F3",
    )

    draw.rounded_rectangle((760, 80, 1115, 550), radius=30, fill="#FFFFFF")
    draw.rounded_rectangle((800, 130, 1075, 445), radius=20, fill="#F4F6F9")
    draw.text(
        (833, 170),
        "PLANO DE ENSINO",
        font=_social_font(25, bold=True),
        fill="#0B1F3A",
    )
    draw.rectangle((834, 220, 1040, 232), fill="#2E74B5")
    for index, width in enumerate((200, 182, 216, 174, 198)):
        y = 270 + index * 34
        draw.rounded_rectangle(
            (834, y, 834 + width, y + 11),
            radius=5,
            fill="#C8D3E1",
        )
    draw.rounded_rectangle((833, 470, 1045, 520), radius=22, fill="#FFC107")
    draw.text(
        (880, 480),
        "BAIXAR DOCX",
        font=_social_font(21, bold=True),
        fill="#0B1F3A",
    )

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    response = HttpResponse(output.getvalue(), content_type="image/png")
    patch_cache_control(response, public=True, max_age=86400, immutable=True)
    return response


def _safe_next_url(request) -> str:
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return ""


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    next_url = _safe_next_url(request)
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(
            request, "Conta criada. Seus cinco créditos gratuitos estão disponíveis."
        )
        return redirect(next_url or "dashboard")
    return render(
        request,
        "form.html",
        {"form": form, "title": "Criar conta", "next": next_url},
    )


class SignInView(LoginView):
    template_name = "form.html"
    authentication_form = EmailAuthenticationForm
    extra_context = {"title": "Entrar"}


class SignOutView(LogoutView):
    pass


@login_required
def dashboard(request):
    documents = request.user.documents.all()
    onboarding_steps = [
        {
            "label": "Cadastrar instituição",
            "description": "Identifique a instituição e, se desejar, envie a logomarca.",
            "done": request.user.institutions.exists(),
            "url": reverse("institution_create"),
        },
        {
            "label": "Cadastrar curso",
            "description": "Associe o curso à instituição cadastrada.",
            "done": request.user.courses.exists(),
            "url": reverse("course_create"),
        },
        {
            "label": "Cadastrar disciplina",
            "description": "Informe ementa, carga horária, objetivos e bibliografia.",
            "done": request.user.disciplines.exists(),
            "url": reverse("discipline_create"),
        },
        {
            "label": "Adicionar uma fonte",
            "description": "Envie uma referência acadêmica em PDF ou DOCX, se precisar.",
            "done": request.user.sources.filter(status="done").exists(),
            "url": reverse("source_create"),
            "optional": True,
        },
        {
            "label": "Gerar o primeiro plano",
            "description": "Configure a oferta e gere o DOCX para revisão.",
            "done": documents.exists(),
            "url": reverse("generate_document"),
        },
    ]
    required_steps = [step for step in onboarding_steps if not step.get("optional")]
    completed_steps = sum(step["done"] for step in required_steps)
    onboarding_percent = round((completed_steps / len(required_steps)) * 100)
    return render(
        request,
        "dashboard.html",
        {
            "documents": documents[:5],
            "onboarding_steps": onboarding_steps,
            "onboarding_percent": onboarding_percent,
            "onboarding_complete": completed_steps == len(required_steps),
        },
    )


@login_required
def academics(request):
    return render(
        request,
        "academics.html",
        {
            "institutions": request.user.institutions.all(),
            "courses": request.user.courses.all(),
            "disciplines": request.user.disciplines.all(),
        },
    )


@login_required
def institution_create(request):
    if (
        request.user.institutions.count()
        >= request.user.subscription.plan.institution_limit
    ):
        messages.error(request, "Você atingiu o limite de instituições do seu plano.")
        return redirect("academics")

    form = InstitutionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        institution = form.save(commit=False)
        institution.owner = request.user
        institution.save()
        messages.success(request, "Instituição cadastrada.")
        return redirect("academics")
    return render(
        request, "form.html", {"form": form, "title": "Nova instituição"}
    )


@login_required
def course_create(request):
    form = CourseForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.owner = request.user
        course.save()
        messages.success(request, "Curso cadastrado.")
        return redirect("academics")
    return render(request, "form.html", {"form": form, "title": "Novo curso"})


@login_required
def discipline_create(request):
    if (
        request.user.disciplines.count()
        >= request.user.subscription.plan.discipline_limit
    ):
        messages.error(request, "Você atingiu o limite de disciplinas do seu plano.")
        return redirect("academics")

    form = DisciplineForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        discipline = form.save(commit=False)
        discipline.owner = request.user
        discipline.save()
        messages.success(request, "Disciplina cadastrada.")
        return redirect("academics")
    return render(
        request, "form.html", {"form": form, "title": "Nova disciplina"}
    )


@login_required
def source_create(request):
    if request.user.sources.count() >= request.user.subscription.plan.source_limit:
        messages.error(request, "Você atingiu o limite de fontes do seu plano.")
        return redirect("document_history")

    form = SourceForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        source = form.save(commit=False)
        source.owner = request.user
        source.save()
        extract_source_text(source)
        messages.success(request, "Fonte enviada e processada.")
        return redirect("generate_document")
    return render(request, "form.html", {"form": form, "title": "Enviar fonte"})


@login_required
def generate_document(request):
    form = GenerationForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        discipline = form.cleaned_data["discipline"]
        key = str(uuid.uuid4())
        generation = Generation.objects.create(
            owner=request.user,
            discipline=discipline,
            idempotency_key=key,
        )
        reserved = False
        try:
            reserve_credits(
                request.user,
                2,
                idempotency_key=f"reserve:{key}",
                reference=str(generation.pk),
            )
            reserved = True
            payload = {
                "instituicao": discipline.institution.name,
                "curso": discipline.course.name,
                "disciplina": discipline.name,
                "carga_horaria": discipline.workload,
                "periodo": form.cleaned_data["period"],
                "semanas": form.cleaned_data["weeks"],
                "ementa": discipline.syllabus,
                "objetivos": discipline.objectives,
                "bibliografia": discipline.bibliography,
                "preferencias_metodologicas": form.cleaned_data["methodology"],
                "estrategia_avaliativa": form.cleaned_data["assessment"],
                "observacoes": form.cleaned_data["notes"],
                "fontes": [
                    {"titulo": source.title, "texto": source.extracted_text[:30000]}
                    for source in form.cleaned_data["sources"]
                ],
            }
            data, input_tokens, output_tokens = generate_plan_with_openai(payload)
            code = new_document_code()
            document = GeneratedDocument.objects.create(
                owner=request.user,
                generation=generation,
                code=code,
                title=f"Plano de Ensino — {discipline.name}",
                content=data,
            )
            file_content = build_plan_docx(
                document,
                discipline,
                data,
                watermark=request.user.subscription.plan.watermark,
            )
            document.file.save(f"{code}.docx", file_content, save=True)
            generation.status = "completed"
            generation.output = data
            generation.input_tokens = input_tokens
            generation.output_tokens = output_tokens
            generation.save(
                update_fields=[
                    "status",
                    "output",
                    "input_tokens",
                    "output_tokens",
                ]
            )
            messages.success(request, "Plano de ensino gerado com sucesso.")
            return redirect("document_detail", pk=document.pk)
        except Exception as exc:
            generation.status = "failed"
            generation.error = str(exc)[:500]
            generation.save(update_fields=["status", "error"])
            if reserved:
                refund_credits(
                    request.user,
                    2,
                    idempotency_key=f"refund:{key}",
                    reference=str(generation.pk),
                )
            messages.error(request, f"Não foi possível gerar o documento: {exc}")

    return render(request, "generate.html", {"form": form})


@login_required
def document_history(request):
    return render(
        request,
        "history.html",
        {
            "documents": request.user.documents.all(),
            "sources": request.user.sources.all(),
        },
    )


@login_required
def document_detail(request, pk):
    document = get_object_or_404(
        GeneratedDocument,
        pk=pk,
        owner=request.user,
    )
    return render(
        request,
        "detail.html",
        {
            "document": document,
            "document_sections": _document_sections(document.content),
        },
    )


@login_required
def document_download(request, pk):
    document = get_object_or_404(
        GeneratedDocument,
        pk=pk,
        owner=request.user,
    )
    if document.file.url.startswith("http"):
        return HttpResponseRedirect(document.file.url)
    document.file.open("rb")
    return FileResponse(
        document.file,
        as_attachment=True,
        filename=f"{document.code}.docx",
    )


def pricing(request):
    return render(
        request,
        "pricing.html",
        {"plans": Plan.objects.filter(active=True).order_by("display_order")},
    )


def legal(request, kind):
    return render(request, "legal.html", {"kind": kind})
