from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0007_donor_api_auth"),
    ]

    operations = [
        migrations.AddField(
            model_name="donorsite",
            name="connector_url",
            field=models.URLField(
                blank=True,
                help_text=(
                    "Необязательно. По умолчанию endpoint вычисляется из "
                    "Admin URL и работает через публичный index.php."
                ),
                max_length=500,
                verbose_name="JPC Connector URL",
            ),
        ),
        migrations.AddField(
            model_name="donorsite",
            name="encrypted_connector_token",
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AlterField(
            model_name="donorsite",
            name="auth_mode",
            field=models.CharField(
                choices=[
                    ("password", "Логин и пароль (Joomla 3)"),
                    ("connector_token", "JPC Connector (Joomla 3)"),
                    ("api_token", "API Token (Joomla 4/5)"),
                ],
                default="password",
                max_length=20,
                verbose_name="Способ авторизации",
            ),
        ),
    ]
