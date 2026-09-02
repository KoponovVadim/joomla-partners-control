import uuid
from django.db import models
from django.urls import reverse


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PageTemplate(TimeStampedModel):
    name = models.CharField("Название", max_length=150)
    slug = models.SlugField(unique=True)
    wrapper_html = models.TextField(default='<ul class="partners">\n{{ items }}\n</ul>')
    item_html = models.TextField(default='<li>\n <div class="Img"><a href="{{ url }}"{{ link_attributes }}><img src="{{ image }}" alt="{{ client_name }}"></a></div>\n <div class="txt">{{ client_html }}</div>\n <div class="Clear"></div>\n</li>')
    css = models.TextField(blank=True)
    include_css_in_article = models.BooleanField("Добавлять CSS в материал", default=False)
    enabled = models.BooleanField("Активен", default=True)
    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name


class DonorSite(TimeStampedModel):
    class JoomlaVersion(models.TextChoices):
        UNKNOWN = "unknown", "Неизвестна"
        V3 = "3", "Joomla 3"
        V4 = "4", "Joomla 4"
        V5 = "5", "Joomla 5"

    class ConnectionStatus(models.TextChoices):
        UNKNOWN = "unknown", "Не проверено"
        ONLINE = "online", "Online"
        ERROR = "error", "Ошибка"
        NOT_IMPLEMENTED = "not_implemented", "Не реализовано"

    name = models.CharField("Название", max_length=200)
    domain = models.CharField("Домен", max_length=253, unique=True)
    admin_url = models.URLField("Admin URL", max_length=500)
    page_url = models.URLField("URL страницы партнёров", max_length=500)
    joomla_version = models.CharField(
        "Версия Joomla",
        max_length=10,
        choices=JoomlaVersion.choices,
        default=JoomlaVersion.UNKNOWN,
    )
    username = models.CharField("Логин", max_length=150, blank=True)
    encrypted_password = models.TextField(blank=True, editable=False)
    article_id = models.PositiveIntegerField("ID материала", null=True, blank=True)
    article_title = models.CharField("Заголовок материала", max_length=255, default="Наши партнёры")
    article_category_id = models.PositiveIntegerField("ID категории материала", default=2)
    menu_item_id = models.PositiveIntegerField("ID пункта меню", null=True, blank=True)
    article_alias = models.SlugField("Alias", max_length=255, blank=True)
    template = models.ForeignKey(
        PageTemplate,
        verbose_name="Шаблон",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    enabled = models.BooleanField("Активен", default=True)
    connection_status = models.CharField(
        max_length=30,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.UNKNOWN,
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_published_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField("Заметки", blank=True)
    managed_marker_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ["domain"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("donor-edit", args=[self.pk])

    @property
    def password_is_set(self):
        return bool(self.encrypted_password)


class ClientSite(TimeStampedModel):
    name = models.CharField("Название", max_length=200)
    domain = models.CharField("Домен / URL", max_length=500, unique=True)
    logo = models.ImageField("Логотип", upload_to="client_logos/", blank=True)
    default_html = models.TextField("HTML", blank=True)
    enabled = models.BooleanField("Активен", default=True)
    notes = models.TextField("Заметки", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("client-edit", args=[self.pk])


class Placement(TimeStampedModel):
    donor = models.ForeignKey(DonorSite, related_name="placements", on_delete=models.CASCADE)
    client = models.ForeignKey(ClientSite, related_name="placements", on_delete=models.PROTECT)
    position = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    html_override = models.TextField(blank=True)
    url_override = models.URLField(max_length=500, blank=True)
    image_override = models.URLField(max_length=500, blank=True)
    target_blank = models.BooleanField(default=False)
    nofollow = models.BooleanField(default=False)
    sponsored = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["donor", "client"], name="unique_donor_client")]

    def __str__(self):
        return f"{self.client} → {self.donor}"


class PublicationLog(models.Model):
    class Action(models.TextChoices):
        PREVIEW = "preview", "Предпросмотр"
        CONNECTION_TEST = "connection_test", "Проверка подключения"
        PUBLISH = "publish", "Публикация"
        CREATE_ARTICLE = "create_article", "Создание материала"
        UPDATE_ARTICLE = "update_article", "Обновление материала"
        TRASH_ARTICLE = "trash_article", "В корзину"
        RESTORE_ARTICLE = "restore_article", "Восстановление"
        ADOPT_ARTICLE = "adopt_article", "Принятие под управление"

    class Status(models.TextChoices):
        SUCCESS = "success", "Успешно"
        ERROR = "error", "Ошибка"
        NOT_IMPLEMENTED = "not_implemented", "Не реализовано"

    donor = models.ForeignKey(DonorSite, related_name="publication_logs", on_delete=models.CASCADE)
    action = models.CharField(max_length=30, choices=Action.choices)
    status = models.CharField(max_length=30, choices=Status.choices)
    message = models.TextField(blank=True)
    generated_html_hash = models.CharField(max_length=64, blank=True)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ArticleSnapshot(models.Model):
    donor = models.ForeignKey(DonorSite, related_name="article_snapshots", on_delete=models.CASCADE)
    article_id = models.PositiveIntegerField()
    title = models.CharField(max_length=500, blank=True)
    body_html = models.TextField()
    body_hash = models.CharField(max_length=64)
    reason = models.CharField(max_length=40, default="before_update")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
