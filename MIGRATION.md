# Миграция Render PostgreSQL → Cloudflare D1

Схема по смыслу совпадает с исходным приложением:

- `user(id, username, password_hash, created_at)`
- `expense(id, user_id, amount, category, note, expense_date, created_at)`

Хэши паролей можно переносить как есть, потому что приложение продолжает использовать Werkzeug password hashes.

Автоматический перенос невозможен без доступа к твоей PostgreSQL-базе.
