# Продукты Даром

Backend Telegram Mini App для каталога магазинов, категорий и товаров со скидками. Пользователь сможет просматривать каталог и настраивать отслеживание скидок. Сейчас готова основа API и полноценный контур пользовательской сессии; методы каталога и отслеживания оформлены как контракты и пока отвечают HTTP 501.

Каталог пока не реализован. На следующем этапе предполагаются локальные снимки каталога в SQLite через SQLAlchemy, чтобы поддержать поиск, фильтры и отслеживание изменений скидок; Redis может позднее выступить брокером фоновой синхронизации.

Репозиторий: [alihor123/freefood](https://github.com/alihor123/freefood)

## Состав проекта

| Возможность | Состояние |
| --- | --- |
| Telegram Mini App `initData`, создание пользователя | Реализовано |
| Access/refresh JWT, ротация, проверка текущего пользователя, выход | Реализовано |
| Очистка истёкших и отозванных сессий | Реализовано |
| Просмотр магазинов, категорий, товаров и карточки товара | Контракт API; HTTP 501 |
| CRUD отслеживания скидок пользователя | Контракт API; HTTP 501 |
| Клиент React/TypeScript | Запланирован, ещё не входит в репозиторий |
| Мобильный клиент Kotlin/Jetpack Compose | Возможное дальнейшее развитие |

В первой версии нет ролей, разрешений, dev-login, получения товаров по URL или графиков. Redis и отдельный SQL-кэш каталога сейчас не требуются. Telegram удостоверяет учётную запись; возможность отдельно связать её с будущим Kotlin-клиентом можно добавить позднее.

## Технологии

Python 3.13+, FastAPI, SQLAlchemy Async, aiosqlite, AuthX 1.x, Pydantic Settings, APScheduler 3.x и Alembic. Ограничения зависимостей зафиксированы в `backend/pyproject.toml`, точное разрешение пакетов — в `backend/uv.lock`.

## Структура

```text
backend/
├── app/
│   ├── adapters/       # будущие источники каталога
│   ├── database/       # модели, SQLite и репозитории пользователей/сессий
│   ├── routers/        # auth, каталог и отслеживание
│   ├── schemas/        # DTO и проверка API-данных
│   ├── services/       # Telegram auth, токены и заготовки каталога
│   ├── tasks/          # периодическая очистка сессий, будущая синхронизация
│   ├── config.py       # настройки окружения
│   └── main.py         # FastAPI, CORS, планировщик и точки подключения маршрутов
├── migrations/         # Alembic и начальная миграция
├── .env.example
├── alembic.ini
└── pyproject.toml
docs/                   # область проекта, мини-отчёт и скриншоты
scripts/build_report.py # сборка DOCX из шаблона, краткого текста и скриншотов
```

## Быстрый запуск

Нужны Python 3.13+ и `uv`. В PowerShell перейдите в каталог `backend`, создайте `.env`, если его ещё нет, установите зависимости и примените миграцию:

```powershell
cd backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Укажите значения `JWT_SECRET_KEY` и `TELEGRAM_BOT_TOKEN` в `.env`. Для JWT-секрета можно сгенерировать локальное значение стандартной библиотекой Python:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(48))"
```

Сохраните сгенерированную строку только в локальном `.env`. `TELEGRAM_BOT_TOKEN` выдаёт менеджер Telegram-ботов. Оба секрета обязательны в настройках приложения. Не отправляйте `.env` в Git и не помещайте секреты в README, отчёты или скриншоты.

```powershell
uv sync --all-groups
uv run alembic upgrade head
uv run python -m app.main
```

Эта команда запускает Uvicorn на `127.0.0.1:8000`. Для автоматической перезагрузки кода во время разработки можно запустить `uv run uvicorn app.main:app --reload`. После старта откройте `http://127.0.0.1:8000/docs`. Настройки запуска и CORS заданы прямо в `app/main.py`, как в кампус бэке.

Схема базы создаётся только миграцией Alembic. При старте backend проверяет наличие таблиц пользователей и сессий и подсказывает команду миграции, если схема ещё не применена.

## Конфигурация `.env`

Секреты обязательны. Все остальные параметры имеют значения по умолчанию, приведённые в таблице.

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `JWT_SECRET_KEY` | Обязательный секрет | Подпись JWT; значение хранится только в `.env` |
| `TELEGRAM_BOT_TOKEN` | Обязательный секрет | Серверная проверка Telegram `initData` |
| `JWT_ACCESS_TTL_MINUTES` | `10` минут | Срок access-токена |
| `JWT_REFRESH_TTL_DAYS` | `7` дней | Срок refresh-токена |
| `JWT_COOKIE_SECURE` | `true` | Отправлять cookies только по HTTPS. В локальном `.env` стоит `false` для HTTP |
| `JWT_COOKIE_SAMESITE` | `lax` | Ограничение отправки cookies между сайтами |
| `TELEGRAM_CHECK_INIT_DATA_AGE` | `true` | Проверять допустимый возраст initData |
| `TELEGRAM_INIT_DATA_TTL_SECONDS` | `300` секунд | Максимальный возраст initData при включённой проверке |
| `TELEGRAM_CLOCK_SKEW_SECONDS` | `30` секунд | Допустимое расхождение часов для initData |
| `DATABASE_NAME` | `freefood.db` | Файл SQLite; относительный путь считается от `backend/` |
| `SESSION_CLEANUP_ENABLED` | `true` | Включить очистку старых сессий |
| `SESSION_CLEANUP_INTERVAL_HOURS` | `24` часа | Период фоновой очистки |

`uv sync --all-groups` также устанавливает dev-инструменты для проверок и `python-docx` для генерации отчёта.

## API аутентификации

Все маршруты начинаются с `/api/auth`. При входе и refresh токены возвращаются в JSON и одновременно устанавливаются в cookies. Веб-клиент использует cookies, будущий мобильный клиент сможет использовать JSON и заголовок `Authorization: Bearer <access_token>`.

| Метод и путь | Действие | Успешный ответ |
| --- | --- | --- |
| `POST /api/auth/telegram` | Проверяет подписанный Telegram `initData`, создаёт пользователя при первом входе и открывает сессию | `200`, access/refresh и профиль |
| `POST /api/auth/refresh` | Принимает refresh из JSON либо cookie и атомарно ротирует его | `200`, новая пара для той же сессии |
| `GET /api/auth/me` | Возвращает пользователя действующей access-сессии | `200`, профиль |
| `POST /api/auth/logout` | Отзывает текущую сессию | `200`, подтверждение выхода |

При неверной подписи, истёкшем JWT, отозванной сессии или повторном предъявлении уже заменённого refresh-токена API отвечает `401`.

### Пример клиентского обмена

1. Telegram-клиент передаёт исходную строку `initData` на `POST /api/auth/telegram`.
2. Backend проверяет подпись, получает Telegram ID и создаёт или находит локального пользователя. В ответе клиент получает JSON-поля `access_token`, `refresh_token`, `token_type`, `expires_in` и `user`.
3. Клиент вызывает защищённые маршруты с access-токеном в Bearer-заголовке. `GET /api/auth/me` возвращает профиль текущей сессии.
4. После истечения access-токена клиент отправляет сохранённый refresh-токен на `POST /api/auth/refresh` и заменяет оба локальных токена новой парой. Старый refresh-токен после ротации использовать нельзя.
5. При выходе клиент вызывает `POST /api/auth/logout` с access-токеном и удаляет локально сохранённую пару.

Refresh-токен хранится в базе только в виде SHA-256-хеша. Каждый access-запрос проверяет JWT средствами AuthX и наличие связанной неотозванной сессии. Срок JWT проверяется AuthX. Срок записи в таблице `auth_sessions` нужен для периодической очистки.

### Cookies для веб-клиента

AuthX устанавливает `access_token_cookie` и `refresh_token_cookie` с `HttpOnly`, `SameSite` и сроками, соответствующими JWT. JavaScript не читает эти cookies. Браузер сохраняет и отправляет их сам, если в `fetch` указано `credentials: 'include'`. JSON с токенами веб-клиенту сохранять не требуется.

Для запросов с cookies, которые изменяют данные, включена CSRF-защита AuthX. Отдельные cookies `csrf_access_token` и `csrf_refresh_token` доступны JavaScript. При refresh без JSON-токена веб-клиент отправляет значение `csrf_refresh_token` в заголовке `X-CSRF-TOKEN`. При logout и других изменяющих запросах используется значение `csrf_access_token`. После refresh значения нужно читать заново. GET-профиль не требует CSRF-заголовка.

Явный Bearer-токен имеет приоритет над cookie. Refresh из JSON работает без CSRF-заголовка. При logout сессия отзывается в базе и все четыре cookies удаляются.

Для локального веб-клиента используйте `http://127.0.0.1:5173` с API `http://127.0.0.1:8000`, чтобы `SameSite=lax` работал между портами. В локальном `.env` задано `JWT_COOKIE_SECURE=false`. При HTTPS установите `true`. Если веб-клиент и API размещены на разных сайтах, нужен `JWT_COOKIE_SAMESITE=none` вместе с `JWT_COOKIE_SECURE=true`.

## Каталог и скидки

Маршруты каталога публичные: `GET /api/stores`, `GET /api/categories`, `GET /api/products` и `GET /api/products/{product_id}`. Контракты включают магазины, цены, скидки, наличие, фильтры, сортировку и пагинацию.

Маршруты `/api/tracking` требуют access-токен и описывают будущие операции `GET`, `POST`, `GET /{tracking_id}`, `PATCH /{tracking_id}` и `DELETE /{tracking_id}`. Модели запросов проверяют, что правило относится ровно к товару или категории, а PATCH содержит допустимое непустое изменение. До подключения хранилища обработчики явно возвращают HTTP 501 и ничего не записывают.

## Очистка сессий

При старте приложения очистка выполняется один раз, после чего APScheduler запускает её с интервалом из `SESSION_CLEANUP_INTERVAL_HOURS` (по умолчанию сутки). Один SQL-запрос `DELETE` удаляет все сессии с `expires_at <= текущее время` или заполненным `revoked_at`. Дополнительного срока хранения нет: записи удаляются при ближайшей очистке. Срок JWT и отзыв сессии проверяются на запросах независимо от этого задания.

## Проверки и отчёт

```powershell
cd backend
uv run pytest
uv run ruff check .
```

Результаты проверок сохранены в `docs/validation.json`. В мини-отчёт входят краткий текст из `docs/mini_report.md`, титульник и стили из `docs/report_template.docx`, а также скриншоты Swagger и ответов API из `docs/screenshots/`: `01_swagger.jpg`, `02_auth_validation.jpg`, `03_api_responses.jpg`.

Из корня репозитория DOCX-отчёт собирается так:

```powershell
uv run --project backend --group docs python scripts/build_report.py
```

Файл появится в `docs/Мини-отчёт_Тема_1.docx`.

## Документы и официальные материалы

- [Область проекта](docs/project_scope.md)
- [Справочник функций](docs/functions.md)
- [Мини-отчёт](docs/mini_report.md)
- [Генератор DOCX-отчёта](scripts/build_report.py)
- [Telegram Mini Apps](https://core.telegram.org/bots/webapps)
- [FastAPI](https://fastapi.tiangolo.com/features/)
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [APScheduler 3.x](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
