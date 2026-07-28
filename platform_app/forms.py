from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Course, Discipline, Institution, Source, User
from .services import provision_free_account


class RegistrationForm(UserCreationForm):
    accept_terms = forms.BooleanField(
        label="Li e aceito os Termos de Uso e o Aviso de Privacidade"
    )

    class Meta:
        model = User
        fields = ["full_name", "professional_name", "email"]

    def clean_email(self):
        return User.objects.normalize_email(self.cleaned_data["email"]).lower()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            provision_free_account(user)
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="E-mail")


class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ["name", "acronym", "logo", "city", "state"]


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["institution", "name", "level"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["institution"].queryset = Institution.objects.filter(owner=user)


class DisciplineForm(forms.ModelForm):
    class Meta:
        model = Discipline
        fields = [
            "institution",
            "course",
            "name",
            "workload",
            "semester",
            "syllabus",
            "objectives",
            "bibliography",
        ]
        widgets = {
            "syllabus": forms.Textarea(attrs={"rows": 4}),
            "objectives": forms.Textarea(attrs={"rows": 3}),
            "bibliography": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["institution"].queryset = Institution.objects.filter(owner=user)
        self.fields["course"].queryset = Course.objects.filter(owner=user)

    def clean(self):
        cleaned = super().clean()
        institution = cleaned.get("institution")
        course = cleaned.get("course")
        if institution and course and course.institution_id != institution.id:
            self.add_error("course", "O curso não pertence à instituição escolhida.")
        return cleaned


class SourceForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = ["institution", "discipline", "title", "kind", "file"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["institution"].queryset = Institution.objects.filter(owner=user)
        self.fields["discipline"].queryset = Discipline.objects.filter(owner=user)

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        extension = uploaded.name.lower().rsplit(".", 1)[-1]
        if uploaded.size > 5 * 1024 * 1024:
            raise forms.ValidationError("O arquivo deve ter no máximo 5 MB.")
        if extension not in {"pdf", "docx"}:
            raise forms.ValidationError("Envie somente um arquivo PDF ou DOCX.")
        return uploaded

    def clean(self):
        cleaned = super().clean()
        institution = cleaned.get("institution")
        discipline = cleaned.get("discipline")
        if discipline and institution and discipline.institution_id != institution.id:
            self.add_error(
                "discipline", "A disciplina não pertence à instituição escolhida."
            )
        return cleaned


class GenerationForm(forms.Form):
    discipline = forms.ModelChoiceField(
        queryset=Discipline.objects.none(), label="Disciplina"
    )
    period = forms.CharField(label="Período letivo", max_length=80)
    weeks = forms.IntegerField(
        label="Número de semanas", min_value=1, max_value=30, initial=20
    )
    methodology = forms.CharField(
        label="Preferências metodológicas",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    assessment = forms.CharField(
        label="Estratégia de avaliação",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    sources = forms.ModelMultipleChoiceField(
        queryset=Source.objects.none(),
        label="Fontes de referência",
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    notes = forms.CharField(
        label="Observações adicionais",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["discipline"].queryset = Discipline.objects.filter(owner=user)
        self.fields["sources"].queryset = Source.objects.filter(
            owner=user, status="done"
        )
