import io

from PIL import Image
from django.test import TestCase
from django.urls import reverse

from .models import Course, Discipline, GeneratedDocument, Generation, Institution, User
from .services import ensure_plans, provision_free_account


class HealthTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class SeoTests(TestCase):
    def setUp(self):
        ensure_plans()

    def test_home_exposes_canonical_social_and_structured_metadata(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<link rel="canonical"')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, 'name="twitter:card"')
        self.assertContains(response, 'type="application/ld+json"')
        self.assertContains(response, '"@type": "SoftwareApplication"')

    def test_robots_excludes_private_routes_and_points_to_sitemap(self):
        response = self.client.get(reverse("robots"))
        content = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("Allow: /", content)
        self.assertIn(f"Disallow: {reverse('dashboard')}", content)
        self.assertIn(f"Disallow: {reverse('document_history')}", content)
        self.assertIn(f"Sitemap: http://testserver{reverse('sitemap')}", content)

    def test_sitemap_lists_only_public_routes(self):
        response = self.client.get(reverse("sitemap"))
        content = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response["Content-Type"])
        for route in ("home", "pricing", "register", "terms", "privacy"):
            self.assertIn(f"http://testserver{reverse(route)}", content)
        self.assertNotIn(reverse("dashboard"), content)

    def test_social_card_is_a_1200_by_630_png(self):
        response = self.client.get(reverse("social_card"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (1200, 630))


class RegistrationTests(TestCase):
    def test_registration_is_public_and_grants_free_credits_once(self):
        page = self.client.get(reverse("register"))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Código de convite")
        self.assertContains(page, "Termos de Uso")
        self.assertContains(page, "Aviso de Privacidade")

        response = self.client.post(
            reverse("register"),
            {
                "full_name": "Professor Teste",
                "professional_name": "Prof. Teste",
                "email": "PROFESSOR@EXAMPLE.COM",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "accept_terms": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(email="professor@example.com")
        self.assertEqual(user.subscription.plan.code, "FREE")
        self.assertEqual(user.wallet.balance, 5)
        provision_free_account(user)
        user.wallet.refresh_from_db()
        self.assertEqual(user.wallet.balance, 5)

    def test_registration_honors_safe_internal_next_url(self):
        response = self.client.post(
            f"{reverse('register')}?next={reverse('subscription')}",
            {
                "full_name": "Professor Assinante",
                "professional_name": "Prof. Assinante",
                "email": "assinante@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "accept_terms": "on",
                "next": reverse("subscription"),
            },
        )
        self.assertRedirects(response, reverse("subscription"))


class CommercialPagesTests(TestCase):
    def setUp(self):
        ensure_plans()

    def test_home_has_no_restricted_release_language(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8").lower()
        self.assertEqual(response.status_code, 200)
        for forbidden in ("beta", "código de convite", "acesso fundador"):
            self.assertNotIn(forbidden, content)
        self.assertIn("começar com 5 créditos grátis", content)
        self.assertIn("cada geração consome 2 créditos", content)

    def test_pricing_is_commercial_and_direct(self):
        response = self.client.get(reverse("pricing"))
        content = response.content.decode("utf-8").lower()
        self.assertEqual(response.status_code, 200)
        for forbidden in (
            "beta",
            "fundador",
            "solicitar acesso",
            "registrar interesse",
        ):
            self.assertNotIn(forbidden, content)
        self.assertContains(response, "R$ 19,90/mês")
        self.assertContains(response, "R$ 49,90/mês")
        self.assertContains(response, "Pro")
        self.assertContains(response, "Ultra")
        self.assertIn("assinar", content)
        self.assertIn("1 plano de ensino = 2 créditos", content)
        self.assertIn("sem cartão e sem cobrança automática", content)

    def test_legal_pages_are_commercial(self):
        for route in ("terms", "privacy"):
            response = self.client.get(reverse(route))
            content = response.content.decode("utf-8").lower()
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("beta", content)
            self.assertIn("25 de julho de 2026", content)


class ProductExperienceTests(TestCase):
    def setUp(self):
        ensure_plans()
        self.user = User.objects.create_user(
            email="experiencia@example.com",
            password="SenhaForte123!",
            full_name="Professora Experiência",
            professional_name="Profa. Experiência",
        )
        provision_free_account(self.user)
        self.client.force_login(self.user)

    def test_dashboard_has_actionable_onboarding(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prepare sua primeira geração")
        self.assertContains(response, "0%")
        self.assertContains(response, "Cadastrar instituição")
        self.assertContains(response, "Adicionar uma fonte")
        self.assertContains(response, "(opcional)")

    def test_generation_page_has_visible_waiting_state_and_double_submit_guard(self):
        response = self.client.get(reverse("generate_document"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="generation-form"')
        self.assertContains(response, 'id="generation-status"')
        self.assertContains(response, "Gerando seu Plano de Ensino")
        self.assertContains(response, "Não feche nem atualize esta página")
        self.assertContains(response, "submitted = true")

    def test_document_detail_renders_academic_sections_instead_of_raw_json(self):
        institution = Institution.objects.create(
            owner=self.user,
            name="Universidade Exemplo",
        )
        course = Course.objects.create(
            owner=self.user,
            institution=institution,
            name="Medicina",
        )
        discipline = Discipline.objects.create(
            owner=self.user,
            institution=institution,
            course=course,
            name="Imunologia",
            syllabus="Ementa de teste",
        )
        generation = Generation.objects.create(
            owner=self.user,
            discipline=discipline,
            idempotency_key="experience-generation",
            status="completed",
        )
        document = GeneratedDocument.objects.create(
            owner=self.user,
            generation=generation,
            code="RND-EXPERIENCIA-001",
            title="Plano de Ensino — Imunologia",
            content={
                "ementa": "Fundamentos da resposta imune.",
                "objetivo_geral": "Integrar mecanismos imunológicos.",
                "objetivos_especificos": ["Explicar imunidade inata."],
                "competencias": ["Interpretar situações clínicas."],
                "conteudo": [
                    {
                        "unidade": "Imunidade inata",
                        "topicos": ["Reconhecimento de padrões"],
                        "carga": "8 horas",
                    }
                ],
                "metodologia": ["Aulas dialogadas."],
                "avaliacao": ["Estudo de caso."],
                "recursos": ["Ambiente virtual."],
                "bibliografia_basica": ["Referência básica."],
                "bibliografia_complementar": ["Referência complementar."],
                "observacoes": "Revisão docente obrigatória.",
            },
            file="generated/experiencia.docx",
        )
        response = self.client.get(reverse("document_detail", args=[document.pk]))
        content = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<pre", content)
        self.assertContains(response, "Conteúdo programático")
        self.assertContains(response, "Imunidade inata")
        self.assertContains(response, "Reconhecimento de padrões")
        self.assertContains(response, "Baixar DOCX")
        self.assertContains(response, "Documento pronto para revisão")


class ObjectIsolationTests(TestCase):
    def setUp(self):
        ensure_plans()
        self.user_a = User.objects.create_user(
            email="a@example.com",
            password="SenhaForte123!",
            full_name="Professor A",
            professional_name="Prof. A",
        )
        self.user_b = User.objects.create_user(
            email="b@example.com",
            password="SenhaForte123!",
            full_name="Professor B",
            professional_name="Prof. B",
        )
        provision_free_account(self.user_a)
        provision_free_account(self.user_b)
        institution = Institution.objects.create(owner=self.user_a, name="Instituição A")
        course = Course.objects.create(
            owner=self.user_a,
            institution=institution,
            name="Curso A",
        )
        discipline = Discipline.objects.create(
            owner=self.user_a,
            institution=institution,
            course=course,
            name="Disciplina A",
            syllabus="Ementa de teste",
        )
        generation = Generation.objects.create(
            owner=self.user_a,
            discipline=discipline,
            idempotency_key="test-generation",
            status="completed",
        )
        self.document = GeneratedDocument.objects.create(
            owner=self.user_a,
            generation=generation,
            code="RND-TESTE-001",
            title="Documento privado",
            content={"ementa": "Teste"},
            file="generated/teste.docx",
        )

    def test_user_cannot_open_another_users_document(self):
        self.client.force_login(self.user_b)
        response = self.client.get(reverse("document_detail", args=[self.document.pk]))
        self.assertEqual(response.status_code, 404)
