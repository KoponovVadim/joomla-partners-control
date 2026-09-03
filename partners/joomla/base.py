from abc import ABC

from partners.services.credentials import decrypt_password, decrypt_secret
from .exceptions import JoomlaNotImplementedError


class JoomlaAdapter(ABC):
    version = "unknown"

    def __init__(self, donor):
        self.donor = donor

    def credentials(self):
        return self.donor.username, decrypt_password(self.donor.encrypted_password)

    def api_token(self):
        return decrypt_secret(self.donor.encrypted_api_token)

    def connector_token(self):
        return decrypt_secret(self.donor.encrypted_connector_token)

    def _unavailable(self, operation):
        raise JoomlaNotImplementedError(
            f"Адаптер Joomla {self.version}: {operation} пока не реализована"
        )

    def test_connection(self):
        self._unavailable("проверка подключения")

    def detect_version(self):
        return self.version

    def get_article(self, article_id):
        self._unavailable("получение материала")

    def update_article(self, article_id, html):
        self._unavailable("публикация")

    def create_article(self, **kwargs):
        self._unavailable("создание материала")

    def trash_article(self, article_id):
        self._unavailable("удаление материала")

    def restore_article(self, article_id):
        self._unavailable("восстановление материала")

    def adopt_article(self, article_id):
        self._unavailable("принятие материала под управление")
