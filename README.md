# Joomla Partners Control

Внутренняя Django-система веб-студии для централизованного управления страницами «Наши партнёры» на Joomla 3/4/5. Система хранит доноров, клиентов и размещения, строит контролируемый HTML, показывает изолированный preview и журналирует работу с Joomla. Собственные Joomla-расширения на сайты не устанавливаются.

## Архитектура

- `partners/models.py` — DonorSite, ClientSite, Placement, PageTemplate, PublicationLog и ArticleSnapshot.
- `partners/services/page_renderer.py` — детерминированный renderer, CSS отдельно от body, SHA-256 и защитный `JPC-MANAGED-PAGE` marker.
- `partners/services/credentials.py` — Fernet-шифрование паролей и API tokens ключом из environment.
- `partners/joomla/` — отдельный HTML-адаптер Joomla 3 и общий Web Services API-адаптер Joomla 4/5. Все версии поддерживают чтение, безопасное принятие материала под управление, создание, обновление, marker verification и snapshots.
- `partners/views.py`, Django templates и vanilla JS — защищённый интерфейс, CRUD, переключатели, drag-and-drop и отдельное управление несколькими шаблонами страниц.
- Django admin доступен как служебный интерфейс `/admin/`.
- `.github/workflows/tests.yml` запускает Django checks, проверку миграций, `collectstatic` и тесты на push/PR.

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

Контейнер запуска ждёт PostgreSQL, выполняет migrations и `collectstatic`, затем запускает Gunicorn на внутреннем `0.0.0.0:8000`. Наружу Compose публикует приложение только на `127.0.0.1:${APP_PORT}`. PostgreSQL наружу не публикуется. Загруженные логотипы сохраняются в отдельном Docker volume `media_data`.

### Environment

Все параметры перечислены в `.env.example`. Настоящий `.env` исключён из git.

- `SECRET_KEY`, `POSTGRES_PASSWORD` и `CREDENTIAL_ENCRYPTION_KEY` необходимо заменить. Production-запуск с пустыми значениями или `change-me` блокируется.
- Не меняйте `CREDENTIAL_ENCRYPTION_KEY` после сохранения credentials: существующие пароли перестанут расшифровываться.
- `PUBLIC_BASE_URL` — внешний HTTPS URL самой панели, например `https://parasyte.deluxmedia.ru`. Он используется для превращения загруженных логотипов и относительных `image_override` в абсолютные URL перед публикацией на сторонние Joomla-сайты.
- `ALLOWED_HOSTS` должен содержать внешний домен панели.
- `CSRF_TRUSTED_ORIGINS` должен содержать внешний origin с `https://`.

Пароли и API tokens доноров находятся в PostgreSQL только в зашифрованных полях и не возвращаются в HTML форм или списков. Joomla API token передаётся только в заголовке `X-Joomla-Token`; redirects не следуются автоматически, а token удаляется из текстов API-ошибок.

### Reverse proxy и media

`scripts/deploy.sh` сначала проверяет обязательные production-переменные и `DEBUG=0`, затем сохраняет текущий `APP_PORT`, если он свободен или уже принадлежит этому Compose-проекту. При конфликте `scripts/find_free_port.py` проверяет реальный socket bind и выбирает порт из `8100–8999`, записывает его в `.env`, после чего запускает Compose. Reverse proxy направляется на напечатанный `http://127.0.0.1:<порт>` и обязан передавать `Host` и `X-Forwarded-Proto`:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

При `DEBUG=0` включены HTTPS redirect, secure session/CSRF cookies, HSTS, `nosniff`, same-origin referrer policy и `X-Frame-Options: DENY`. `SECURE_HSTS_INCLUDE_SUBDOMAINS` и `SECURE_HSTS_PRELOAD` намеренно выключены по умолчанию; включайте их только если HTTPS гарантирован для всех поддоменов.

