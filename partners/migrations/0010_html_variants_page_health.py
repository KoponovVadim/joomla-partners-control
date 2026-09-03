from django.db import migrations, models


def migrate_legacy_html(apps, schema_editor):
    ClientSite = apps.get_model("partners", "ClientSite")
    ClientDescriptionVariant = apps.get_model("partners", "ClientDescriptionVariant")

    for client in ClientSite.objects.exclude(default_html="").iterator():
        variant = (
            ClientDescriptionVariant.objects.filter(client_id=client.pk)
            .order_by("position", "id")
            .first()
        )
        if variant:
            variant.html = client.default_html
            if not variant.name:
                variant.name = "Основное"
            variant.enabled = True
            variant.save(update_fields=["html", "name", "enabled"])
        else:
            ClientDescriptionVariant.objects.create(
                client_id=client.pk,
                name="Основное",
                html=client.default_html,
                position=1,
                enabled=True,
            )
        client.default_html = ""
        client.save(update_fields=["default_html"])


def restore_legacy_html(apps, schema_editor):
    ClientSite = apps.get_model("partners", "ClientSite")
    ClientDescriptionVariant = apps.get_model("partners", "ClientDescriptionVariant")

    for client in ClientSite.objects.filter(default_html="").iterator():
        variant = (
            ClientDescriptionVariant.objects.filter(client_id=client.pk, enabled=True)
            .order_by("position", "id")
            .first()
        )
        if variant:
            client.default_html = variant.html
            client.save(update_fields=["default_html"])


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0009_client_description_variants"),
    ]

    operations = [
        migrations.RenameField(
            model_name="clientdescriptionvariant",
            old_name="text",
            new_name="html",
        ),
        migrations.AlterField(
            model_name="clientdescriptionvariant",
            name="html",
            field=models.TextField(
                help_text="HTML-фрагмент, который JPC вставляет в текстовую часть карточки партнёра.",
                verbose_name="HTML описания",
            ),
        ),
        migrations.AddField(
            model_name="donorsite",
            name="page_http_status",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="HTTP статус страницы"),
        ),
        migrations.AddField(
            model_name="donorsite",
            name="page_checked_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Страница проверена"),
        ),
        migrations.AddField(
            model_name="donorsite",
            name="page_unhealthy_since",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Ошибка страницы с"),
        ),
        migrations.AddField(
            model_name="donorsite",
            name="page_check_error",
            field=models.TextField(blank=True, verbose_name="Ошибка проверки страницы"),
        ),
        migrations.RunPython(migrate_legacy_html, restore_legacy_html),
    ]
