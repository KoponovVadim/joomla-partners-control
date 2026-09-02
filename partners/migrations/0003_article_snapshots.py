import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("partners", "0002_default_template")]
    operations = [
        migrations.CreateModel(name="ArticleSnapshot", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("article_id", models.PositiveIntegerField()), ("title", models.CharField(blank=True, max_length=500)),
            ("body_html", models.TextField()), ("body_hash", models.CharField(max_length=64)),
            ("reason", models.CharField(default="before_update", max_length=40)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("donor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="article_snapshots", to="partners.donorsite")),
        ], options={"ordering": ["-created_at"]}),
        migrations.AlterField(model_name="publicationlog", name="action", field=models.CharField(choices=[("preview", "Предпросмотр"), ("connection_test", "Проверка подключения"), ("publish", "Публикация"), ("create_article", "Создание материала"), ("update_article", "Обновление материала"), ("trash_article", "В корзину"), ("restore_article", "Восстановление"), ("adopt_article", "Принятие под управление")], max_length=30)),
    ]
