from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0006_structured_partner_copy"),
    ]

    operations = [
        migrations.AddField(
            model_name="donorsite",
            name="auth_mode",
            field=models.CharField(
                choices=[
                    ("password", "Логин и пароль (Joomla 3)"),
                    ("api_token", "API Token (Joomla 4/5)"),
                ],
                default="password",
                max_length=20,
                verbose_name="Способ авторизации",
            ),
        ),
        migrations.AddField(
            model_name="donorsite",
            name="api_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text=(
                    "Необязательно. По умолчанию JPC вычисляет /api/index.php/v1 "
                    "из Admin URL."
                ),
                max_length=500,
                verbose_name="API URL",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="donorsite",
            name="encrypted_api_token",
            field=models.TextField(blank=True, default="", editable=False),
            preserve_default=False,
        ),
    ]
