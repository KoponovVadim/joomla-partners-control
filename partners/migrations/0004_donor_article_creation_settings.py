from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("partners", "0003_article_snapshots")]

    operations = [
        migrations.AddField(
            model_name="donorsite",
            name="article_title",
            field=models.CharField(default="Наши партнёры", max_length=255, verbose_name="Заголовок материала"),
        ),
        migrations.AddField(
            model_name="donorsite",
            name="article_category_id",
            field=models.PositiveIntegerField(default=2, verbose_name="ID категории материала"),
        ),
    ]
