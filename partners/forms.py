from django import forms

from .models import ClientSite, DonorSite, PageTemplate, Placement


MAX_LOGO_SIZE = 8 * 1024 * 1024


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.FileInput)):
                field.widget.attrs.setdefault("class", "input")


class DonorForm(StyledModelForm):
    password = forms.CharField(
        label="Пароль",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Оставьте пустым, чтобы сохранить текущий пароль.",
    )

    class Meta:
        model = DonorSite
        fields = [
            "name",
            "domain",
            "admin_url",
            "page_url",
            "joomla_version",
            "username",
            "password",
            "article_id",
            "article_title",
            "article_category_id",
            "menu_item_id",
            "article_alias",
            "template",
            "enabled",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class ClientForm(StyledModelForm):
    logo = forms.ImageField(
        label="Картинка / логотип",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp,image/gif",
                "data-logo-input": "1",
            }
        ),
        help_text=(
            "Загрузите JPG, PNG, WebP или GIF до 8 МБ. После сохранения JPC сам подставит "
            "абсолютный URL этой картинки в <img src> при формировании статьи."
        ),
    )

    class Meta:
        model = ClientSite
        fields = ["name", "domain", "logo", "default_html", "notes", "enabled"]
        widgets = {
            "default_html": forms.Textarea(attrs={"rows": 14, "class": "input code-editor"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and getattr(logo, "size", 0) > MAX_LOGO_SIZE:
            raise forms.ValidationError("Картинка слишком большая. Максимальный размер — 8 МБ.")
        return logo


class PageTemplateForm(StyledModelForm):
    class Meta:
        model = PageTemplate
        fields = [
            "name",
            "slug",
            "wrapper_html",
            "item_html",
            "css",
            "include_css_in_article",
            "enabled",
            "version",
        ]
        widgets = {
            "wrapper_html": forms.Textarea(attrs={"rows": 7, "class": "input code-editor"}),
            "item_html": forms.Textarea(attrs={"rows": 12, "class": "input code-editor"}),
            "css": forms.Textarea(attrs={"rows": 12, "class": "input code-editor"}),
        }


class PlacementForm(StyledModelForm):
    class Meta:
        model = Placement
        fields = [
            "html_override",
            "url_override",
            "image_override",
            "target_blank",
            "nofollow",
            "sponsored",
            "enabled",
        ]
        widgets = {"html_override": forms.Textarea(attrs={"rows": 12, "class": "input code-editor"})}
        help_texts = {
            "image_override": (
                "Оставьте пустым, чтобы автоматически использовать картинку, загруженную в карточке клиента. "
                "Заполняйте только если для этого размещения нужен другой URL картинки."
            )
        }
