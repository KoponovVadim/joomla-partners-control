import os
import time

from django.core.management.base import BaseCommand

from partners.services.page_health import check_all_donor_pages


class Command(BaseCommand):
    help = "Периодически проверяет HTTP-статус публичных страниц партнёров."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=int(os.getenv("PAGE_CHECK_INTERVAL_SECONDS", "900")),
            help="Интервал между проверками в секундах (по умолчанию 900).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Выполнить одну проверку и завершиться.",
        )

    def handle(self, *args, **options):
        interval = max(60, options["interval"])
        once = options["once"]

        while True:
            results = check_all_donor_pages()
            healthy = sum(1 for _, status, _ in results if status is not None and status < 400)
            self.stdout.write(
                f"Проверено страниц: {len(results)}, доступны: {healthy}, проблем: {len(results) - healthy}"
            )
            if once:
                return
            time.sleep(interval)
