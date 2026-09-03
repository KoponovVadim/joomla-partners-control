from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0005_publicationlog_restore_snapshot_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientsite",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Обычный текст без HTML. Переносы строк сохраняются.",
                verbose_name="Текстовое описание",
            ),
        ),
        migrations.AddField(
            model_name="clientsite",
            name="link_text",
            field=models.CharField(
                blank=True,
                help_text="Например: «Перейти на сайт». Если не заполнено, используется название клиента.",
                max_length=255,
                verbose_name="Текст ссылки",
            ),
        ),
        migrations.AddField(
            model_name="placement",
            name="description_override",
            field=models.TextField(
                blank=True,
                verbose_name="Описание для этого донора",
            ),
        ),
        migrations.AddField(
            model_name="placement",
            name="link_text_override",
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name="Текст ссылки для этого донора",
            ),
        ),
        migrations.AlterField(
            model_name="clientsite",
            name="default_html",
            field=models.TextField(
                blank=True,
                help_text="Необязательный режим для существующей сложной разметки.",
                verbose_name="Расширенный HTML",
            ),
        ),
        migrations.AlterField(
            model_name="placement",
            name="html_override",
            field=models.TextField(
                blank=True,
                verbose_name="Расширенный HTML для этого донора",
            ),
        ),
    ]
