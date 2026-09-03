from django.contrib import admin
from .models import (
    ArticleSnapshot,
    ClientDescriptionVariant,
    ClientSite,
    DonorSite,
    PageTemplate,
    Placement,
    PublicationLog,
)


class PlacementInline(admin.TabularInline):
    model = Placement
    extra = 0


class ClientDescriptionVariantInline(admin.StackedInline):
    model = ClientDescriptionVariant
    extra = 1
    fields = ("name", "html", "enabled", "position")


@admin.register(DonorSite)
class DonorAdmin(admin.ModelAdmin):
    list_display = ("domain", "joomla_version", "page_http_status", "page_checked_at", "enabled")
    list_filter = ("joomla_version", "page_http_status", "enabled")
    search_fields = ("name", "domain")
    exclude = ("encrypted_password", "encrypted_api_token", "encrypted_connector_token")
    inlines = [PlacementInline]


@admin.register(ClientSite)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "enabled")
    search_fields = ("name", "domain")
    inlines = [ClientDescriptionVariantInline]


admin.site.register(PageTemplate)
admin.site.register(Placement)
admin.site.register(PublicationLog)
admin.site.register(ArticleSnapshot)
