from django.contrib import admin
from .models import ArticleSnapshot, ClientSite, DonorSite, PageTemplate, Placement, PublicationLog

class PlacementInline(admin.TabularInline):
    model = Placement
    extra = 0

@admin.register(DonorSite)
class DonorAdmin(admin.ModelAdmin):
    list_display = ("domain", "joomla_version", "connection_status", "enabled", "last_published_at")
    list_filter = ("joomla_version", "connection_status", "enabled")
    search_fields = ("name", "domain")
    exclude = ("encrypted_password", "encrypted_api_token")
    inlines = [PlacementInline]

@admin.register(ClientSite)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "enabled")
    search_fields = ("name", "domain")

admin.site.register(PageTemplate)
admin.site.register(Placement)
admin.site.register(PublicationLog)
admin.site.register(ArticleSnapshot)
