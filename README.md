# Joomla Partners Control

Внутренняя Django-система веб-студии для централизованного управления страницами «Наши партнёры» на Joomla 3/4/5. MVP хранит доноров, клиентов и размещения, строит контролируемый HTML, показывает изолированный preview и журналирует попытки работы с Joomla. Собственные Joomla-расширения на сайты не устанавливаются.

## Архитектура

- `partners/models.py` — DonorSite, ClientSite, Placement, PageTemplate, PublicationLog.
- `partners/services/page_renderer.py` — детерминированный renderer, CSS отдельно от body, SHA-256 и защитный `JPC-MANAGED-PAGE` marker.
- `partners/services/credentials.py` — Fernet-шифрование паролей ключом из environment.
- `partners/joomla/` — интерфейс и отдельные адаптеры Joomla 3/4/5. Joomla 3 поддерживает вход в administrator, чтение существующего материала, безопасное принятие под управление и обновление; Joomla 4/5 пока честно возвращают `not_implemented`.
- `partners/views.py`, Django templates и vanilla JS — собственный защищённый интерфейс, CRUD, fetch-переключатели и drag-and-drop.
- Django admin доступен как служебный интерфейс `/admin/`.

## Локальный запуск без Docker

Требуется Python 3.13. Если `POSTGRES_HOST` не задан, development использует SQLite.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export CREDENTIAL_ENCRYPTION_KEY=local-development-key
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

В PowerShell активация: `.venv\Scripts\Activate.ps1`, environment: `$env:CREDENTIAL_ENCRYPTION_KEY='local-development-key'`.

## Docker / первый запуск

```bash
cp .env.example .env
# замените все change-me; APP_PORT можно оставить пустым
./scripts/deploy.sh
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
```

Контейнер запуска ждёт PostgreSQL, выполняет migrations и `collectstatic`, затем запускает Gunicorn на внутреннем `0.0.0.0:8000`. Наружу Compose публикует приложение только на `127.0.0.1:${APP_PORT}`. PostgreSQL наружу не публикуется.

### Environment

Все параметры перечислены в `.env.example`. Настоящий `.env` исключён из git. `SECRET_KEY`, `POSTGRES_PASSWORD` и `CREDENTIAL_ENCRYPTION_KEY` необходимо заменить. Не меняйте encryption key после сохранения credentials: существующие пароли перестанут расшифровываться. Пароли доноров находятся в PostgreSQL только в зашифрованном `DonorSite.encrypted_password`, никогда не возвращаются в HTML формы или списков.

### Автопоиск порта и VDS

`scripts/deploy.sh` сохраняет текущий `APP_PORT`, если он свободен или уже принадлежит этому Compose-проекту. При конфликте `scripts/find_free_port.py` проверяет реальный socket bind и выбирает порт из `8100–8999`, записывает его в `.env`, после чего запускает Compose. Внешний reverse proxy следует направить на напечатанный `http://127.0.0.1:<порт>`.

Обновление:

```bash
git pull
./scripts/deploy.sh
```

## Backup PostgreSQL

```bash
docker compose exec -T db pg_dump -U joomla_partners joomla_partners > backup.sql
cat backup.sql | docker compose exec -T db psql -U joomla_partners joomla_partners
```

Имя пользователя/БД берите из `.env`. Храните дамп и encryption key раздельно и безопасно.

## Модели и безопасность удаления

DonorSite описывает Joomla-сайт и содержит уникальный managed-marker. ClientSite хранит логотип и цельный HTML-фрагмент. Placement связывает их, задаёт порядок, overrides и link attributes; пара donor/client уникальна. PageTemplate содержит wrapper/item/CSS и настройку включения CSS в материал. PublicationLog фиксирует preview, connection и publication actions с реальным статусом.

Перед первой записью в существующий материал Joomla 3 оператор обязан нажать «Принять материал под управление». Система сохраняет полный исходный HTML в `ArticleSnapshot`, затем добавляет невидимый UUID-marker. Каждое последующее обновление также создаёт snapshot и запрещается при несовпадении marker. Проверка подключения читает материал и корректно снимает блокировку редактирования через `article.cancel`.

Удаление Placement убирает только связь. ClientSite архивируется через `enabled=false`, связи сохраняются. Физическое удаление клиента, имеющего размещения, защищено `PROTECT`. Будущие trash/cleanup операции Joomla обязаны сначала получить материал и проверить совпадение managed-marker; одного совпавшего article ID недостаточно.

## Проверки

```bash
python manage.py check
python manage.py test
docker compose config
```
