from django.db import migrations, models
import django.db.models.deletion


def copy_legacy_descriptions(apps, schema_editor):
    ClientSite = apps.get_model("partners", "ClientSite")
    ClientDescriptionVariant = apps.get_model("partners", "ClientDescriptionVariant")

    variants = []
    for client in ClientSite.objects.exclude(description="").iterator():
        variants.append(
            ClientDescriptionVariant(
                client_id=client.pk,
                name="Основное",
                text=client.description,
                position=1,
                enabled=True,
            )
        )
    if variants:
        ClientDescriptionVariant.objects.bulk_create(variants)


def restore_legacy_descriptions(apps, schema_editor):
    ClientSite = apps.get_model("partners", "ClientSite")
    ClientDescriptionVariant = apps.get_model("partners", "ClientDescriptionVariant")

    for client in ClientSite.objects.filter(description="").iterator():
        variant = (
            ClientDescriptionVariant.objects.filter(client_id=client.pk, enabled=True)
            .order_by("position", "id")
            .first()
        )
        if variant:
            client.description = variant.text
            client.save(update_fields=["description"])


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0008_donor_connector_auth"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientDescriptionVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(blank=True, help_text="Например: Основное, Короткое, Нейтральное.", max_length=80, verbose_name="Название варианта")),
                ("text", models.TextField(help_text="Обычный текст без HTML. Переносы строк сохраняются.", verbose_name="Описание")),
                ("position", models.PositiveIntegerField(default=0)),
                ("enabled", models.BooleanField(default=True, verbose_name="Использовать")),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="description_variants", to="partners.clientsite")),
            ],
            options={
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddField(
            model_name="placement",
            name="description_variant",
            field=models.ForeignKey(blank=True, help_text="Пусто — JPC стабильно распределяет варианты по донорам автоматически.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="placements", to="partners.clientdescriptionvariant", verbose_name="Вариант описания"),
        ),
        migrations.AlterField(
            model_name="clientsite",
            name="description",
            field=models.TextField(blank=True, help_text="Legacy fallback. Новые описания редактируются через варианты описания.", verbose_name="Текстовое описание"),
        ),
        migrations.RunPython(copy_legacy_descriptions, restore_legacy_descriptions),
    ]
