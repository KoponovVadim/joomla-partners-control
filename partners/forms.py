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
        help_text="Для Joomla 3. Оставьте пустым, чтобы сохранить текущий пароль.",
    )
    api_token = forms.CharField(
        label="API Token",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Для Joomla 4/5. Токен передаётся только в X-Joomla-Token и хранится "
            "в зашифрованном виде. Оставьте пустым, чтобы сохранить текущий."
        ),
    )

    class Meta:
        model = DonorSite
        fields = [
            "name",
            "domain",
            "admin_url",
            "page_url",
            "joomla_version",
            "auth_mode",
            "username",
            "password",
            "api_url",
            "api_token",
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

    def clean(self):
        cleaned = super().clean()
        version = cleaned.get("joomla_version")
        auth_mode = cleaned.get("auth_mode")

        if version == DonorSite.JoomlaVersion.V3 and auth_mode != DonorSite.AuthMode.PASSWORD:
            self.add_error("auth_mode", "Для Joomla 3 используется вход по логину и паролю.")
        elif version in {DonorSite.JoomlaVersion.V4, DonorSite.JoomlaVersion.V5}:
            if auth_mode != DonorSite.AuthMode.API_TOKEN:
                self.add_error("auth_mode", "Для Joomla 4/5 выберите авторизацию по API Token.")
            if not cleaned.get("api_token") and not self.instance.api_token_is_set:
                self.add_error("api_token", "Укажите API Token пользователя Joomla.")

        return cleaned


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
        fields = [
            "name",
            "domain",
            "logo",
            "description",
            "link_text",
            "default_html",
            "notes",
            "enabled",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "default_html": forms.Textarea(attrs={"rows": 8, "class": "input code-editor"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "default_html": (
                "Расширенный режим для старой или сложной разметки. Если поле заполнено, оно имеет "
                "приоритет над текстовым описанием; JPC оставит в нём одну текстовую ссылку и приведёт "
                "её URL и атрибуты к настройкам клиента."
            )
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
            "description_override",
            "link_text_override",
            "html_override",
            "url_override",
            "image_override",
            "target_blank",
            "nofollow",
            "sponsored",
            "enabled",
        ]
        widgets = {
            "description_override": forms.Textarea(attrs={"rows": 5}),
            "html_override": forms.Textarea(attrs={"rows": 8, "class": "input code-editor"}),
        }
        help_texts = {
            "description_override": (
                "Оставьте пустым, чтобы использовать текстовое описание из карточки клиента."
            ),
            "link_text_override": (
                "Оставьте пустым, чтобы использовать текст ссылки из карточки клиента."
            ),
            "html_override": (
                "Расширенный режим только для этого донора. Имеет приоритет над обычным описанием; "
                "JPC нормализует ссылки до одной текстовой."
            ),
            "image_override": (
                "Оставьте пустым, чтобы автоматически использовать картинку, загруженную в карточке клиента. "
                "Заполняйте только если для этого размещения нужен другой URL картинки."
            ),
        }
