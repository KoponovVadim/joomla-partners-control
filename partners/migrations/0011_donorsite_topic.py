from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0010_html_variants_page_health"),
    ]

    operations = [
        migrations.AddField(
            model_name="donorsite",
            name="topic",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=120,
                verbose_name="Тематика сайта",
            ),
        ),
    ]