Загруженные клиентские логотипы лежат в `MEDIA_ROOT/client_logos/`. Приложение само публично отдаёт только непосредственные JPG, PNG, WebP и GIF-файлы из `/media/client_logos/`, в том числе при `DEBUG=0`; вложенные пути, traversal и остальные файлы из `MEDIA_ROOT` через этот endpoint недоступны. Это позволяет использовать абсолютные URL логотипов непосредственно в HTML, публикуемом на Joomla-донорах, без обязательного отдельного location для media в Nginx. Для большого объёма файлов reverse proxy позже можно настроить на прямую раздачу `/media/client_logos/`.

`STATIC_URL` и `MEDIA_URL` заданы root-relative (`/static/` и `/media/`), поэтому ресурсы корректно работают и на вложенных URL панели.

Обновление:

```bash
git pull --ff-only origin main
./scripts/deploy.sh
```

## Joomla 3: существующий материал

Если в доноре указан `article_id`, перед первой записью оператор нажимает «Принять материал под управление». Система:

1. входит в Joomla administrator;
2. читает существующий материал;
3. сохраняет полный исходный HTML в `ArticleSnapshot`;
4. добавляет невидимый UUID-marker `JPC-MANAGED-PAGE`;
5. проверяет, что marker реально сохранился.

Каждое последующее обновление также создаёт snapshot и запрещается при несовпадении marker. Проверка подключения читает материал и снимает блокировку редактирования через `article.cancel`.

## Joomla 3: создание нового материала

Если `article_id` оставлен пустым, первая синхронизация создаёт новый материал через штатную форму `com_content`. Используются поля донора:

- `article_title` — заголовок, по умолчанию «Наши партнёры»;
- `article_alias` — alias, может быть пустым, тогда Joomla может сформировать его сама;
- `article_category_id` — ID категории Joomla, по умолчанию `2` (обычно «Uncategorised/Без категории»).

Создание выполняется через `article.apply`, чтобы получить назначенный Joomla ID. После ответа система проверяет managed-marker, сохраняет `article_id` и фактический alias в DonorSite и снимает edit-lock. Если ID или marker определить не удалось, операция фиксируется как ошибка и дальнейшая автоматическая синхронизация не продолжается.

## Joomla 4/5: Web Services API

Для Joomla 4/5 в доноре выберите «API Token». Если поле API URL пустое, JPC вычислит базовый URL вида `https://site.test/api/index.php/v1` из Admin URL; нестандартный базовый URL можно указать явно.

В Joomla нужен отдельный сервисный пользователь с включённым API token, правом входа в Web Services (`core.login.api`) и правами просмотра, создания и редактирования материалов `com_content`. JPC использует штатные endpoints `content/articles`: GET для проверки/чтения, POST с `articletext` для создания и PATCH с `introtext`/`fulltext` для обновления.

После POST полученный article ID и фактический alias сохраняются до повторной проверки managed-marker. Поэтому даже если Joomla отфильтровала marker и verification завершилась ошибкой, следующая синхронизация продолжит работу с уже созданным материалом и не создаст дубликат.

## Шаблоны страниц

PageTemplate содержит wrapper HTML, item HTML, CSS и настройку включения CSS непосредственно в материал. В интерфейсе можно создавать и редактировать несколько шаблонов; каждый донор выбирает свой шаблон.

## Безопасность удаления

Удаление Placement убирает только связь. ClientSite архивируется через `enabled=false`, связи сохраняются. Физическое удаление клиента, имеющего размещения, защищено `PROTECT`. Будущие trash/cleanup операции Joomla обязаны сначала получить материал и проверить совпадение managed-marker; одного совпавшего article ID недостаточно.

## Backup PostgreSQL

```bash
docker compose exec -T db pg_dump -U joomla_partners joomla_partners > backup.sql
cat backup.sql | docker compose exec -T db psql -U joomla_partners joomla_partners
```

Имя пользователя/БД берите из `.env`. Храните дамп и encryption key раздельно и безопасно.

## Проверки

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
python manage.py test
docker compose config
```
