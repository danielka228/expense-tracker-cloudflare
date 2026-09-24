# СпендТрекер — Cloudflare Workers + D1

Это адаптированная версия исходного Flask-приложения для Cloudflare Workers.

## Что изменилось

- Flask остаётся Flask.
- Gunicorn и Render больше не нужны.
- Flask запускается через Cloudflare Python Workers WSGI.
- PostgreSQL/SQLite через Flask-SQLAlchemy заменены на Cloudflare D1.
- Сессии Flask остаются cookie-based и подписываются через `SECRET_KEY`.
- `/ping` добавлен для проверки доступности.
- HTML-шаблоны встроены в Python Worker.

Cloudflare официально поддерживает Flask в Python Workers и D1 из Python Workers.

## 1. Установить инструменты

Нужны Node.js и uv.

```bash
npm install -g wrangler
```

## 2. Авторизоваться

```bash
npx wrangler login
```

## 3. Создать D1

```bash
npx wrangler d1 create expense-tracker-db
```

Команда покажет `database_id`.

Вставь этот ID в `wrangler.jsonc` вместо `REPLACE_WITH_YOUR_D1_DATABASE_ID`.

## 4. Создать таблицы

```bash
npx wrangler d1 execute expense-tracker-db --remote --file=./schema.sql
```

## 5. Создать секрет Flask

```bash
npx wrangler secret put SECRET_KEY
```

Введи длинную случайную строку. Не помещай настоящий SECRET_KEY в GitHub.

## 6. Деплой

```bash
npx wrangler deploy
```

Cloudflare выдаст адрес вида:

`https://expense-tracker.<твой-subdomain>.workers.dev`

## Локальная разработка

Создай `.dev.vars`:

```text
SECRET_KEY="your-local-secret"
```

Затем:

```bash
uv run pywrangler dev
```

## Важно про старую базу Render

Этот проект создаёт новую D1-базу. Пользователи и расходы из PostgreSQL на Render автоматически не перенесутся.

Если на Render уже есть важные данные, сначала сделай экспорт PostgreSQL и отдельную миграцию в D1.

## Бесплатные лимиты D1

По текущей документации Workers Free включает 5 млн прочитанных строк в день, 100 тыс. записанных строк в день и 5 ГБ общего хранения.

