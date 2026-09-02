from django.core.management.base import BaseCommand
from partners.models import ClientSite, DonorSite, PageTemplate, Placement

DEFAULT_CSS = """ul.partners { list-style: none; margin: 0; padding: 0; }
ul.partners > li { display: flex; gap: 24px; padding: 24px 0; border-bottom: 1px solid #ddd; }
ul.partners .Img { width: 180px; flex: 0 0 180px; }
ul.partners .Img img { max-width: 100%; height: auto; }
ul.partners .txt { flex: 1; }
ul.partners h3 { margin-top: 0; }
ul.partners h3 span { display: block; font-size: .75em; font-weight: normal; }
ul.partners .Clear { display: none; }
@media (max-width: 600px) { ul.partners > li { display: block; } ul.partners .Img { width: auto; margin-bottom: 15px; } }"""

class Command(BaseCommand):
    help = "Создаёт или обновляет безопасные демонстрационные данные"
    def handle(self, *args, **options):
        template, _ = PageTemplate.objects.get_or_create(slug="default", defaults={"name": "Партнёры — основной", "css": DEFAULT_CSS})
        donor, _ = DonorSite.objects.get_or_create(domain="timohovskiemexa.ru", defaults={
            "name": "Тимоховские меха", "admin_url": "https://timohovskiemexa.ru/administrator/",
            "page_url": "https://timohovskiemexa.ru/nashi-partnery", "joomla_version": "3",
            "article_id": 123, "menu_item_id": 391, "article_alias": "nashi-partnery", "template": template,
        })
        clients = [
            ("Hydrotact", "hydrotact.ru", "<h3>Hydrotact <span>современные решения</span></h3><p>Информация о компании <a href=\"https://hydrotact.ru/\">Hydrotact</a>.</p>"),
            ("Brenda Sport", "brendasport.ru", "<h3>Спортивные товары BRENDA <span>продажа очков и масок</span></h3><p>Компания-производитель спортивных товаров. <a href=\"https://brendasport.ru/\">Спортивные очки</a>.</p>"),
            ("Elpark Plaza", "elparkplaza.ru", "<h3>Elpark Plaza</h3><p>Информация о компании <a href=\"https://elparkplaza.ru/\">Elpark Plaza</a>.</p>"),
            ("TCM Russia", "tcm-russia.ru", "<h3>TCM Russia</h3><p>Информация о компании <a href=\"https://tcm-russia.ru/\">TCM Russia</a>.</p>"),
        ]
        for position, (name, domain, html) in enumerate(clients, start=1):
            client, _ = ClientSite.objects.get_or_create(domain=domain, defaults={"name": name, "default_html": html})
            Placement.objects.get_or_create(donor=donor, client=client, defaults={"position": position})
        self.stdout.write(self.style.SUCCESS("Demo-данные готовы (команда идемпотентна, credentials не создавались)."))

