from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("partners", "0004_donor_article_creation_settings")]

    operations = [
        migrations.AlterField(
            model_name="publicationlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("preview", "Предпросмотр"),
                    ("connection_test", "Проверка подключения"),
                    ("publish", "Публикация"),
                    ("create_article", "Создание материала"),
                    ("update_article", "Обновление материала"),
                    ("trash_article", "В корзину"),
                    ("restore_article", "Восстановление"),
                    ("restore_snapshot", "Восстановление snapshot"),
                    ("adopt_article", "Принятие под управление"),
                ],
                max_length=30,
            ),
        ),
    ]
