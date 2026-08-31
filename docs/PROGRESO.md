# PROGRESO DE IMPLEMENTACIÓN

## Resumen

Este documento registra el progreso por sesión/capa de implementación.
Cada entrada incluye: qué se hizo, desviaciones del diseño original, cómo verificar localmente, y preguntas abiertas.

---

## 2026-08-28 — Capa 1: DB (modelos + migración inicial)

### Qué se implementó

1. **Estructura de carpetas del backend** (`backend/app/`)
   - `database/base.py` — Base declarativa de SQLAlchemy
   - `database/session.py` — Engine y SessionLocal
   - `core/config.py` — Settings con pydantic-settings
   - `users/models.py` — User, RefreshToken
   - `groups/models.py` — Group, GroupInviteCode, GroupMembership
   - `categories/models.py` — Category
   - `payment_methods/models.py` — PaymentMethod
   - `obligations/models.py` — Obligation, ObligationPeriod
   - `payments/models.py` — Payment
   - `audit/models.py` — AuditLog
   - `notification/models.py` — NotificationRule, NotificationEvent

2. **Configuración**
   - `backend/pyproject.toml` — Dependencias (FastAPI, SQLAlchemy, Alembic, psycopg, pytest)
   - `backend/requirements.txt` — Versión pins para reproducibility
   - `backend/alembic.ini` — Config de Alembic
   - `backend/.env` — Copiado de backend.env.example

3. **Migración Alembic**
   - `backend/alembic/env.py` — Configuración con imports de todos los modelos
   - `backend/alembic/versions/001_initial.py` — Migración manual basada en `docs/db/schema.sql`
   - **Nota**: No se pudo usar `alembic revision --autogenerate` porque PostgreSQL no estaba disponible (la imagen Docker no se descargó a tiempo)

4. **Tests** (`backend/tests/`)
   - `tests/conftest.py` — Fixtures para engine SQLite en memoria y sessions
   - `tests/test_models.py` — 21 tests cubriendo:
     - Unicidad de email en User
     - PK compuesta en GroupMembership
     - Restricciones de Category (sistema vs. grupo)
     - Validación de PaymentMethod (CASH, BANK_ACCOUNT, DIGITAL_WALLET)
     - Restricciones de Obligation (amount >= 0, end_date >= start_date)
     - PK compuesta en ObligationPeriod
     - Restricción de amount en Payment
     - Diseño inmutable de Payment (voided_at)
     - Default en NotificationRule.days_before_due

### Desviaciones del schema.sql

**Ninguna desviación sustancial**. El código replica fielmente el schema.sql con las siguientes notas técnicas:

1. **CITEXT**: Implementado como TypeDecorator (`CITText`) que usa `citext` en PostgreSQL y `TEXT` en SQLite (tests). Esto es necesario para compatibilidad con tests.

2. **JSONB**: Implementado como TypeDecorator (`JSONType`) que usa `JSONB` en PostgreSQL y `TEXT` (serializado como JSON) en SQLite.

3. **ARRAY (SmallInt)**: Implementado como TypeDecorator (`SmallIntArray`) que usa `ARRAY` en PostgreSQL y `JSON` en SQLite.

4. **Partial unique indexes**: Implementados como `Index` con `postgresql_where` en los modelos. En SQLite, estos índices parciales se crean sin la condición WHERE (comportamiento diferente pero aceptable para tests).

5. **FK compuesta en Obligation**: La relación `(responsible_user_id, group_id) -> group_memberships(user_id, group_id)` está modelada pero NO enforced a nivel ORM (la constraint real está en la migración). El campo `responsible_user_id` es nullable en el modelo.

### Cómo verificar localmente

```bash
# 1. Entrar al directorio del backend
cd backend

# 2. Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Levantar PostgreSQL (usando docker-compose del repo)
cd ..  # ir a la raíz del repo
docker compose up -d postgres
# Esperar a que esté listo
sleep 10

# 4. Configurar DATABASE_URL
export DATABASE_URL="postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos"

# 5. Correr migraciones
cd backend
alembic upgrade head

# 6. Verificar que las tablas se crearon
psql "$DATABASE_URL" -c "\dt"

# 7. Insertar seed data (categorías del sistema)
psql "$DATABASE_URL" -c "INSERT INTO categories (group_id, name, icon) VALUES
    (NULL, 'Servicios del hogar', 'home'),
    (NULL, 'Suscripciones', 'tv'),
    (NULL, 'Salud', 'heart'),
    (NULL, 'Educación', 'book'),
    (NULL, 'Seguros', 'shield'),
    (NULL, 'Transporte', 'car'),
    (NULL, 'Créditos y deudas', 'credit-card'),
    (NULL, 'Alimentación', 'shopping-cart'),
    (NULL, 'Entretenimiento', 'film'),
    (NULL, 'Otros', 'more-horizontal')
ON CONFLICT DO NOTHING;"

# 8. Correr tests
cd backend
source .venv/bin/activate
pytest tests/test_models.py -v
```

### Preguntas abiertas / Pendientes

1. **PostgreSQL no disponible durante la implementación**: La imagen `postgres:16-alpine` no se descargó a tiempo. La migración se escribió manualmente. **Recomendación**: Verificar que la migración autogenerada funcione cuando PostgreSQL esté disponible:
   ```bash
   # Para regenerar la migración con autogen (después de verificar PostgreSQL)
   alembic revision --autogenerate -m "Regenerate with PG"
   # Comparar con la versión manual
   diff alembic/versions/001_initial.py alembic/versions/002_*.py
   ```

2. **Composite FK de Obligation**: La FK `(responsible_user_id, group_id) -> group_memberships` no está implementada como constraint en el modelo SQLAlchemy (solo en la migración). Esto se hizo así para evitar problemas con el import circular. **Verificar** que la migración la crea correctamente.

3. **Partial unique indexes en SQLite**: Los tests usan SQLite que no soporta índices parciales con WHERE. Los tests pasan pero no prueban la funcionalidad de índice parcial. **Recomendación**: Crear tests de integración con PostgreSQL real para verificar estas constraints.

4. **Seed data**: El seed de categorías del sistema está en `docs/db/seed.sql` pero no hay script para ejecutarlo automáticamente. **Pendiente**: Crear script `scripts/seed.py` que cargue el seed.

5. **CITEXT case-insensitivity**: En PostgreSQL, el tipo `citext` hace que las búsquedas sean case-insensitive. Los tests de email case-insensitivity deberían pasar en PostgreSQL pero no se probaron con PG real.

### Archivos creados

```
backend/
├── .env
├── .venv/
├── alembic.ini
├── pyproject.toml
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── database/
│   │   ├── base.py
│   │   └── session.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── users/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── groups/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── categories/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── payment_methods/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── obligations/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── payments/
│   │   ├── __init__.py
│   │   └── models.py
│   ├── audit/
│   │   ├── __init__.py
│   │   └── models.py
│   └── notification/
│       ├── __init__.py
│       └── models.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py
└── tests/
    ├── conftest.py
    └── test_models.py
```

---

## 2026-08-28 — Capa 1 (corrección): ENUMs, tipos BigInteger, FKs, verificación contra Postgres real

### Qué se corrigió (6 bugs del revisor)

1. **`sa.JSONB()` AttributeError** (`backend/alembic/versions/001_initial.py:282`): Cambiado `sa.JSONB()` → `from sqlalchemy.dialects.postgresql import JSONB` y `JSONB()`. La migración fallaba con `AttributeError: module 'sqlalchemy' has no attribute 'JSONB'`.

2. **Default de array inválido** (`backend/alembic/versions/001_initial.py:298`): Cambiado `server_default="[3, 1]"` → `server_default=sa.text("'{3,1}'::smallint[]")`. Postgres espera sintaxis `'{3,1}'` para arrays, no JSON `[3, 1]`.

3. **ENUMs creados pero no usados** (migración + 6 modelos): Las columnas `group_memberships.role`, `group_invite_codes.role_to_assign`, `payment_methods.kind`, `obligations.periodicity`, `obligations.currency`, `obligation_periods.status`, `payments.currency`, `notification_rules.channel`, `notification_events.event_type/channel/status` se creaban como `sa.Text()`/`String` aunque los `CREATE TYPE` existían. Corregido a `postgresql.ENUM(..., name='...', create_type=False)` tanto en la migración (usa instancia con `create_type=False` para no recrear el tipo) como en los modelos (`backend/app/groups/models.py`, `payment_methods/models.py`, `obligations/models.py`, `payments/models.py`, `notification/models.py`).

4. **PKs, FKs y montos como Integer en vez de BigInteger** (`backend/app/*/models.py`): Todas las columnas `id`, FKs que apuntan a esos IDs y `expected_amount_cents`/`amount_cents` usaban `Integer`. Cambiadas a `BigInteger` (con `BigInt = BigInteger().with_variant(Integer, "sqlite")` para PKs autoincrementales en SQLite). Migración ya usaba `sa.BigInteger()` correctamente. Archivos tocados: `users`, `groups` (incl. `max_uses`→`SmallInteger`, `uses_count`→`Integer` para reflejar `SMALLINT`/`INT` reales), `categories`, `payment_methods`, `obligations`, `payments`, `audit`, `notification`, y `app/database/base.py` (nuevo helper `BigInt`).

5. **Tres FKs con `ondelete="CASCADE"` inexistente en schema.sql** (`backend/app/groups/models.py`, `payments/models.py`): Quitadas de `groups.created_by → users.id`, `group_invite_codes.created_by_user_id → users.id`, `payments.registered_by_user_id → users.id` (ahora `ForeignKey("users.id")` sin `ondelete`). Verificado que la migración ya tenía `NO ACTION` y que Postgres reporta `NO ACTION` vía `information_schema`.

6. **CHECK `due_month BETWEEN 1 AND 12` faltante en modelo Obligation** (`backend/app/obligations/models.py`): Ya existía `chk_due_month_only_if_annual` y `chk_due_day_range`, pero faltaba `CheckConstraint("due_month BETWEEN 1 AND 12", name="chk_due_month_range")`. Agregado para que el modelo coincida con la migración (`chk_due_month_range` ya en `001_initial.py:210`).

### Salida real de `alembic upgrade head` contra Postgres

```bash
$ docker compose up -d postgres
# esperar: until docker compose ps postgres | grep -q "healthy"; do sleep 2; done
$ export DATABASE_URL="postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos"
$ alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, Initial schema migration - 13 tables from schema.sql

# Verificación de downgrade/upgrade limpio:
$ alembic downgrade base && alembic upgrade head
INFO  [alembic.runtime.migration] Running downgrade 001_initial -> , Initial schema migration - 13 tables from schema.sql
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, Initial schema migration - 13 tables from schema.sql
```

Verificación extra con `psycopg`: `payment_methods.kind` → `payment_method_kind`, `obligations.currency` → `supported_currency`, `obligations.periodicity` → `periodicity`, `group_memberships.role` → `membership_role`, `obligation_periods.status` → `period_status`, `payments.currency` → `supported_currency`, FKs `groups.created_by`/`group_invite_codes.created_by_user_id`/`payments.registered_by_user_id` → `NO ACTION`, `users.id` → `bigint`, `chk_due_month_range` existe, `days_before_due` default → `'{3,1}'::smallint[]`.

### Tests: cuántos y resultado

- **21 tests SQLite** (`tests/test_models.py`) — siguen pasando contra `sqlite:///:memory:` (BigInteger FIX con `BigInt` variant para PKs autoincrementales).
- **6 tests Postgres nuevos** (`tests/test_postgres.py`) — específicos para bugs #1-#3, corren con `DATABASE_URL` real:
  - `test_alembic_upgrade_head_creates_all_tables` — 13 tablas + extensión `citext`
  - `test_jsonb_column_works` — inserta/read `audit_logs.metadata` como JSONB (bug #1)
  - `test_array_default_is_postgres_array` — verifica default `'{3,1}'::smallint[]` y valor por defecto (bug #2)
  - `test_enum_rejects_invalid_payment_method_kind` — `INVALID_KIND` falla con `DataError` (bug #3)
  - `test_enum_rejects_invalid_currency` — `EUR` falla (bug #3)
  - `test_enum_rejects_invalid_role` — `superadmin` falla (bug #3)

```
$ DATABASE_URL="postgresql+psycopg://app:app_dev_only@localhost:5432/gestor_pagos" pytest tests/ -v
...
27 passed, 1 warning in 0.99s
```

### Problemas nuevos encontrados al probar contra Postgres real

- **PKs BigInteger en SQLite**: Al cambiar `Integer` → `BigInteger`, las PKs dejaron de ser `INTEGER PRIMARY KEY AUTOINCREMENT` en SQLite y fallaron con `NOT NULL constraint failed: categories.id`. Se resolvió con `BigInt = BigInteger().with_variant(Integer, "sqlite")` solo para PKs (FKs y montos siguen `BigInteger` puro, Chicago: FK `BIGINT` no necesita autoincrement).
- **PG_ENUM en SQLite**: `postgresql.ENUM(..., create_type=False)` funciona en SQLite (se mapea a VARCHAR) pero había que verificar que `create_all` no intentara crear el tipo. Con `create_type=False` no lo intenta.
- **Imagen postgres lenta**: El `docker pull postgres:16-alpine` tardó >2 min; ahora usa healthcheck activo en vez de `sleep 10`.

---

## 2026-08-28 — Capa 2a: Auth (core/security.py — hashing + JWT)

### Qué se implementó

1. **`backend/app/core/security.py`** — 6 funciones puras (sin DB, sin FastAPI):
   - `hash_password(password: str) -> str` — Hashea con Argon2id usando los parámetros de `settings` (time_cost, memory_cost, parallelism).
   - `verify_password(password: str, password_hash: str) -> bool` — Verifica contra el hash. Captura `VerifyMismatchError` y retorna `False` nunca lanza excepción.
   - `create_access_token(user_id: int) -> str` — JWT HS256 con claims `sub` (user_id como string), `exp` (now + TTL configurable), `iat` (now). Usa `datetime.now(timezone.utc)`.
   - `decode_access_token(token: str) -> dict` — Decodifica y valida el JWT. Propaga `ExpiredSignatureError` / `InvalidTokenError` al caller.
   - `generate_refresh_token() -> str` — Token opaco con `secrets.token_urlsafe(32)`, no es JWT ni derivado del usuario.
   - `hash_refresh_token(token: str) -> str` — SHA-256 hex digest del token (lo que se almacena en `refresh_tokens.token_hash`).

2. **`backend/tests/test_security.py`** — 9 tests:
   - Password hashing: correcta → True, incorrecta → False, misma contraseña genera hashes distintos pero ambos verifican.
   - JWT: round-trip con mismo user_id, token con secret incorrecto falla (`InvalidTokenError`), token expirado falla (`ExpiredSignatureError`).
   - Refresh tokens: dos generaciones producen valores distintos, hash es determinístico, hash es distinto del token original.

3. **Dependencias nuevas** en `pyproject.toml` y `requirements.txt`:
   - `argon2-cffi>=23.1.0` (hashing Argon2id)
   - `pyjwt>=2.8.0` (JWT HS256)
   - `freezegun>=1.5.5` (dev dependency para tests con tiempo congelado, opcional)

### Gap corregido: PYTHONPATH

Agregado `pythonpath = ["."]` a `[tool.pytest.ini_options]` en `backend/pyproject.toml`. Antes de este fix, `pytest tests/` fallaba con `ModuleNotFoundError: No module named 'app'` a menos que se exportara `PYTHONPATH=.` manualmente. Ahora pytest resuelve `app.*` correctamente desde la raíz del backend.

### Resultado de tests

```
$ pytest tests/ -v
36 passed, 1 warning in 4.17s
```

- 21 tests de Capa 1 (test_models.py)
- 6 tests de Capa 1 — Postgres (test_postgres.py)
- 9 tests nuevos de Capa 2a (test_security.py)

### Decisiones de diseño

1. **Claims JWT mínimos**: Solo `sub`, `exp`, `iat` — sin `roles`, `groups` ni datos del usuario. Estos claims se agregarán cuando se implementen los endpoints de auth (Capa 2b). Mantener el JWT ligero minimiza el tamaño del token y reduce superficie de ataque.

2. **Argon2id como función pura**: Cada llamada a `hash_password`/`verify_password` instancia un `PasswordHasher` nuevo con los parámetros de `settings`. Esto es deliberado: en producción los parámetros pueden cambiar entre requests (reconfiguración), y un PasswordHasher no es thread-safe para reutilización.

3. **Refresh token hash con SHA-256**: Se usa SHA-256 (no Argon2id) para el hash del refresh token porque: (a) el refresh token ya es un valor aleatorio de 256 bits, no una contraseña con baja entropía; (b) SHA-256 es suficiente para prevenir que un atacante que obtiene la tabla `refresh_tokens` pueda usar los tokens directamente; (c) Argon2id sería overkill y añadiría latencia innecesaria en cada refresh.

4. **`decode_access_token` propaga excepciones**: A diferencia de `verify_password`, esta función NO captura errores de JWT. La razón es que el dependency de FastAPI (en la sesión siguiente) necesita distinguir entre token expirado (redirigir a refresh) y token inválido (rechazar 401).

5. **`freezegun` no se usa finalmente**: El test de token expirado construye el token manualmente con `exp` en el pasado en vez de congelar el tiempo. Es más simple y no añade dependencia de runtime.

### Preguntas abiertas para el humano

1. **¿Agregar `freezegun` a `dev` dependencies de `pyproject.toml`?** No se usó finalmente pero puede ser útil para tests futuros con timing sensible.

2. **¿Rotación de JWT_SECRET documentada como procedure?** ADR-008 menciona que invalida todas las sesiones — ¿procedimiento documentado en algún ADR o wiki?

3. **¿Límite de tamaño para `password`?** Las funciones actuales no validan longitud mínima/máxima. ¿Eso va en el endpoint (validación Pydantic) o también aquí?

---

## 2026-08-28 — Capa 2b: Auth (endpoints register/login/refresh/logout + main.py)

### Qué se implementó, archivo por archivo

1. **`backend/app/main.py`** — Punto de entrada FastAPI:
   - CORS middleware: `allow_origins=[settings.FRONTEND_ORIGIN]`, `allow_credentials=True` (ADR-008).
   - Router de auth bajo prefijo `/api/v1`.
   - Exception handler para `HTTPException`: aplana el detail cuando es un dict `{"detail": ..., "code": ...}` para que la respuesta JSON tenga `{"detail": "...", "code": "..."}` al nivel raíz (no anidado).
   - Exception handler genérico para errores inesperados → 500.

2. **`backend/app/auth/__init__.py`** — Módulo vacío (init de paquete).

3. **`backend/app/auth/schemas.py`** — Pydantic v2 schemas:
   - `RegisterRequest`: email (EmailStr), password (8-128 chars), full_name, phone_number (opcional). Sin invite_code.
   - `LoginRequest`: email (EmailStr), password.
   - `AccessTokenResponse`: access_token, token_type="bearer".

4. **`backend/app/auth/repository.py`** — Queries SQLAlchemy:
   - `get_user_by_email`, `create_user`, `get_active_refresh_token_by_hash`, `create_refresh_token`, `revoke_refresh_token`.
   - Todas las queries usan la sesión de SQLAlchemy inyectada (sin imports de DB global).

5. **`backend/app/auth/service.py`** — Lógica de negocio:
   - `register()`: valida email único (409 EMAIL_ALREADY_EXISTS), crea usuario, retorna par de tokens.
   - `authenticate()`: busca usuario + verify_password. Si falla, 401 INVALID_CREDENTIALS (mismo mensaje para email inexistente y password incorrecto — no revela cuál falló).
   - `refresh()`: valida cookie, rota refresh token (revoca el viejo, emite nuevo), retorna par nuevo.
   - `logout()`: revoca el refresh token si existe (idempotente — no es error si no existe).
   - `AuthError` exception con detail, code y status_code.

6. **`backend/app/auth/router.py`** — 4 endpoints:
   - `POST /register` → 201 + body AccessTokenResponse + cookie refresh_token.
   - `POST /login` → 200 + body AccessTokenResponse + cookie refresh_token.
   - `POST /refresh` → 200 + body AccessTokenResponse + cookie nueva (rotación).
   - `POST /logout` → 204 + borra cookie (idempotente).

7. **`backend/app/database/session.py`** — Agregada función `get_db_session()` como generador plano para `Depends()` de FastAPI. No se borra `get_db()` existente.

8. **`backend/tests/test_auth.py`** — 10 tests de integración con Postgres real:
   - Register: éxito (201), email duplicado (409).
   - Login: éxito (200), email inexistente (401), password incorrecta (401).
   - Refresh: éxito con rotación (200 + fila vieja revoked), reuso de token viejo (401), sin cookie (401).
   - Logout: éxito (204 + cookie borrada + fila revoked), idempotente (204 dos veces).

9. **`backend/tests/test_security.py`** — Eliminado import muerto de `freezegun` (no estaba en requirements.txt, causaba `ModuleNotFoundError` en instalación fresca).

### Formato de error elegido

**Aplanado**: `{"detail": "...", "code": "..."}` al nivel raíz del JSON. Esto se logra con un exception handler custom en `main.py` que intercepta `HTTPException` y, cuando el `detail` es un dict con keys `"detail"` y `"code"`, retorna el dict directamente como JSON body (sin el wrapper `"detail"` que FastAPI agrega por defecto). El motivo: el contrato de API (ADR-004) define `{"detail": "...", "code": "..."}` y el frontend no debería tener que parsear `resp.detail.code`.

### Resultado de tests

```
$ pytest tests/ -v
46 passed, 8 warnings in 8.52s
```

- 21 tests de Capa 1 (test_models.py)
- 6 tests de Capa 1 — Postgres (test_postgres.py)
- 9 tests de Capa 2a (test_security.py)
- 10 tests nuevos de Capa 2b (test_auth.py)

### Decisiones de diseño

1. **`get_db_session()` como generador plano**: Se creó una función nueva en `session.py` en vez de modificar `get_db()` existente. La razón: `get_db()` usa `@contextmanager` (para scripts/Alembic), pero FastAPI `Depends()` necesita un generador plano (yield sin decorador). Coexisten las dos sin romper nada.

2. **Login no revela si el email existe**: Ambos casos (email inexistente y password incorrecto) retornan el mismo `401 INVALID_CREDENTIALS`. Esto previene enumeración de usuarios.

3. **Refresh token viaja SOLO en cookie httpOnly**: Nunca se retorna en el JSON body. La cookie se configura con `secure=True`, `samesite="none"`, `httponly=True`, path restringido a `/api/v1/auth/refresh`.

4. **Rotación de refresh token**: Cada uso de `/refresh` invalida la fila vieja (revoked_at = now) y crea una nueva. Esto previene replay attacks y es consistente con ADR-001.

5. **Logout idempotente**: Si el token ya estaba revocado o no existe, logout retorna 204 igual. No es un error semántico.

6. **Dependencia `email-validator`**: Se instaló para soportar `EmailStr` de Pydantic. Ya estaba incluida en `pydantic[email]`.

### Pendientes a propósito (no implementados en esta capa)

- **Rate limiting** (ADR-008): `slowapi` en `/auth/login`, `/auth/register`, `/auth/refresh`. Queda pendiente para una capa de hardening.
- **Audit logging** (ADR-008): `audit.service.log_action` en register y login. Queda pendiente cuando se implemente el módulo de auditoría.
- **invite_code en register**: Listado en ADR-004/ADR-014 pero los grupos todavía no existen como feature.

### Preguntas abiertas

1. **¿Usar `httpx2` en vez de `httpx`?** Starlette emite `DeprecationWarning` sugiriendo instalar `httpx2` para el TestClient. ¿Migrar o ignorar hasta que sea necesario?

2. **¿Agregar `SameSite` explicitamente a la cookie?** Configurado como `samesite="none"` que es necesario para cross-origin (Cloudflare Pages → Render). ¿Alguna preferencia de testing adicional?

---

## 2026-08-28 — Capa 2c: Auth dependency (`get_current_user`) + `GET /users/me`

### Qué se implementó, archivo por archivo

1. **`backend/app/core/deps.py`** (nuevo) — Dependency `get_current_user`:
   - Parsea header `Authorization: Bearer <token>` (usa `Header(None)` directamente, no `HTTPBearer`).
   - Decodifica JWT con `decode_access_token()` de `core/security.py`.
   - Busca usuario por `sub` claim (user_id como string → int) en la DB.
   - Valida `is_active == True`.
   - 5 códigos de error distintos (ver tabla abajo).

2. **`backend/app/auth/repository.py`** (modificado) — Agregada función `get_user_by_id(db, user_id) -> User | None`. Misma query pattern que `get_user_by_email` pero filtra por `User.id`.

3. **`backend/app/users/schemas.py`** (nuevo) — `UserResponse` (Pydantic v2 con `from_attributes=True`):
   - Campos: `id`, `email`, `full_name`, `phone_number`, `whatsapp_opt_in`, `created_at`.
   - NUNCA expone `password_hash` (no está en el schema).

4. **`backend/app/users/router.py`** (nuevo) — Endpoint protegido:
   - `GET /api/v1/users/me` con `Depends(get_current_user)`.
   - Retorna `UserResponse` con los datos del usuario autenticado.

5. **`backend/app/main.py`** (modificado) — Agregado router de users con prefijo `/api/v1`.

6. **`backend/tests/test_users_me.py`** (nuevo) — 8 tests de integración con Postgres real:
   - `test_returns_user_profile` → 200, campos correctos, sin `password_hash`.
   - `test_no_header` → 401 MISSING_TOKEN.
   - `test_header_without_bearer_prefix` → 401 MISSING_TOKEN.
   - `test_bearer_with_empty_token` → 401 MISSING_TOKEN.
   - `test_garbage_token` → 401 INVALID_TOKEN.
   - `test_token_signed_with_wrong_secret` → 401 INVALID_TOKEN.
   - `test_expired_token` → 401 TOKEN_EXPIRED.
   - `test_nonexistent_user_id` → 401 USER_NOT_FOUND.

### Códigos de error de `get_current_user`

| Código | Cuándo se dispara |
|---|---|
| `MISSING_TOKEN` | No hay header `Authorization`, o no empieza con `Bearer `, o el token después de `Bearer` está vacío. |
| `TOKEN_EXPIRED` | JWT válido pero `exp` ya pasó (`jwt.ExpiredSignatureError`). |
| `INVALID_TOKEN` | JWT con firma incorrecta, estructura malformada, o claim `sub` no es un int válido (`jwt.InvalidTokenError`). |
| `USER_NOT_FOUND` | `sub` del JWT es válido pero no existe usuario con ese ID en la DB (fue borrado). |
| `USER_INACTIVE` | Usuario existe pero `is_active == False`. |

### Resultado de tests

```
$ pytest tests/ -v
54 passed, 8 warnings in 8.50s
```

- 21 tests de Capa 1 (test_models.py)
- 6 tests de Capa 1 — Postgres (test_postgres.py)
- 9 tests de Capa 2a (test_security.py)
- 10 tests de Capa 2b (test_auth.py)
- 8 tests nuevos de Capa 2c (test_users_me.py)

### Decisiones de diseño

1. **`Header(None)` vs `HTTPBearer`**: Se usó `Header(None)` directamente porque es más explícito y no depende de la clase `HTTPBearer` de FastAPI (que tiene su propio formato de error por defecto). Esto da control total sobre el formato `{"detail": ..., "code": ...}`.

2. **`get_user_by_id` en `auth/repository.py`**: Aunque es una query de "users", se puso en `auth/repository.py` porque es la única query de lookup de usuario que necesita el módulo de auth (deps.py). Cuando groups/obligations necesiten queries de usuario, se evalúa si mover a `users/repository.py`.

3. **5 códigos de error granulares**: En vez de un solo `UNAUTHORIZED`, se distinguen los 5 casos para que el frontend pueda reaccionar de forma diferente (ej: `TOKEN_EXPIRED` → refrescar silenciosamente, `USER_NOT_FOUND` → pedir re-login, `MISSING_TOKEN` → redirigir a login).

4. **`UserResponse` sin `password_hash`**: El schema Pydantic expone solo campos públicos. Nunca se serializa `password_hash` porque no está en el schema. Esto es defense-in-depth: incluso si accidentalmente se pasara el objeto User completo, Pydantic lo filtraría.

### Preguntas abiertas

1. **¿Rate limiting en `get_current_user`?** Tokens inválidos podrían usarse para fingerprinting (probar muchos IDs). ¿Agregar rate limiting a endpoints protegidos o solo a auth?

2. **¿Middleware de logging para 401s?** Los 401s son esperados (tokens expirados, etc.) pero podrían ser útiles para detectar intentos de ataque. ¿Loguear o ignorar?

3. **¿Mover `get_user_by_id` a un módulo dedicado de users?** Actualmente vive en `auth/repository.py`. Cuando se creen más endpoints de users, podría merecer su propio repository.

---

## 2026-08-28 — Capa 3a: Groups (CRUD + membresías + get_current_membership)

### Qué se implementó, archivo por archivo

1. **`backend/app/core/deps.py`** (modificado) — Agregados 3 elementos nuevos:
   - `get_current_membership(group_id: int, current_user, db) -> GroupMembership`: Dependency simple (no factory) que FastAPI resuelve automáticamente del path param `group_id`. Verifica que el grupo existe (404 GROUP_NOT_FOUND) y que el usuario es miembro (403 NOT_GROUP_MEMBER). Retorna la membresía con su `.role`.
   - `require_owner(membership)`: Helper que levanta 403 FORBIDDEN_NOT_OWNER si el rol no es `owner`.
   - `require_admin(membership)`: Helper que levanta 403 FORBIDDEN_NOT_ADMIN si el rol no es `owner` ni `admin`.
   - Se mantuvo `get_current_user` intacto. Se agregó import de `GroupMembership` al inicio del archivo.

2. **`backend/app/groups/schemas.py`** (nuevo) — Schemas Pydantic v2:
   - `GroupCreate`: `name: str` (1-200 chars).
   - `GroupUpdate`: `name: str` (1-200 chars).
   - `GroupResponse`: `id`, `name`, `created_by`, `created_at`, `updated_at`, `my_role: str` (rol del usuario actual, construido en el endpoint, no de la tabla).
   - `MemberAdd`: `email: EmailStr`, `role: Literal["admin", "member"]` default `"member"`. Nunca acepta `"owner"`.
   - `MemberRoleUpdate`: `role: Literal["admin", "member"]`. Mismo motivo.
   - `MemberResponse`: `user_id`, `email`, `full_name`, `role`, `joined_at`.

3. **`backend/app/groups/repository.py`** (nuevo) — Queries SQLAlchemy:
   - `create_group`, `get_group_by_id`, `list_groups_for_user` (join con GroupMembership), `create_membership`, `get_membership`, `list_members` (join con User para email/full_name), `update_membership_role`, `delete_membership`, `update_group_name`.
   - Todas las queries usan `db.flush()` en vez de `db.commit()` para permitir transacciones atómicas desde el service.

4. **`backend/app/groups/service.py`** (nuevo) — Lógica de negocio:
   - `create_group()`: Crea Group + GroupMembership(role='owner') en la misma transacción. `db.commit()` solo al final.
   - `add_member()`: Busca usuario por email (reutiliza `get_user_by_email` de auth.repository). Si no existe → 404 USER_NOT_FOUND_MUST_REGISTER. Si ya es miembro → 409 ALREADY_MEMBER.
   - `change_member_role()`: Si el target tiene role=='owner' → 403 CANNOT_MODIFY_OWNER.
   - `remove_member()`: Mismo guard → 403 CANNOT_MODIFY_OWNER si intenta quitar al owner.
   - `GroupError` exception con detail, code, status_code (mismo patrón que AuthError).

5. **`backend/app/groups/router.py`** (nuevo) — 7 endpoints:
   - `POST /groups` → 201 (solo `get_current_user`, el grupo no existe todavía).
   - `GET /groups` → 200 (lista grupos del usuario con `my_role`).
   - `GET /groups/{group_id}` → 200 (usa `get_current_membership`).
   - `PATCH /groups/{group_id}` → 200 (usa `get_current_membership` + `require_owner`).
   - `POST /groups/{group_id}/members` → 201 (usa `get_current_membership` + `require_admin`).
   - `PATCH /groups/{group_id}/members/{user_id}` → 200 (usa `get_current_membership` + `require_admin`).
   - `DELETE /groups/{group_id}/members/{user_id}` → 204 (usa `get_current_membership` + `require_admin`).

6. **`backend/app/main.py`** (modificado) — Agregado `groups_router` con prefijo `/api/v1`.

7. **`backend/tests/test_groups.py`** (nuevo) — 27 tests de integración con Postgres real:
   - **POST /groups**: éxito (201 + my_role=owner), creador es owner, sin auth → 401.
   - **GET /groups**: vacío, solo grupos del usuario, incluye my_role.
   - **GET /groups/{id}**: éxito, no miembro → 403 NOT_GROUP_MEMBER, no existe → 404 GROUP_NOT_FOUND.
   - **PATCH /groups/{id}**: owner → 200, member → 403 FORBIDDEN_NOT_OWNER, admin → 403 FORBIDDEN_NOT_OWNER.
   - **POST /groups/{id}/members**: éxito member, éxito admin, admin agrega, usuario no existe → 404, ya miembro → 409, member no puede → 403, role=owner rechazado → 422.
   - **PATCH /groups/{id}/members/{uid}**: éxito, owner no modificable → 403, no miembro → 404.
   - **DELETE /groups/{id}/members/{uid}**: éxito, owner no eliminable → 403, no miembro → 404.
   - **Integridad transaccional**: Group + membership creados juntos, owner aparece en list.

### Tabla de códigos de error nuevos

| Código | HTTP | Cuándo se dispara |
|---|---|---|
| `GROUP_NOT_FOUND` | 404 | `get_current_membership`: el group_id del path no corresponde a un grupo existente. |
| `NOT_GROUP_MEMBER` | 403 | `get_current_membership`: el usuario autenticado no tiene membresía en el grupo. |
| `FORBIDDEN_NOT_OWNER` | 403 | `require_owner`: la acción requiere rol `owner` pero el usuario tiene otro rol. |
| `FORBIDDEN_NOT_ADMIN` | 403 | `require_admin`: la acción requiere rol `owner` o `admin` pero el usuario es `member`. |
| `USER_NOT_FOUND_MUST_REGISTER` | 404 | `add_member`: el email no corresponde a ningún usuario registrado. |
| `ALREADY_MEMBER` | 409 | `add_member`: el usuario ya tiene una membresía en el grupo. |
| `CANNOT_MODIFY_OWNER` | 403 | `change_member_role` / `remove_member`: se intenta modificar o eliminar al `owner` del grupo. |

### Resultado real de `pytest tests/ -v`

```
$ pytest tests/ -v
81 passed, 8 warnings in 22.65s
```

- 21 tests de Capa 1 (test_models.py)
- 6 tests de Capa 1 — Postgres (test_postgres.py)
- 9 tests de Capa 2a (test_security.py)
- 10 tests de Capa 2b (test_auth.py)
- 8 tests de Capa 2c (test_users_me.py)
- 27 tests nuevos de Capa 3a (test_groups.py)

### Decisiones de diseño

1. **`get_current_membership` es dependency simple, no factory**: Se investigó el patrón "dependency factory" (`get_current_membership(group_id)`) y se descartó porque FastAPI lo evalúa una sola vez al definir la ruta, no por request. El patrón correcto es una dependency que recibe `group_id: int` como parámetro — FastAPI lo resuelve automáticamente del path param del endpoint. Se verificó con tests que `group_id` llega correcto.

2. **`flush()` en repository, `commit()` en service**: El repository hace `db.flush()` para que SQLAlchemy genere los IDs y las constraints se validen, pero no commitea. El service decide cuándo commitear (siempre al final de la operación). Esto permite transacciones atómicas (ej: crear grupo + membresía owner en la misma txn).

3. **No se acepta `role="owner"` desde el cliente**: `MemberAdd` y `MemberRoleUpdate` usan `Literal["admin", "member"]` en Pydantic. FastAPI retorna 422 si el cliente envía `"owner"`. Esto es defense-in-depth: aunque el service lo rechazaría, Pydantic lo bloquea antes.

4. **`my_role` se construye en el endpoint, no se almacena**: El schema `GroupResponse` incluye `my_role` pero no existe en la tabla `groups`. Se construye consultando `get_membership` en cada endpoint que retorna grupos. Esto mantiene la fuente de verdad en una sola tabla (`group_memberships.role`).

5. **Cleanup de tests con subquery**: La limpieza de tablas en los tests de groups usa subqueries para encontrar los groups creados por usuarios de prueba (ya que los group names no contienen `@groups-test`). El orden de DELETE es: memberships → groups (via subquery on created_by) → refresh_tokens → users.

6. **`get_user_by_id` reutilizado desde auth/repository.py**: No se creó un módulo separado de users para esta query. Se mantiene en auth/repository.py por ahora.

### Pendientes a propósito (no implementados en esta capa)

- **Invite codes / QR / join por código**: Queda para la siguiente sesión (Capa 3b). El modelo `GroupInviteCode` existe en `models.py` pero no se usa en esta capa.
- **`register` con `invite_code`**: Sigue fuera de scope.
- **Listado de miembros endpoint dedicado**: No se creó un `GET /groups/{id}/members` endpoint — los miembros se obtienen implícitamente al listar. Si se necesita, se agrega en la siguiente sesión.

### Preguntas abiertas

1. **¿Endpoint explícito `GET /groups/{id}/members`?** Actualmente no existe. El frontend puede obtener la lista de miembros necesaria de otras fuentes. ¿Se necesita para la UI de gestión de miembros?

2. **¿Transferir ownership?** ADR-002 dice "no hay transferencia de ownership en MVP". ¿Se mantiene así o se agrega un endpoint `PATCH /groups/{id}/transfer-ownership`?

3. **¿Soft-delete de grupos?** Actualmente el DELETE de membresía elimina al usuario del grupo pero no elimina el grupo. ¿Se necesita un `DELETE /groups/{id}` (solo owner) o se maneja por otro mecanismo?

4. **¿Rate limiting en endpoints de groups?** Los endpoints de members (add/remove/change role) podrían abusarse. ¿Agregar rate limiting o se maneja a nivel de UI?

### Archivos creados o modificados

```
backend/app/
├── core/
│   └── deps.py              (MODIFICADO — +get_current_membership, +require_owner, +require_admin)
├── groups/
│   ├── __init__.py           (sin cambios)
│   ├── models.py             (sin cambios)
│   ├── schemas.py            (NUEVO — GroupCreate, GroupUpdate, GroupResponse, MemberAdd, MemberRoleUpdate, MemberResponse)
│   ├── repository.py         (NUEVO — 10 queries)
│   ├── service.py            (NUEVO — GroupError + 4 funciones de negocio)
│   └── router.py             (NUEVO — 7 endpoints)
└── main.py                   (MODIFICADO — +groups_router)

backend/tests/
└── test_groups.py            (NUEVO — 27 tests de integración)
```

---

## 2026-08-28 — Capa 3b: Invite codes + QR + join + invite_code en register

### Qué se implementó, archivo por archivo

1. **`backend/pyproject.toml`** (modificado) — Agregada dependencia `qrcode[pil]>=8.0` al proyecto.

2. **`backend/requirements.txt`** (modificado) — Agregada dependencia `qrcode[pil]>=8.0`.

3. **`backend/app/groups/schemas.py`** (modificado) — Agregados 5 schemas:
   - `InviteCodeCreate`: `role_to_assign: Literal["admin", "member"]` (default `"member"`), `max_uses: int | None`, `expires_at: datetime | None`. Validator `never_owner` rechaza `"owner"` explícitamente.
   - `InviteCodeResponse`: `id`, `code`, `role_to_assign`, `max_uses`, `uses_count`, `expires_at`, `is_active`, `created_at`. `from_attributes=True`.
   - `JoinPreviewResponse`: `group_name: str`.
   - `JoinRequest`: `code: str`.
   - `JoinResponse`: `group_id`, `group_name`, `role`.

4. **`backend/app/groups/repository.py`** (modificado) — Agregadas 6 funciones:
   - `create_invite_code()`: INSERT con `db.flush()`.
   - `list_invite_codes()`: SELECT por `group_id`, ordenado por `created_at` DESC.
   - `get_invite_code_by_id()`: SELECT por `id` + `group_id` (aislamiento entre grupos).
   - `get_active_invite_code_by_code()`: SELECT por `code` + `is_active=True`, SIN filtro por `group_id` (el código es global, ADR-014).
   - `revoke_invite_code()`: SET `is_active=False`, retorna `None` si no existe.
   - `increment_invite_code_uses()`: UPDATE `uses_count = uses_count + 1`.

5. **`backend/app/groups/service.py`** (modificado) — Agregadas 7 funciones:
   - `_generate_unique_code()`: Genera 8 chars de `23456789ABCDEFGHJKMNPQRSTVWXYZ` usando `secrets.choice` (no `random`). Reintenta hasta 5 veces en caso de colisión.
   - `_is_code_valid()`: Valida expiración y max_uses. Reutilizada por preview y join.
   - `create_invite_code()`: Genera código único + INSERT + commit.
   - `list_invite_codes()`: Delega al repository.
   - `revoke_invite_code()`: Revoke + commit. 404 `INVITE_CODE_NOT_FOUND` si no existe.
   - `get_group_name_for_code()`: Valida vigencia del código, retorna nombre del grupo. 404 `INVALID_INVITE_CODE` si no válido.
   - `join_group_by_code()`: Valida código, crea membresía con `joined_via_invite_code_id`, incrementa `uses_count`. NO commitea (caller debe commitear). 404 `INVALID_INVITE_CODE` o 409 `ALREADY_MEMBER`.

6. **`backend/app/groups/router.py`** (modificado) — Agregados 6 endpoints:
   - `POST /groups/join` — autenticado, une al usuario actual vía código. Commit al final.
   - `GET /groups/join/preview` — público (sin auth), retorna nombre del grupo.
   - `POST /groups/{group_id}/invite-codes` — admin+, crea código.
   - `GET /groups/{group_id}/invite-codes` — admin+, lista códigos.
   - `PATCH /groups/{group_id}/invite-codes/{id}` — admin+, revoca código.
   - `GET /groups/{group_id}/invite-codes/{id}/qr` — admin+, genera PNG al vuelo con `qrcode`.
   - Rutas `/join` y `/join/preview` definidas ANTES de `/{group_id}` para evitar conflicto de path matching.

7. **`backend/app/auth/schemas.py`** (modificado) — Agregado `invite_code: str | None = None` a `RegisterRequest`.

8. **`backend/app/auth/repository.py`** (modificado) — Cambiados `create_user`, `create_refresh_token`, `revoke_refresh_token` de `db.commit()` a `db.flush()`. Esto permite que el commit ocurra al final del flujo en el service layer, haciendo posible la transacción atómica register+join.

9. **`backend/app/auth/service.py`** (modificado) — Modificada `register()` para aceptar `invite_code` opcional. Si viene, llama a `join_group_by_code()` después de crear el usuario. Si el join falla, `db.rollback()` revierte todo (usuario no queda huérfano). Commit al final del flujo completo. Agregado `db.commit()` a `authenticate()`, `refresh()`, `logout()` (antes lo hacía el repository).

10. **`backend/app/auth/router.py`** (modificado) — Pass `invite_code=body.invite_code` a `service.register()`.

11. **`backend/tests/test_invite_codes.py`** (nuevo) — 33 tests de integración con Postgres real.

### Tabla de códigos de error nuevos

| Código | HTTP | Cuándo se dispara |
|---|---|---|
| `INVALID_INVITE_CODE` | 404 | Código no existe, está inactivo, expirado, o agotado. Mismo código para todos los casos (no revela la diferencia). |
| `INVITE_CODE_NOT_FOUND` | 404 | `revoke_invite_code` / QR: el ID no corresponde a un código del grupo indicado. |
| `CODE_GENERATION_FAILED` | 500 | `_generate_unique_code`: colisión en los 5 reintentos (no debería pasar en la práctica). |

### Decisiones de diseño

1. **Código en claro (no hasheado)**: `group_invite_codes.code` se almacena y busca en texto plano. Es un código de compartir, no un secreto tipo refresh token. La entropía (32^8 ≈ 1.1 × 10^12) mitiga fuerza bruta sin necesidad de hash.

2. **Código globalmente único (no por grupo)**: `get_active_invite_code_by_code` NO filtra por `group_id`. Esto permite resolver el código sin conocer de antemano el grupo (simplifica el flujo de join/preview). Aislamiento entre grupos se mantiene en `get_invite_code_by_id` (para revoke/QR).

3. **Preview y join usan la misma función `_is_code_valid()`**: Lógica centralizada de validación de vigencia (expiración + max_uses), reutilizada sin duplicación.

4. **Transacción atómica register+join**: `auth/repository.py:create_user` y `create_refresh_token` cambiaron de `db.commit()` a `db.flush()`. El commit ocurre una sola vez al final de `register()`. Si `join_group_by_code()` falla, `db.rollback()` revierte el usuario también. No queda usuario huérfano.

5. **`/join` y `/join/preview` definidos antes de `/{group_id}`**: FastAPI resuelve rutas en orden de definición. Definir `/join` primero evita que `"join"` sea matcheado como `group_id` entero.

6. **QR generado al vuelo, sin persistencia**: Cada request a `/qr` genera el PNG en memoria (`io.BytesIO`) con `qrcode.make()`. No se guarda como archivo ni en DB.

7. **`role_to_assign` nunca `"owner"`**: Validado tanto en Pydantic (`Literal["admin", "member"]` + `field_validator`) como en DB (`CHECK (role_to_assign <> 'owner')`). Doble defensa.

### Resultado real de `pytest tests/ -v`

```
$ pytest tests/ -v
114 passed, 8 warnings in 31.78s
```

- 21 tests de Capa 1 (test_models.py)
- 6 tests de Capa 1 — Postgres (test_postgres.py)
- 9 tests de Capa 2a (test_security.py)
- 10 tests de Capa 2b (test_auth.py)
- 8 tests de Capa 2c (test_users_me.py)
- 27 tests de Capa 3a (test_groups.py)
- 33 tests nuevos de Capa 3b (test_invite_codes.py)

### Preguntas abiertas

1. **¿Rate limiting en `/groups/join` y `/auth/register` con `invite_code`?** ADR-014 lo recomienda (ADR-008, RNF-SEG-03) pero queda pendiente para una capa de hardening.

2. **¿Máximo de códigos activos por grupo?** Actualmente no hay límite. Un admin podría generar muchos códigos. ¿Agregar un tope razonable (ej: 10 activos)?

3. **¿Notificación al admin cuando alguien se une por código?** Actualmente no se notifica. ¿Email al owner/admin, o push notification?

4. **¿Código de un solo uso por defecto?** ADR-014 dice que `max_uses=NULL` es "código familiar reutilizable" (el caso típico). ¿Se mantiene así o se cambia el default a `max_uses=1`?

### Archivos creados o modificados

```
backend/
├── pyproject.toml                          (MODIFICADO — +qrcode[pil])
├── requirements.txt                        (MODIFICADO — +qrcode[pil])
├── app/
│   ├── auth/
│   │   ├── schemas.py                      (MODIFICADO — +invite_code en RegisterRequest)
│   │   ├── repository.py                   (MODIFICADO — flush en vez de commit en create_user, create_refresh_token, revoke_refresh_token)
│   │   ├── service.py                      (MODIFICADO — register() acepta invite_code, commit al final)
│   │   └── router.py                       (MODIFICADO — pass invite_code)
│   └── groups/
│       ├── schemas.py                      (MODIFICADO — +5 schemas de invite code)
│       ├── repository.py                   (MODIFICADO — +6 funciones de invite code)
│       ├── service.py                      (MODIFICADO — +7 funciones de invite code)
│       └── router.py                       (MODIFICADO — +6 endpoints)
└── tests/
    └── test_invite_codes.py                (NUEVO — 33 tests de integración)
```

---

## 2026-08-28 — Capa 3c: Categories + Payment Methods

### Qué se implementó, archivo por archivo

1. **`backend/app/categories/schemas.py`** (nuevo) — 2 schemas:
   - `CategoryCreate`: `name: str` (1-100 chars), `icon: str | None = None`.
   - `CategoryResponse`: `id`, `group_id` (nullable), `name`, `icon`, `is_system: bool`, `created_at`. `from_attributes=True`.

2. **`backend/app/categories/repository.py`** (nuevo) — 3 funciones:
   - `list_categories_for_group()`: Una sola query con `OR` que trae categorías de sistema (`group_id IS NULL`) + personalizadas del grupo (`group_id = group_id`). Ordenado por `group_id NULLS FIRST, name`.
   - `create_category()`: INSERT con `db.flush()`.
   - `get_category_by_name_in_group()`: SELECT por `group_id + name` para detectar duplicados antes del CHECK de DB.

3. **`backend/app/categories/service.py`** (nuevo) — `CategoryError` + 2 funciones:
   - `list_categories()`: Delega al repository.
   - `create_category()`: Verifica duplicado → 409 `CATEGORY_NAME_ALREADY_EXISTS`. Crea + commit.

4. **`backend/app/categories/router.py`** (nuevo) — 2 endpoints:
   - `GET /groups/{group_id}/categories` — cualquier miembro puede listar.
   - `POST /groups/{group_id}/categories` — admin+ para crear.

5. **`backend/app/payment_methods/schemas.py`** (nuevo) — 3 schemas:
   - `PaymentMethodCreate`: `kind`, `provider_name`, `label`, `last4`, `masked_key`, `holder_name`. Incluye `model_validator(mode="after")` que replica el CHECK `chk_payment_method_reference` de la DB (4 casos: CASH, bank/debit/credit, wallet/bre-b/pse, OTHER). Validación adicional: `last4` debe ser exactamente 4 dígitos, `masked_key` máx 20 chars.
   - `PaymentMethodUpdate`: `label: str | None`, `is_active: bool | None` — solo campos opcionales, NO permite cambiar `kind`.
   - `PaymentMethodResponse`: todos los campos del modelo. `from_attributes=True`.

6. **`backend/app/payment_methods/repository.py`** (nuevo) — 4 funciones:
   - `list_payment_methods_for_group()`: SELECT por `group_id`, ordenado por `created_at DESC`.
   - `create_payment_method()`: INSERT con `db.flush()`.
   - `get_payment_method_by_id()`: SELECT por `id + group_id` (aislamiento entre grupos).
   - `update_payment_method()`: Actualiza campos dinámicamente con `setattr`. Retorna `None` si no existe.

7. **`backend/app/payment_methods/service.py`** (nuevo) — `PaymentMethodError` + 3 funciones:
   - `list_payment_methods()`: Delega al repository.
   - `create_payment_method()`: Crea + commit.
   - `update_payment_method()`: Actualiza + commit. 404 `PAYMENT_METHOD_NOT_FOUND` si no existe o pertenece a otro grupo.

8. **`backend/app/payment_methods/router.py`** (nuevo) — 3 endpoints:
   - `GET /groups/{group_id}/payment-methods` — cualquier miembro puede listar.
   - `POST /groups/{group_id}/payment-methods` — admin+ para crear.
   - `PATCH /groups/{group_id}/payment-methods/{id}` — admin+ para actualizar.

9. **`backend/app/main.py`** (modificado) — Agregados `categories_router` y `payment_methods_router` con prefijo `/api/v1`.

10. **`backend/tests/test_categories.py`** (nuevo) — 10 tests de integración.

11. **`backend/tests/test_payment_methods.py`** (nuevo) — 22 tests de integración.

### Tabla de códigos de error nuevos

| Código | HTTP | Cuándo se dispara |
|---|---|---|
| `CATEGORY_NAME_ALREADY_EXISTS` | 409 | `create_category`: ya existe una categoría con ese nombre en el grupo. |
| `PAYMENT_METHOD_NOT_FOUND` | 404 | `update_payment_method`: el ID no corresponde a un medio de pago del grupo indicado. |
| `EMPTY_UPDATE` | 422 | `update_payment_method`: el body del PATCH está vacío (sin campos a actualizar). |

### Decisiones de diseño

1. **Routers separados con `prefix` en `main.py`**: Se crearon `categories/router.py` y `payment_methods/router.py` como módulos independientes, cada uno con su propio `APIRouter(prefix="/groups/{group_id}/...")`. Se montan en `main.py` con `app.include_router(..., prefix="/api/v1")`. FastAPI resuelve `group_id` correctamente del path param cuando viene del prefijo del router — verificado con tests reales.

2. **Pydantic validator replica CHECK de DB**: `PaymentMethodCreate.model_validator(mode="after")` valida los 4 casos del CHECK `chk_payment_method_reference` antes de tocar la DB. Esto devuelve un 422 claro con mensaje descriptivo en vez de un 500 genérico por `IntegrityError`. Se validan también longitudes: `last4` exactamente 4 dígitos, `masked_key` máx 20 chars.

3. **`is_system` como propiedad, no campo**: El schema `CategoryResponse` incluye `is_system: bool` que se deriva de `group_id IS NULL` (propiedad `@property` en el modelo). No es un campo存储ado en la DB — es un `GENERATED ALWAYS AS` column en PostgreSQL.

4. **`PaymentMethodUpdate` no permite cambiar `kind`**: Si el tipo está mal, se crea uno nuevo y se desactiva el viejo (más simple que re-validar el CHECK completo en un PATCH parcial). Solo se permite cambiar `label` e `is_active`.

### Resultado real de `pytest tests/ -v`

```
$ pytest tests/ -v
146 passed, 8 warnings in 43.96s
```

- 21 tests de Capa 1 (test_models.py)
- 6 tests de Capa 1 — Postgres (test_postgres.py)
- 9 tests de Capa 2a (test_security.py)
- 10 tests de Capa 2b (test_auth.py)
- 8 tests de Capa 2c (test_users_me.py)
- 27 tests de Capa 3a (test_groups.py)
- 33 tests de Capa 3b (test_invite_codes.py)
- 10 tests nuevos de Capa 3c (test_categories.py)
- 22 tests nuevos de Capa 3c (test_payment_methods.py)

### Preguntas abiertas

1. **¿Soft-delete de categorías personalizadas?** Actualmente se crean pero no se pueden desactivar ni borrar. ¿Se necesita un `DELETE /groups/{group_id}/categories/{id}` (admin+) o se mantiene simple?

2. **¿Endpoints de categorías del sistema?** No hay endpoint para listar/crear categorías de sistema (son seed data). ¿Se necesita un admin panel que las gestione, o se mantiene fijo en `seed.sql`?

3. **¿Límite de medios de pago por grupo?** Actualmente no hay límite. ¿Agregar un tope razonable?

4. **¿Endpoint `DELETE /groups/{group_id}/payment-methods/{id}`?** Actualmente solo se puede desactivar (`is_active=false`). ¿Se necesita borrado físico o el soft-delete es suficiente?

5. **¿Filtros en listados?** Los GET actuales no tienen paginación ni filtros. ¿Se necesita `?kind=` para filtrar por tipo de medio de pago, o `?is_active=` para filtrar solo activos?

### Archivos creados o modificados

```
backend/
├── app/
│   ├── categories/
│   │   ├── __init__.py                 (sin cambios)
│   │   ├── models.py                   (sin cambios)
│   │   ├── schemas.py                  (NUEVO — CategoryCreate, CategoryResponse)
│   │   ├── repository.py               (NUEVO — 3 queries)
│   │   ├── service.py                  (NUEVO — CategoryError + 2 funciones)
│   │   └── router.py                   (NUEVO — 2 endpoints)
│   ├── payment_methods/
│   │   ├── __init__.py                 (sin cambios)
│   │   ├── models.py                   (sin cambios)
│   │   ├── schemas.py                  (NUEVO — PaymentMethodCreate con validator, PaymentMethodUpdate, PaymentMethodResponse)
│   │   ├── repository.py               (NUEVO — 4 queries)
│   │   ├── service.py                  (NUEVO — PaymentMethodError + 3 funciones)
│   │   └── router.py                   (NUEVO — 3 endpoints)
│   └── main.py                         (MODIFICADO — +categories_router, +payment_methods_router)
└── tests/
    ├── test_categories.py              (NUEVO — 10 tests de integración)
    └── test_payment_methods.py         (NUEVO — 22 tests de integración)
```

---

## 2026-08-28 — Capa 3d: Obligations + generación de Periods

### Qué se implementó, archivo por archivo

1. **`backend/app/obligations/schemas.py`** (nuevo) — 4 schemas:
   - `ObligationCreate`: campos de la tabla excepto `id`, `group_id`, `created_at`, `updated_at`. `model_validator` valida: `due_month` obligatorio solo para ANNUAL, `end_date >= start_date`.
   - `ObligationUpdate`: todos los campos opcionales con validación cruzada (si cambia periodicity a ANNUAL sin due_month → 422). Usa sentinel `"unset"` para distinguir "no envió el campo" de "quiere ponerlo en null".
   - `ObligationResponse`: todos los campos del modelo. `from_attributes=True`.
   - `ObligationPeriodResponse`: `id`, `obligation_id`, `period_month`, `due_date`, `status`, `created_at`.

2. **`backend/app/obligations/repository.py`** (nuevo) — 10 funciones:
   - CRUD de obligaciones: `create_obligation`, `get_obligation_by_id`, `list_obligations_for_group`, `update_obligation`, `deactivate_obligation`.
   - Periods: `list_periods_for_group` (JOIN con Obligation para filtro por group_id, filtros opcionales por status y month), `get_period_by_id`, `get_periods_for_obligation`, `upsert_period` (busca primero, inserta si no existe), `update_period_status`.

3. **`backend/app/obligations/service.py`** (nuevo) — `ObligationError` + funciones centrales:
   - `_last_day_of_month`, `_compute_due_date` (clamping), `_months_interval_for_periodicity`.
   - `generate_periods_for_obligation`: generación lazy con `zoneinfo.ZoneInfo("America/Bogota")`, maneja MONTHLY/BIMONTHLY/QUARTERLY/SEMIANNUAL (iteración con saltos) y ANNUAL (iteración por año en due_month). Actualiza PENDIENTE → VENCIDO para períodos vencidos.
   - `_validate_category`, `_validate_payment_method`, `_validate_responsible`: validación pre-DB de FKs compuestas.
   - CRUD delegado: `create_obligation` (valida + genera períodos + commit), `list_obligations`, `get_obligation`, `update_obligation` (valida relaciones si cambian), `deactivate_obligation`.
   - Periods: `list_periods` (regenera para todas las obligaciones activas, luego consulta), `get_period`.

4. **`backend/app/obligations/router.py`** (nuevo) — 7 endpoints:
   - `POST /groups/{group_id}/obligations` — admin+.
   - `GET /groups/{group_id}/obligations` — cualquier miembro.
   - `GET /groups/{group_id}/obligations/{id}` — cualquier miembro.
   - `PATCH /groups/{group_id}/obligations/{id}` — admin+.
   - `DELETE /groups/{group_id}/obligations/{id}` — admin+, soft-delete.
   - `GET /groups/{group_id}/periods` — cualquier miembro, filtros `?status=` y `?month=`.
   - `GET /groups/{group_id}/periods/{id}` — cualquier miembro.

5. **`backend/app/main.py`** (modificado) — Agregados `obligations_router` y `periods_router` con prefijo `/api/v1`.

6. **`backend/tests/test_obligations.py`** (nuevo) — 24 tests de integración con Postgres real.

7. **`backend/tests/test_periods.py`** (nuevo) — 18 tests de integración con Postgres real.

### Tabla de códigos de error nuevos

| Código | HTTP | Cuándo se dispara |
|---|---|---|
| `OBLIGATION_NOT_FOUND` | 404 | `get_obligation` / `update_obligation` / `deactivate_obligation`: el ID no corresponde a una obligación del grupo indicado. |
| `CATEGORY_NOT_IN_GROUP` | 400 | `create_obligation` / `update_obligation`: la `category_id` pertenece a otro grupo (no es de sistema ni del grupo actual). |
| `PAYMENT_METHOD_NOT_IN_GROUP` | 400 | `create_obligation` / `update_obligation`: el `payment_method_id` pertenece a otro grupo. |
| `RESPONSIBLE_NOT_GROUP_MEMBER` | 400 | `create_obligation` / `update_obligation`: el `responsible_user_id` no es miembro del grupo. |
| `PERIOD_NOT_FOUND` | 404 | `get_period`: el ID no corresponde a un período de una obligación del grupo indicado. |
| `EMPTY_UPDATE` | 422 | `update_obligation`: el body del PATCH está vacío (sin campos a actualizar). |

### Lógica de generación de períodos — ejemplo concreto

**Obligación de ejemplo:**
- `name`: "Internet mensual"
- `periodicity`: MONTHLY
- `due_day`: 15
- `start_date`: 2026-06-01
- `end_date`: null (indefinida)
- Creación: 2026-08-28

**Resultado de generación (hoy = 2026-08-28):**

| period_month | due_date | status |
|---|---|---|
| 2026-06-01 | 2026-06-15 | VENCIDO |
| 2026-07-01 | 2026-07-15 | VENCIDO |
| 2026-08-01 | 2026-08-15 | VENCIDO |
| 2026-09-01 | 2026-09-15 | PENDIENTE |

**Cálculo:**
- Límite superior = mes actual (agosto) + 1 = septiembre 2026
- Límite inferior = start_date = junio 2026
- Iteración: jun → jul → ago → sep (cada 1 mes), 4 períodos
- Clamping: due_day=15 existe en todos esos meses (no se aplica)
- Status: due_date < hoy (2026-08-28) → VENCIDO; due_date >= hoy → PENDIENTE

**Ejemplo con ANNUAL:**
- `periodicity`: ANNUAL, `due_day`: 15, `due_month`: 3, `start_date`: 2024-01-01
- Genera un período por año: 2024-03-01, 2025-03-01, 2026-03-01 (hasta mes actual+1)

**Ejemplo con clamping (due_day=31 en febrero):**
- `periodicity`: MONTHLY, `due_day`: 31, `start_date`: 2026-02-01
- Para febrero 2026: `_compute_due_date(2026, 2, 31)` → `min(31, 28)` = 28 → `due_date = 2026-02-28`

### Resultado real de `pytest tests/ -v`

```
$ pytest tests/ -v
188 passed, 8 warnings in 59.19s
```

- 21 tests de Capa 1 (test_models.py)
- 6 tests de Capa 1 — Postgres (test_postgres.py)
- 9 tests de Capa 2a (test_security.py)
- 10 tests de Capa 2b (test_auth.py)
- 8 tests de Capa 2c (test_users_me.py)
- 27 tests de Capa 3a (test_groups.py)
- 33 tests de Capa 3b (test_invite_codes.py)
- 10 tests de Capa 3c (test_categories.py)
- 22 tests de Capa 3c (test_payment_methods.py)
- 24 tests nuevos de Capa 3d (test_obligations.py)
- 18 tests nuevos de Capa 3d (test_periods.py)

### Decisiones de diseño

1. **Generación lazy, no cron**: Se confirma la decisión de ADR-003. No hay job en background. La función `generate_periods_for_obligation` se llama (a) al crear una obligación y (b) al listar períodos de un grupo. Esto garantiza que los períodos existan cuando el frontend los necesite, sin infraestructura adicional.

2. **`zoneinfo.ZoneInfo("America/Bogota")`**: El cálculo de "hoy" para determinar VENCIDO usa `datetime.now(ZoneInfo("America/Bogota")).date()` en Python, no depende del timezone del servidor Postgres ni del sistema operativo. Esto es consistente con ADR-011 #4.

3. **Clamping de `due_day`**: `min(due_day, calendar.monthrange(year, month)[1])` — exactamente como especifica ADR-011 #5. Verificado con febrero (28 días) y abril (30 días) en tests.

4. **`ANNUAL` genera UN período por año**: La iteración salta de `due_month` en `due_month`, no de mes en mes. Verificado que todos los `period_month` corresponden al mes `due_month`.

5. **Idempotencia del upsert**: `upsert_period` busca primero por `(obligation_id, period_month)` UNIQUE, solo inserta si no existe. Llamar `list_periods` dos veces seguidas no duplica filas — verificado con `COUNT(*)` directo en DB.

6. **Actualización de VENCIDO**: Después de generar períodos faltantes, la función itera todos los períodos existentes de la obligación y actualiza a `VENCIDO` los que estén en `PENDIENTE` pero cuyo `due_date < hoy`.

7. **Validación pre-DB de FKs compuestas**: `_validate_category`, `_validate_payment_method` y `_validate_responsible` verifican ANTES de tocar la DB que las referencias pertenezcan al grupo correcto. Esto evita `IntegrityError` 500 por la FK compuesta DEFERRABLE.

8. **Soft-delete**: `deactivate_obligation` solo hace `is_active=False`, nunca `db.delete()`. La fila permanece en DB.

9. **Filtro `month` compara DATE, no STRING**: El repository parsea `"YYYY-MM"` a `date(year, month, 1)` antes de comparar con `period_month` (columna DATE). Comparar un string contra una columna DATE en PostgreSQL puede causar 500s por casting implícito.

### Preguntas abiertas

1. **¿PATCH de obligación debería regenerar períodos futuros?** Actualmente, si se cambia `periodicity`, `due_day` o `start_date` via PATCH, los períodos futuros ya generados quedan con los valores viejos. No se regeneran. **Pregunta**: ¿debería el PATCH eliminar/regenerar períodos futuros ( Pendientes) cuando cambian estos campos críticos? No está especificado en los ADR. No se implementó en esta capa.

2. **¿Regenerar períodos si se cambia `end_date`?** Similar al punto anterior: si se acorta el `end_date`, los períodos generados más allá de la nueva fecha quedarían huérfanos. ¿Eliminarlos o dejarlos?

3. **¿Límite de obligation_periods por obligación?** Actualmente no hay tope. Una obligación MONTHLY desde 2020 podría generar 70+ períodos. ¿Se necesita un límite razonable?

4. **¿Filtros adicionales en listado de periods?** El ADR-004 define `?status=` y `?month=`. ¿Se necesita `?obligation_id=` para filtrar por obligación específica?

### Archivos creados o modificados

```
backend/
├── app/
│   └── obligations/
│       ├── __init__.py                 (sin cambios)
│       ├── models.py                   (sin cambios)
│       ├── schemas.py                  (NUEVO — ObligationCreate, ObligationUpdate, ObligationResponse, ObligationPeriodResponse)
│       ├── repository.py               (NUEVO — 10 queries)
│       ├── service.py                  (NUEVO — ObligationError + generación de períodos + CRUD)
│       └── router.py                   (NUEVO — 7 endpoints)
│   └── main.py                         (MODIFICADO — +obligations_router, +periods_router)
└── tests/
    ├── test_obligations.py             (NUEVO — 24 tests de integración)
    └── test_periods.py                 (NUEVO — 18 tests de integración)
```

---

## 2026-08-29 — Capa 3d (corrección): off-by-one en límite de generación de períodos

### Bug identificado

**Síntoma**: Las obligaciones creadas no generaban el período del "mes actual + 1" en ciertas condiciones. Ejemplo: obligación MONTHLY con `start_date=2026-06-01`, hoy=2026-08-29 → debería generar 4 períodos (jun, jul, ago, sep) pero solo generaba 3.

**Causa raíz**: Operador `>=` en la condición de corte de la iteración en `generate_periods_for_obligation` (service.py). El `>=` descartaba el período del mes límite (hoy + 1), que es exactamente el que se debe generar.

**Dónde**:
- `backend/app/obligations/service.py`, línea ~99 (rama no-ANNUAL): `if period_month >= limit_date: break` → `if period_month > limit_date: break`
- `backend/app/obligations/service.py`, línea ~119 (rama ANNUAL): misma corrección
- `backend/tests/test_periods.py`, función `_period_count`, línea ~46: mismo bug en el helper de tests (`>=` → `>`). Esto explicaba por qué los tests existentes pasaban a pesar del bug: el test oracle compartía la misma equivocación que la implementación.

### Qué se corrigió

1. **`backend/app/obligations/service.py`** — Cambiado `>=` → `>` en ambas ramas de `generate_periods_for_obligation` (no-ANNUAL y ANNUAL). El período del mes actual+1 ahora se genera correctamente.

2. **`backend/tests/test_periods.py`** — Corregido `_period_count` helper: `>=` → `>`. Ahora el helper mide correctamente la cantidad de períodos esperados.

3. **`backend/tests/test_periods.py`** — Nuevo test `test_next_month_period_is_generated_in_advance`:
   - Crea una obligación MONTHLY cuyo start_date es 2 meses atrás de hoy
   - Verifica que el período del mes siguiente (hoy + 1) existe en la respuesta con status `PENDIENTE`
   - El test filtra por `obligation_id` y verifica la fecha concreta del período, no una fórmula paralela

### Resultado real de `pytest tests/ -v`

```
$ pytest tests/ -v
189 passed, 8 warnings in 53.64s
```

- 18 tests de Capa 3d (test_periods.py) + 1 nuevo = 19 tests de períodos
- Total: 189 tests (188 anteriores + 1 nuevo)

### Lección aprendida

**El test oracle compartió el mismo bug que la implementación.** La función helper `_period_count` usaba la misma lógica `>=` que `generate_periods_for_obligation`, por lo que siempre producía el mismo resultado incorrecto. Los tests pasaban porque "esperaban" el mismo valor erróneo que se generaba. Solución: el nuevo test verifica el período del mes siguiente por su fecha concreta (`expected_next_period_month`), no por una fórmula paralela que pudiera replicar el bug.

### Archivos modificados

```
backend/
├── app/obligations/
│   └── service.py          (MODIFICADO — >= → > en dos ramas)
└── tests/
    └── test_periods.py     (MODIFICADO — _period_count corregido + nuevo test)
```

---

## 2026-08-29 — Capa 3e: Payments (registrar + anular)

### Qué se implementó, archivo por archivo

1. **`backend/app/core/deps.py`** (modificado) — Nueva función de autorización:
   - `require_admin_or_responsible(membership, responsible_user_id, current_user)`: Permite owner/admin, pero también a un `member` si `obligation.responsible_user_id == current_user.id`. Diferente al patrón `require_admin` que se usa en otros módulos — aquí el member SÍ puede escribir, pero solo si es el responsable de la obligación.
   - Agregado `TYPE_CHECKING` import para evitar circular imports con `User`.

2. **`backend/app/obligations/models.py`** (modificado) — Agregada relationship `obligation` a `ObligationPeriod`:
   - `obligation: Mapped[Optional["Obligation"]] = relationship("Obligation", ..., viewonly=True)`.
   - Permite acceder a `period.obligation` para obtener la obligación asociada sin queries separadas.

3. **`backend/app/payments/schemas.py`** (nuevo) — 2 schemas:
   - `PaymentCreate`: `amount_cents` (int >= 0), `currency` (Literal["COP", "USD"]), `paid_at` (date), `notes` (str | None), `receipt_url` (str | None).
   - `PaymentResponse`: todos los campos del modelo Payment. `from_attributes=True`.

4. **`backend/app/payments/repository.py`** (nuevo) — 4 funciones:
   - `create_payment()`: INSERT con `db.flush()`.
   - `get_payment_by_id()`: SELECT con JOIN a través de `obligation_period_id → ObligationPeriod → Obligation` filtrando por `Obligation.group_id` (mismo patrón de aislamiento que en otros módulos).
   - `list_payments_for_group()`: Mismo tipo de JOIN, ordenado por `paid_at DESC`. Retorna TODOS los pagos (incluidos los voided).
   - `void_payment()`: UPDATE `payments SET voided_at = now(), voided_by_user_id = :id WHERE id = :id`. **Es el ÚNICO lugar del código que toca una fila de payments después de creada**, y solo esas dos columnas.

5. **`backend/app/payments/service.py`** (nuevo) — `PaymentError` + 4 funciones:
   - `_period_status_for_due_date(due_date, today)`: Reutiliza la lógica `"VENCIDO" if due_date < today else "PENDIENTE"` de obligations/service.py (misma lógica, centralizada).
   - `register_payment()`: Busca período (404 PERIOD_NOT_FOUND), valida status (409 PERIOD_ALREADY_PAID), valida moneda (400 CURRENCY_MISMATCH), crea Payment + actualiza period a PAGADO en la misma transacción, commit al final.
   - `void_payment()`: Busca pago (404 PAYMENT_NOT_FOUND), valida si ya está anulado (409 PAYMENT_ALREADY_VOIDED), marca voided_at/voided_by_user_id, recalcula status del período con `_period_status_for_due_date` usando timezone America/Bogota, commit.
   - `list_payments()`: Delega al repository.

6. **`backend/app/payments/router.py`** (nuevo) — 3 endpoints:
   - `POST /groups/{group_id}/periods/{period_id}/payments`: Usa `get_current_membership` + `get_current_user`, obtiene período y su obligación, llama `require_admin_or_responsible(membership, obligation.responsible_user_id, current_user)`, luego `service.register_payment()`. Status 201.
   - `GET /groups/{group_id}/payments`: `Depends(get_current_membership)` solamente (cualquier miembro puede ver historial).
   - `POST /groups/{group_id}/payments/{payment_id}/void`: Mismo patrón de autorización que registrar (obtiene la obligación del pago para verificar responsabilidad).

7. **`backend/app/main.py`** (modificado) — Agregados `payments_router` y `period_payments_router` con prefijo `/api/v1`.

8. **`backend/tests/test_payments.py`** (nuevo) — 17 tests de integración con Postgres real.

### Tabla de códigos de error nuevos

| Código | HTTP | Cuándo se dispara |
|---|---|---|
| `PERIOD_NOT_FOUND` | 404 | `register_payment`: el period_id no corresponde a un período del grupo indicado. |
| `PERIOD_ALREADY_PAID` | 409 | `register_payment`: el período ya tiene un pago activo (voided_at IS NULL). Corrección = anular primero. |
| `CURRENCY_MISMATCH` | 400 | `register_payment`: la moneda del pago no coincide con la de la obligación asociada. |
| `OBLIGATION_NOT_FOUND` | 404 | `register_payment`: la obligación asociada al período no existe (defensivo, no debería ocurrir). |
| `PAYMENT_NOT_FOUND` | 404 | `void_payment` / authorization: el payment_id no corresponde a un pago del grupo indicado. |
| `PAYMENT_ALREADY_VOIDED` | 409 | `void_payment`: el pago ya tiene `voided_at` seteado. |
| `FORBIDDEN_NOT_RESPONSIBLE` | 403 | `require_admin_or_responsible`: el usuario es member pero no es el responsable de la obligación. |

### Decisiones de diseño

1. **Relationship `ObligationPeriod.obligation`**: Agregada una relationship `viewonly=True` al modelo `ObligationPeriod` para acceder a la obligación asociada. Se eligió esta approach sobre una query separada porque: (a) es más simple y consistente con el patrón ya usado en `Obligation.responsible`; (b) evita duplicar la lógica de JOIN del repository; (c) SQLAlchemy maneja el lazy loading correctamente dentro de la misma sesión.

2. **`require_admin_or_responsible` como función, no dependency**: Al igual que `require_owner` y `require_admin`, es una función normal que se llama dentro del router después de obtener la obligación. No es una dependency de FastAPI porque necesita datos (la obligación) que solo están disponibles después de la query al período.

3. **Dos routers separados**: `period_payments_router` (para `POST .../periods/{id}/payments`) y `router` (para `GET .../payments` y `POST .../payments/{id}/void`). Esto permite montar rutas bajo `/periods` y `/payments` sin conflictos de path matching, igual que se hizo con `periods_router` y `obligations_router`.

4. **Authorization doble check en void**: El router hace un pre-check de autorización (obtiene la obligación del pago para verificar `responsible_user_id`) ANTES de llamar al service. Esto es consistente con el patrón de register: la autorización se verifica en el router, la lógica de negocio en el service.

5. **Validación de moneda antes de tocar la DB**: `CURRENCY_MISMATCH` se verifica ANTES del INSERT del pago, usando la relationship `period.obligation.currency`. Si la moneda no coincide, no se toca la DB.

6. **`_period_status_for_due_date` reutiliza la lógica de obligations**: La fórmula `"VENCIDO" if due_date < today else "PENDIENTE"` es idéntica a la que usa `generate_periods_for_obligation`. Se centralizó en esta función en vez de duplicarla. Se usa `datetime.now(ZoneInfo("America/Bogota")).date()` para "hoy", consistente con ADR-011 #4.

### Resultado real de `pytest tests/ -v`

```
$ .venv/bin/pytest tests/ -v
206 passed, 8 warnings in 60.68s
```

- 189 tests de capas anteriores (todavía pasando)
- 17 tests nuevos de Capa 3e (test_payments.py):
  - TestRegisterPayment: 7 tests (owner, admin, responsible member, non-responsible forbidden, already paid, currency mismatch, other group period)
  - TestListPayments: 4 tests (empty, includes created, includes voided, requires membership)
  - TestVoidPayment: 6 tests (sets voided_at, overdue→VENCIDO, future→PENDIENTE, already voided, other group, full correction flow pay→void→repay)

### Archivos creados o modificados

```
backend/
├── app/
│   ├── core/
│   │   └── deps.py              (MODIFICADO — +require_admin_or_responsible)
│   ├── obligations/
│   │   └── models.py            (MODIFICADO — +relationship "obligation" en ObligationPeriod)
│   ├── payments/
│   │   ├── __init__.py          (sin cambios)
│   │   ├── models.py            (sin cambios)
│   │   ├── schemas.py           (NUEVO — PaymentCreate, PaymentResponse)
│   │   ├── repository.py        (NUEVO — 4 queries)
│   │   ├── service.py           (NUEVO — PaymentError + 4 funciones)
│   │   └── router.py            (NUEVO — 3 endpoints)
│   └── main.py                  (MODIFICADO — +payments_router, +period_payments_router)
└── tests/
    └── test_payments.py         (NUEVO — 17 tests de integración)
```

### Preguntas abiertas

1. **¿Audit logging en pagos?** Actualmente no se registra en `audit_logs` cuando se crea o anula un pago. ADR-008 lo recomienda pero queda pendiente para la capa de auditoría.

2. **¿Notificación al anular un pago?** No se notifica a nadie cuando se anula un pago. ¿Se necesita notificar al owner/admin?

3. **¿Límite de pagos por período?** Actualmente no hay tope, pero la lógica de negocio lo limita a 1 pago activo por período (PERIOD_ALREADY_PAID). ¿Se necesita un límite adicional?

4. **¿Endpoint de detalle de pago?** Actualmente no hay `GET /groups/{group_id}/payments/{id}`. ¿Se necesita para ver el detalle de un pago específico?

---

## 2026-08-29 — Capa 3f: Dashboard

### Qué se implementó, archivo por archivo

1. **`backend/app/payments/repository.py`** (corrección) — Housekeeping: `void_payment()` usaba `datetime.now()` (naive) en vez de `datetime.now(timezone.utc)` para la columna `voided_at TIMESTAMPTZ`. Agregado `timezone` al import de `datetime`. Consistente con todo el resto del códigobase.

2. **`backend/app/obligations/service.py`** (modificado) — Extraída función compartida:
   - `_ensure_periods_generated_for_group(db, group_id)`: Itera obligaciones activas del grupo y llama `generate_periods_for_obligation` para cada una. Reutilizada por `list_periods` (que antes duplicaba este loop) y por el nuevo dashboard service.

3. **`backend/app/dashboard/__init__.py`** (nuevo) — Init de paquete vacío.

4. **`backend/app/dashboard/schemas.py`** (nuevo) — 3 schemas Pydantic:
   - `CurrencyTotal`: `currency`, `total_cents`, `paid_cents`, `pending_cents`.
   - `UpcomingPeriod`: `period_id`, `obligation_id`, `obligation_name`, `due_date`, `expected_amount_cents`, `currency`.
   - `DashboardResponse`: `month`, `totals: list[CurrencyTotal]`, `vencen_esta_semana: list[UpcomingPeriod]`.

5. **`backend/app/dashboard/repository.py`** (nuevo) — 3 queries de agregación SQL (func.sum + GROUP BY):
   - `get_totals_by_currency(db, group_id, month_date)`: `SELECT Obligation.currency, SUM(Obligation.expected_amount_cents) ... GROUP BY currency` con JOIN `ObligationPeriod → Obligation`, filtrado por `period_month == month_date`, `group_id`, `is_active=True`.
   - `get_paid_by_currency(db, group_id, month_date)`: `SELECT Obligation.currency, SUM(Payment.amount_cents) ... GROUP BY currency` con JOIN `Payment → ObligationPeriod → Obligation`, mismos filtros + `Payment.voided_at IS NULL`.
   - `get_upcoming_periods(db, group_id, today, week_end)`: Periods PENDIENTE con `due_date BETWEEN today AND today+6`, JOIN a Obligation para traer `obligation_name` en la misma query (sin N+1). Ordenado por `due_date ASC`.

6. **`backend/app/dashboard/service.py`** (nuevo) — `get_dashboard(db, group_id, month_str)`:
   - Resuelve mes: si `month_str` es None → mes actual en `America/Bogota`; si viene → parsea `YYYY-MM` con regex, valida rango (1-12), retorna 422 si inválido.
   - Llama `_ensure_periods_generated_for_group` antes de agregar.
   - Junta `get_totals_by_currency` + `get_paid_by_currency` en un dict por moneda, calcula `pending_cents = total - paid`.
   - Calcula ventana `vencen_esta_semana`: `today = datetime.now(BOGOTA).date()`, `week_end = today + timedelta(days=6)`.
   - Independiente de `?month=`: upcoming siempre es "próximos 7 días desde hoy".

7. **`backend/app/dashboard/router.py`** (nuevo) — 1 endpoint:
   - `GET /groups/{group_id}/dashboard?month=YYYY-MM`: `Depends(get_current_membership)` (cualquier miembro). ValueError → 422 `INVALID_MONTH_FORMAT`.

8. **`backend/app/main.py`** (modificado) — Agregado `dashboard_router` con prefijo `/api/v1`.

9. **`backend/tests/test_dashboard.py`** (nuevo) — 14 tests de integración con Postgres real.

### Queries SQL exactas (equivalente SQLAlchemy)

**total_cents por moneda:**
```sql
SELECT obligations.currency, SUM(obligations.expected_amount_cents) AS total_cents
FROM obligation_periods
JOIN obligations ON obligation_periods.obligation_id = obligations.id
WHERE obligation_periods.period_month = :month_date
  AND obligations.group_id = :group_id
  AND obligations.is_active = TRUE
GROUP BY obligations.currency;
```

**paid_cents por moneda:**
```sql
SELECT obligations.currency, SUM(payments.amount_cents) AS paid_cents
FROM payments
JOIN obligation_periods ON payments.obligation_period_id = obligation_periods.id
JOIN obligations ON obligation_periods.obligation_id = obligations.id
WHERE obligation_periods.period_month = :month_date
  AND obligations.group_id = :group_id
  AND obligations.is_active = TRUE
  AND payments.voided_at IS NULL
GROUP BY obligations.currency;
```

**vencen_esta_semana:**
```sql
SELECT obligation_periods.id AS period_id, obligations.id AS obligation_id,
       obligations.name AS obligation_name, obligation_periods.due_date,
       obligations.expected_amount_cents, obligations.currency
FROM obligation_periods
JOIN obligations ON obligation_periods.obligation_id = obligations.id
WHERE obligation_periods.status = 'PENDIENTE'
  AND obligation_periods.due_date >= :today
  AND obligation_periods.due_date <= :week_end
  AND obligations.group_id = :group_id
  AND obligations.is_active = TRUE
ORDER BY obligation_periods.due_date ASC;
```

### Decisiones de diseño

1. **Agregación en SQL, no en Python**: Consistente con ADR-004 ("evita traer todas las filas y sumarlas en memoria"). Se usa `func.sum()` + `GROUP BY currency` directamente en SQLAlchemy.

2. **Sin conversión de monedas**: Consistente con ADR-011 #6. Si el grupo tiene COP y USD, retorna dos entradas en `totals`. El frontend renderiza una sección por moneda.

3. **`vencen_esta_semana` independiente de `?month=`**: El filtro de "próximos 7 días" es siempre relativo a "hoy" (Bogotá), no al mes consultado. Son conceptos independientes según el ADR-004.

4. **Períodos VENCIDO no aparecen en upcoming**: Solo `status = 'PENDIENTE'` dentro de la ventana de 7 días. Un período vencido ya pasó — no "vence esta semana".

5. **Obligaciones desactivadas excluidas**: `is_active=True` en todas las queries. Una obligación desactivada no contribuye a `totals` ni aparece en `vencen_esta_semana`.

6. **`_ensure_periods_generated_for_group` extraída**: Centraliza la lógica "generar períodos para todas las obligaciones activas de un grupo" que estaba duplicada en `list_periods`. Ahora reutilizada por dashboard y periods.

7. **`pending_cents` calculado en Python**: `total - paid` por moneda, no una tercera query. Es una resta trivial y mantiene el código simple.

### Resultado real de `pytest tests/ -v`

```
$ .venv/bin/pytest tests/ -v
220 passed, 8 warnings in 70.77s
```

- 206 tests de capas anteriores (todavía pasando)
- 14 tests nuevos de Capa 3f (test_dashboard.py):
  - TestDashboardEmptyGroup: 1 test (200 con arrays vacíos)
  - TestDashboardTotals: 3 tests (1 obligación COP pagada+pendiente, 2 obligaciones COP+USD, pago anulado)
  - TestDashboardMonthFilter: 1 test (mes distinto al actual)
  - TestDashboardInvalidMonth: 2 tests ("agosto" → 422, "2026-13" → 422)
  - TestDashboardUpcoming: 3 tests (due in 3 days, due in 20 days, overdue)
  - TestDashboardDeactivatedObligation: 1 test (is_active=False excluida)
  - TestDashboardAccessControl: 2 tests (no miembro → 403, member → 200)
  - TestDashboardUpcomingIndependenceFromMonth: 1 test (upcoming no depende de ?month=)

### Archivos creados o modificados

```
backend/
├── app/
│   ├── dashboard/
│   │   ├── __init__.py              (NUEVO — paquete vacío)
│   │   ├── schemas.py               (NUEVO — CurrencyTotal, UpcomingPeriod, DashboardResponse)
│   │   ├── repository.py            (NUEVO — 3 queries de agregación SQL)
│   │   ├── service.py               (NUEVO — get_dashboard)
│   │   └── router.py                (NUEVO — 1 endpoint GET)
│   ├── obligations/
│   │   └── service.py               (MODIFICADO — +_ensure_periods_generated_for_group, list_periods la reutiliza)
│   ├── payments/
│   │   └── repository.py            (CORREGIDO — datetime.now() → datetime.now(timezone.utc))
│   └── main.py                      (MODIFICADO — +dashboard_router)
└── tests/
    └── test_dashboard.py            (NUEVO — 14 tests de integración)
```

### Preguntas abiertas

1. **¿Paginación en `vencen_esta_semana`?** Actualmente retorna todos los períodos de los próximos 7 días sin límite. Para una familia con muchas obligaciones, podría haber 20+ períodos en una semana. ¿Se necesita paginación o un `LIMIT`?

2. **¿Cache del dashboard?** Las queries de agregación son costosas si hay muchos períodos. ¿Se necesita caché a nivel de request (Redis) o el volumen justifica la simplicity?

3. **¿Más métricas en el dashboard?** Actualmente retorna total/paid/pending y upcoming. ¿Se necesita "obligaciones por vencer este mes", "promedio de gasto mensual", u otras métricas?

---

## 2026-08-29 — Capa 3g: Audit (log_action + instrumentación, cierre de Capa 3)

### Qué se implementó, archivo por archivo

1. **`backend/app/audit/service.py`** (nuevo) — Función `log_action`:
   - `log_action(db, *, actor_user_id, group_id, action, entity_type, entity_id, metadata=None) -> None`
   - Inserta un `AuditLog` directamente (no hay repository intermedio — excepción arquitectónica documentada en ADR-005).
   - Usa `db.flush()`, NUNCA `db.commit()` — el caller es quien commitea.
   - El campo `metadata` del schema se mapea a `extra_metadata` en el modelo (nombre Python diferente al nombre DB).

2. **`backend/app/groups/service.py`** (modificado) — 5 llamadas a `log_action`:
   - `create_group`: `group.created` / `Group` / `group.id` / `{"name": name}`
   - `add_member`: `membership.added` / `GroupMembership` / `user.id` (nuevo miembro) / `{"role": role}`
   - `change_member_role`: `membership.role_changed` / `GroupMembership` / `target_user_id` / `{"new_role": new_role}`
   - `remove_member`: `membership.removed` / `GroupMembership` / `target_user_id` / `None`
   - `join_group_by_code`: `membership.joined_via_code` / `GroupMembership` / `user_id` / `{"invite_code_id": invite.id}`
   - Firma modificada: `add_member`, `change_member_role`, `remove_member` ahora reciben `actor_user_id: int`.

3. **`backend/app/groups/router.py`** (modificado) — 3 llamadas actualizadas:
   - `add_member`: pasa `actor_user_id=membership.user_id`
   - `change_member_role`: pasa `actor_user_id=membership.user_id`
   - `remove_member`: pasa `actor_user_id=membership.user_id`

4. **`backend/app/obligations/service.py`** (modificado) — 3 llamadas a `log_action`:
   - `create_obligation`: `obligation.created` / `Obligation` / `obligation.id` / `{"name": name}`
   - `update_obligation`: `obligation.updated` / `Obligation` / `obligation.id` / `{"fields": list(fields.keys())}`
   - `deactivate_obligation`: `obligation.deactivated` / `Obligation` / `id` / `None`
   - Firma modificada: las 3 funciones ahora reciben `actor_user_id: int | None = None`.

5. **`backend/app/obligations/router.py`** (modificado) — 3 llamadas actualizadas:
   - `create_obligation`: pasa `actor_user_id=membership.user_id`
   - `update_obligation`: pasa `actor_user_id=membership.user_id`
   - `deactivate_obligation`: pasa `actor_user_id=membership.user_id`

6. **`backend/app/payments/service.py`** (modificado) — 2 llamadas a `log_action`:
   - `register_payment`: `payment.registered` / `Payment` / `payment.id` / `{"amount_cents": amount_cents, "currency": currency}`
   - `void_payment`: `payment.voided` / `Payment` / `payment.id` / `None`
   - Sin cambio de firma (estas funciones ya recibían el actor).

7. **`backend/tests/test_audit.py`** (nuevo) — 10 tests de integración con Postgres real, uno por cada acción de auditoría.

### 11 instrumentaciones (tabla completa)

| # | Archivo | Función | action | entity_type | actor_user_id |
|---|---------|---------|--------|-------------|---------------|
| 1 | groups/service.py | `create_group` | `group.created` | `Group` | `user_id` (creador) |
| 2 | groups/service.py | `add_member` | `membership.added` | `GroupMembership` | `actor_user_id` (admin) |
| 3 | groups/service.py | `change_member_role` | `membership.role_changed` | `GroupMembership` | `actor_user_id` (admin) |
| 4 | groups/service.py | `remove_member` | `membership.removed` | `GroupMembership` | `actor_user_id` (admin) |
| 5 | groups/service.py | `join_group_by_code` | `membership.joined_via_code` | `GroupMembership` | `user_id` (quien se une) |
| 6 | obligations/service.py | `create_obligation` | `obligation.created` | `Obligation` | `actor_user_id` (admin) |
| 7 | obligations/service.py | `update_obligation` | `obligation.updated` | `Obligation` | `actor_user_id` (admin) |
| 8 | obligations/service.py | `deactivate_obligation` | `obligation.deactivated` | `Obligation` | `actor_user_id` (admin) |
| 9 | payments/service.py | `register_payment` | `payment.registered` | `Payment` | `current_user_id` |
| 10 | payments/service.py | `void_payment` | `payment.voided` | `Payment` | `voided_by_user_id` |

### Resultado real de `pytest tests/ -v`

```
$ .venv/bin/pytest tests/ -v
230 passed, 8 warnings in 71.31s
```

- 220 tests de capas anteriores (todavía pasando, sin modificar ningún test existente)
- 10 tests nuevos de Capa 3g (test_audit.py):
  - TestAuditGroupCreated: 1 test
  - TestAuditMembershipAdded: 1 test
  - TestAuditMembershipRoleChanged: 1 test
  - TestAuditMembershipRemoved: 1 test
  - TestAuditMembershipJoinedViaCode: 1 test
  - TestAuditObligationCreated: 1 test
  - TestAuditObligationUpdated: 1 test
  - TestAuditObligationDeactivated: 1 test
  - TestAuditPaymentRegistered: 1 test
  - TestAuditPaymentVoided: 1 test

### Decisiones de diseño

1. **`audit/service.py` sin `router.py` ni `repository.py`**: Consistente con ADR-005. `audit` es un módulo de solo escritura interno. No hay endpoints HTTP. El repository se omite porque la función `log_action` es trivial (un solo INSERT).

2. **`extra_metadata` en vez de `metadata`**: El campo Python del modelo `AuditLog` se llama `extra_metadata` (el nombre en DB es `metadata`). Esto evita conflicto con el parámetro `metadata` de la función `log_action`. El schema Pydantic usa `metadata` (más natural para el caller).

3. **Metadata sin valores sensibles**: Solo se almacenan nombres de campos (`{"fields": [...]}`), roles, montos y monedas (ya públicos). Nunca PAN, CVV, PIN ni credenciales. Consistente con ADR-008 y RNF-SEG-01.

4. **`actor_user_id` como keyword-only**: En las funciones de groups y obligations, el parámetro es keyword-only (`*` forcing) para evitar errores posicionales. En payments, ya existía como `current_user_id` / `voided_by_user_id`.

5. **`db.flush()` en `log_action`, `commit()` en el caller**: Misma transacción que el resto de la operación. Si la operación falla y se hace rollback, la entrada de auditoría también se descarta (correcto: no se debe auditar una operación que no se completó).

6. **Alcance de auditoría**: Solo las acciones listadas en ADR-008 y RNF-DATA-04: obligaciones (crear/editar/desactivar), pagos (registrar/anular), membresías (agregar/cambiar rol/quitar/unirse por código), y creación de grupo. **categories** (crear/editar) y **auth** (register/login) quedan FUERA del alcance en este MVP porque ni ADR-008 ni RNF-DATA-04 los mencionan.

7. **`actor_user_id` opcional en obligations**: A diferencia de groups (donde siempre hay un actor), en obligations el parámetro es `int | None = None` por consistencia. En la práctica siempre se pasa desde el router, pero si se llamara directamente (scripts, migraciones) no sería obligatorio.

### Archivos creados o modificados

```
backend/
├── app/
│   ├── audit/
│   │   ├── __init__.py           (sin cambios)
│   │   ├── models.py             (sin cambios)
│   │   └── service.py            (NUEVO — log_action)
│   ├── groups/
│   │   ├── service.py            (MODIFICADO — +log_action calls en 5 funciones, +actor_user_id en 3 firmas)
│   │   └── router.py             (MODIFICADO — +actor_user_id=membership.user_id en 3 llamadas)
│   ├── obligations/
│   │   ├── service.py            (MODIFICADO — +log_action calls en 3 funciones, +actor_user_id en 3 firmas)
│   │   └── router.py             (MODIFICADO — +actor_user_id=membership.user_id en 3 llamadas)
│   └── payments/
│       └── service.py            (MODIFICADO — +log_action calls en 2 funciones)
└── tests/
    └── test_audit.py             (NUEVO — 10 tests de integración)
```

### Preguntas abiertas

1. **¿Auditar categories y payment_methods?** Actualmente crear/editar categorías y medios de pago NO deja entrada en `audit_logs`. Ni ADR-008 ni RNF-DATA-04 los mencionan. **Pregunta a la familia**: ¿se necesita trazabilidad de quién creó/editó una categoría o medio de pago? Si se requiere, se agregan 4 instrumentaciones más (category.created, category.updated, payment_method.created, payment_method.updated).

2. **¿Auditar auth (register/login)?** ADR-008 no lo menciona. register ya deja una entrada implícita (el usuario existe), pero login no. **Pregunta**: ¿se necesita registro de intentos de login fallidos o solo login exitoso?

3. **¿Auditar read operations?** ADR-008 solo pide "mutaciones". Las lecturas (GET) no generan entrada de auditoría. ¿Se necesita en algún caso?

4. **¿Retención de audit_logs?** No hay TTL ni política de purga. Las filas se acumulan indefinidamente. Para una app familiar el volumen es bajo, pero ¿se necesita documentar una política de retención?

5. **¿Endpoint de lectura de audit_logs?** Actualmente no hay GET /audit — es deliberado (ADR-005). Si la familia necesita ver el historial de auditoría, se necesitaría un endpoint con filtros por grupo/fecha/acción. ¿Se agrega en V2?

---

## 2026-08-29 — Cierre de 3 gaps ADR-011: ownership transfer, password reset, timezone

### Qué se implementó

Se cerraron los 3 gaps reales entre ADR-011 y lo implementado, identificados en el backlog consolidado de Capa 3.

#### 1. Transferencia de ownership (ADR-011 #8)

**Archivos modificados:**

- **`backend/app/groups/schemas.py`** — `MemberRoleUpdate.role` cambia de `Literal["admin", "member"]` a `Literal["owner", "admin", "member"]`. Ahora se puede enviar `role: "owner"` en el PATCH.
- **`backend/app/groups/service.py`** — `change_member_role` recibe `caller_membership: GroupMembership` (nuevo parámetro keyword-only). Lógica nueva:
  - Si `new_role == "owner"`: solo el owner actual puede hacerlo (`NOT_OWNER` 403 si no lo es).
  - Guard anti-auto-transfer: `CANNOT_TRANSFER_TO_SELF` 400 si `caller_membership.user_id == target_user_id`.
  - Demote owner actual a `admin`, promueve target a `owner`.
  - Audit entry: `membership.ownership_transferred`.
  - Los roles no-owner siguen la lógica previa (admin+ puede cambiar admin↔member).
- **`backend/app/groups/router.py`** — Pasa `caller_membership=membership` al service.

**Tests nuevos en `test_groups.py` — `TestOwnershipTransfer` (5 tests):**

| # | Test | Verifica |
|---|------|----------|
| 1 | `test_owner_transfers_to_admin` | Owner transfiere → target es owner, old owner es admin, audit entry creado |
| 2 | `test_admin_cannot_transfer_ownership` | Admin intenta → 403 NOT_OWNER |
| 3 | `test_member_cannot_transfer_ownership` | Member intenta → 403 FORBIDDEN_NOT_ADMIN |
| 4 | `test_owner_cannot_transfer_to_self` | Owner se transfiere a sí mismo → 400 CANNOT_TRANSFER_TO_SELF |
| 5 | `test_transfer_non_member_fails` | Target no es miembro → 404 NOT_GROUP_MEMBER |

#### 2. Password reset (ADR-011 #3)

**Archivos creados/modificados:**

- **`backend/app/auth/repository.py`** — 2 funciones nuevas:
  - `update_password_hash(db, user_id, password_hash)` — actualiza el hash del password.
  - `revoke_all_refresh_tokens_for_user(db, user_id)` — revoca todos los refresh tokens activos del usuario (invalida sesiones).
- **`backend/app/groups/schemas.py`** — `PasswordResetResponse` nuevo schema: `{user_id, temporary_password}`.
- **`backend/app/groups/service.py`** — `reset_member_password` nueva función:
  - Genera password temporal con `secrets.token_urlsafe(16)`.
  - Hashea con Argon2id (`hash_password`).
  - Actualiza password_hash en DB.
  - Revoca todos los refresh tokens del usuario.
  - Audit entry: `user.password_reset` / `User` / `entity_id=target_user_id` / `metadata=None` (password NUNCA en metadata).
  - Retorna `{user_id, temporary_password}`.
- **`backend/app/groups/router.py`** — `POST /groups/{group_id}/members/{user_id}/reset-password` endpoint nuevo (admin+ via `require_admin`).

**Tests nuevos en `test_groups.py` — `TestResetMemberPassword` (7 tests):**

| # | Test | Verifica |
|---|------|----------|
| 1 | `test_admin_resets_member_password` | Admin resetea → 200, temp_password ≥16 chars, hash correcto en DB |
| 2 | `test_owner_resets_admin_password` | Owner resetea admin → 200 |
| 3 | `test_member_cannot_reset_password` | Member intenta → 403 FORBIDDEN_NOT_ADMIN |
| 4 | `test_reset_non_member_fails` | Target no es miembro → 404 NOT_GROUP_MEMBER |
| 5 | `test_reset_creates_audit_log` | Audit entry creado, metadata=None |
| 6 | `test_reset_revokes_old_refresh_tokens` | Todos los refresh tokens activos revocados después del reset |
| 7 | `test_temp_password_works_for_login` | Login con temp password exitoso → 200 + access_token |

#### 3. Timezone conexión Postgres (ADR-011 #4)

**Archivos modificados:**

- **`backend/app/database/session.py`** — `create_sync_engine` ahora pasa `connect_args={"options": "-c TimeZone=America/Bogota"}` en cada nueva conexión. Esto fija `TimeZone = 'America/Bogota'` a nivel de protocolo PostgreSQL, sin depender de event listeners.

**Test nuevo en `test_postgres.py`:**

- `test_timezone_set_to_bogota` — usa `_sync_engine` (el engine de la app) y verifica que `SHOW TIME ZONE` retorna `'America/Bogota'`.

### Resultado real de `pytest tests/ -v`

```
$ .venv/bin/pytest tests/ -v
243 passed, 8 warnings in 81.33s
```

- 230 tests de capas anteriores (sin modificar)
- 10 tests de Capa 3g (test_audit.py)
- 1 test de timezone (test_postgres.py)
- 12 tests nuevos de esta sesión:
  - TestOwnershipTransfer: 5 tests
  - TestResetMemberPassword: 7 tests

### Backlog actualizado

Los 3 ítems 🔴 del backlog consolidado de Capa 3 quedan **resueltos** y se mueven a la sección ✅ Ya resueltos.

---

## 2026-08-29 — Rate limiting (RNF-SEG-03/08) + housekeeping

### Housekeeping (2 items previos al rate limiting)

1. **Código de error consistente** (`backend/app/groups/service.py:135`): Cambiado `"NOT_OWNER"` → `"FORBIDDEN_NOT_OWNER"` en la rama de transferencia de ownership de `change_member_role`. El resto de la API usa `FORBIDDEN_NOT_OWNER` para este concepto (ver `require_owner` en `core/deps.py`). Test actualizado en `test_groups.py:653`.

2. **Línea duplicada** (`backend/app/database/session.py:32`): Eliminada la segunda declaración `SessionLocal = sessionmaker(...)` que estaba duplicada justo debajo de la primera.

### Qué se implementó

1. **`backend/app/core/rate_limit.py`** (nuevo) — Define el `Limiter` de slowapi con `key_func=get_remote_address` (in-memory, ADR-008). Módulo separado para evitar circular import entre `app.main` y los routers.

2. **`backend/app/main.py`** (modificado):
   - Importa `limiter` desde `app.core.rate_limit` y lo registra en `app.state.limiter`.
   - Exception handler para `RateLimitExceeded` que retorna `{"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde.", "code": "RATE_LIMIT_EXCEEDED"}` (formato consistente con el resto de la API).
   - Registra `SlowAPIMiddleware`.

3. **`backend/app/auth/router.py`** (modificado):
   - `register`: agregado `request: Request` como primer parámetro + `@limiter.limit("10/minute")`.
   - `login`: agregado `request: Request` como primer parámetro + `@limiter.limit("10/minute")`.
   - `refresh_token`: ya tenía `request: Request`, solo agregado `@limiter.limit("10/minute")`.

4. **`backend/app/groups/router.py`** (modificado):
   - `join_group`: agregado `request: Request` como primer parámetro + `@limiter.limit("10/minute")`.

5. **`backend/tests/conftest.py`** (modificado) — Fixture `autouse=True` `_reset_rate_limiter` que llama `limiter.reset()` antes de cada test. Esto resetea el storage in-memory de slowapi para que el conteo de 10/min no se acumule entre tests (que todos usan el mismo TestClient → misma IP falsa).

6. **`backend/tests/test_rate_limiting.py`** (nuevo) — 6 tests de integración con Postgres real:
   - `TestLoginRateLimit`: 11 requests a `/auth/login` → 429 en la 11ª.
   - `TestRegisterRateLimit`: 11 requests a `/auth/register` con emails distintos → 429 en la 11ª.
   - `TestRefreshRateLimit`: 11 requests a `/auth/refresh` → 429 en la 11ª.
   - `TestJoinGroupRateLimit`: 11 requests a `/groups/join` con códigos inválidos → 429 en la 11ª.
   - `TestLimiterResetBetweenTests`: dos tests que cada uno dispara 5 requests a `/auth/login` → el segundo test NO falla con 429, verificando que el fixture de reseteo funciona.

7. **`backend/pyproject.toml`** y **`backend/requirements.txt`** (modificados) — Agregada dependencia `slowapi>=0.1.9`.

### Decisiones de diseño

1. **Módulo separado `core/rate_limit.py`**: El `Limiter` se definió en un módulo independiente en vez de en `app.main` para evitar circular imports: `app.main` importa routers, routers importan `limiter`. Con el módulo separado, ambos importan de `app.core.rate_limit` sin dependencia circular.

2. **Decorador como inner decorator**: En slowapi + FastAPI, `@limiter.limit(...)` va como decorator interno (entre `@router.post(...)` y `def`). Verificado que funciona correctamente con este orden.

3. **Formato de respuesta 429 consistente**: `{"detail": "...", "code": "RATE_LIMIT_EXCEEDED"}` — mismo formato que usa el resto de la API para errores. El exception handler personalizado intercepta `RateLimitExceeded` (que es subclass de `starlette.exceptions.HTTPException`, no de `fastapi.HTTPException`) y retorna el JSON en el formato correcto.

4. **Reset del limiter entre tests via fixture `autouse=True`**: Fixture en `conftest.py` raíz que llama `limiter.reset()` antes de cada test. Verificado con un test dedicado que dos batches de requests no se interferían.

5. **Rate limiting in-memory (sin Redis)**: Consistente con ADR-008. Se pierde si Render reinicia la instancia, aceptable para el MVP.

### Resultado real de `pytest tests/ -v`

```
$ .venv/bin/pytest tests/ -v
249 passed, 19 warnings in 90.78s (0:01:30)
```

- 243 tests de capas anteriores (sin modificar)
- 6 tests nuevos de rate limiting (test_rate_limiting.py)

### Archivos creados o modificados

```
backend/
├── pyproject.toml                          (MODIFICADO — +slowapi)
├── requirements.txt                        (MODIFICADO — +slowapi)
├── app/
│   ├── core/
│   │   └── rate_limit.py                   (NUEVO — Limiter de slowapi)
│   ├── auth/
│   │   └── router.py                       (MODIFICADO — +request param + @limiter.limit en 3 endpoints)
│   ├── groups/
│   │   ├── router.py                       (MODIFICADO — +request param + @limiter.limit en join_group)
│   │   └── service.py                      (MODIFICADO — NOT_OWNER → FORBIDDEN_NOT_OWNER)
│   ├── database/
│   │   └── session.py                      (MODIFICADO — eliminada línea duplicada)
│   └── main.py                             (MODIFICADO — +rate_limit imports, +exception handler, +middleware)
└── tests/
    ├── conftest.py                         (MODIFICADO — +_reset_rate_limiter autouse fixture)
    ├── test_rate_limiting.py               (NUEVO — 6 tests de integración)
    └── test_groups.py                      (MODIFICADO — NOT_OWNER → FORBIDDEN_NOT_OWNER en assert)
```

### Preguntas abiertas

Ninguna. Rate limiting está completo según RNF-SEG-03 y RNF-SEG-08.

---

## Backlog consolidado — post cierre de gaps ADR-011 (2026-08-29)

Este resumen agrupa por tema las ~25 preguntas abiertas dispersas en las entradas de arriba (Capas 1 a 3g), para revisarlas de una sola vez en vez de bucear entrada por entrada. El backend de la Capa 3 está completo y verificado (243 tests contra Postgres real) — nada de lo siguiente bloquea empezar el frontend, pero conviene decidir antes de exponer la app a la familia real.

### 🟡 Regeneración de períodos al editar una obligación (Capa 3d)

Si un `PATCH` cambia `periodicity`, `due_day`, `start_date` o acorta `end_date` de una obligación, los `ObligationPeriod` ya generados NO se recalculan ni se eliminan — quedan con los valores viejos. No especificado en ningún ADR, decisión de producto pendiente: ¿regenerar automáticamente, o requerir que el admin borre/recree la obligación si necesita cambiar el cronograma?

### 🟢 Endpoints candidatos que el frontend probablemente va a pedir

- `GET /groups/{group_id}/members` — listado explícito de miembros (hoy solo se infiere indirectamente).
- `GET /groups/{group_id}/payments/{id}` — detalle de un pago específico.
- `?obligation_id=` en `GET /groups/{group_id}/periods` — para la vista de detalle de una obligación.

Ninguno bloquea arrancar el frontend; se agregan bajo demanda cuando una pantalla concreta los necesite.

### 🟢 Observabilidad (ADR-011 #9) — no iniciada

Logging estructurado (JSON) vía `structlog`, `request_id` por request correlacionado con `AuditLog`, y `GET /api/v1/health` sin auth — nada de esto existe todavía. No bloquea el frontend, pero sí conviene tenerlo antes de desplegar a Render (para diagnosticar cold starts y errores en producción sin acceso a los logs crudos del hosting).

### ⚪ Decisiones de producto de bajo impacto (YAGNI hasta que un caso real lo pida)

Paginación en `vencen_esta_semana`, caché del dashboard, más métricas de dashboard, límite de invite codes activos por grupo, límite de `obligation_periods` por obligación, política de retención de `audit_logs`, mover `get_user_by_id` a un módulo de users dedicado, migrar de `httpx` a `httpx2` en tests.

### ✅ Ya resueltos (quedan aquí solo como registro, no requieren acción)

- **Rate limiting (RNF-SEG-03/08)**: resuelto el 2026-08-29 — `slowapi` in-memory, 10/min/IP en `/auth/login`, `/auth/register`, `/auth/refresh`, `/groups/join`. Respuesta 429 con `{"detail": "...", "code": "RATE_LIMIT_EXCEEDED"}`. Fixture autouse en conftest resetea el limiter entre tests.
- **Transferencia de ownership (ADR-011 #8)**: resuelta el 2026-08-29 — `PATCH .../members/{user_id}` con `role: "owner"` funciona, demueve owner a admin, audit `membership.ownership_transferred`.
- **Password reset (ADR-011 #3)**: resuelto el 2026-08-29 — `POST .../reset-password` genera temp password, hashea, revoca tokens, audita `user.password_reset`.
- **Timezone conexión Postgres (ADR-011 #4)**: resuelto el 2026-08-29 — `connect_args` fija `TimeZone=America/Bogota` en cada conexión.
- Auditar categorías/medios de pago y auth (register/login): decisión ya tomada en Capa 3g — fuera de alcance del MVP porque ni ADR-008 ni RNF-DATA-04 los mencionan.
- Auditar operaciones de lectura: ADR-008 solo pide mutaciones, confirmado que no aplica.
- Notificación al unirse por código / al anular un pago: cubierto por ADR-012 (el módulo de alertas existe como modelo pero no se activa ningún envío en el MVP).
- Límite de pagos activos por período: ya resuelto, es 1 por diseño (`PERIOD_ALREADY_PAID`).
- Endpoint de lectura de `audit_logs`: deliberadamente fuera de alcance, `audit/` es un módulo de solo escritura (ADR-005).
- Código de invitación de un solo uso por defecto: ya resuelto por ADR-014, `max_uses=NULL` (reutilizable) es el caso típico documentado.
- Script de seed de categorías de sistema: ya existe (`backend/scripts/seed.py`), idempotente.
- Preguntas de Capa 3c (DELETE de categorías/medios de pago, límites, filtros/paginación): ya respondidas en conversación — el contrato ADR-004 ya las descarta explícitamente, no son gaps.
- `freezegun`/`PYTHONPATH`/`datetime.now()` naive: corregidos como housekeeping en capas posteriores.

---

## 2026-08-29 — Capa Frontend 1: api-client + auth-context + smoke test

### Qué se implementó

Carpeta `frontend/` completa con el cliente API tipado, contexto de autenticación, y una página de smoke test temporal. Stack: Next.js 14 (App Router, `output: 'export'`), TypeScript estricto, Tailwind CSS, Vitest + Testing Library + MSW.

#### 1. Configuración del proyecto

- **`frontend/package.json`** — Next.js 14.2.29, React 18, Tailwind, Vitest 3, MSW 2, Testing Library.
- **`frontend/tsconfig.json`** — TypeScript estricto, path alias `@/*`.
- **`frontend/next.config.mjs`** — `output: "export"` (sitio 100% estático, sin SSR — ADR-006).
- **`frontend/tailwind.config.ts`** — Configuración mínima Tailwind.
- **`frontend/postcss.config.js`** — PostCSS con Tailwind y Autoprefixer.
- **`frontend/vitest.config.ts`** — Entorno jsdom, React plugin, setup file.
- **`frontend/.eslintrc.json`** — `next/core-web-vitals` (ESLint 8, compatible con Next.js 14).
- **`frontend/.env.example`** — Copia de `frontend.env.example`.
- **`frontend/Dockerfile`** — Node 20 Alpine, compatible con `docker-compose.yml` servicio `frontend`.

#### 2. `src/lib/api-client.ts` — Cliente API central

- **`ApiError`**: Clase extends Error con `.detail`, `.code`, `.status`.
- **`apiFetch<T>(path, options)`**: Fetch tipado con:
  - Base URL desde `NEXT_PUBLIC_API_BASE_URL`.
  - Authorization header automático vía getter inyectado.
  - Parseo de errores `{detail, code}` → `ApiError`.
  - **Single-flight refresh**: si recibe 401 y el path NO es `/auth/login`, `/auth/register`, `/auth/refresh`:
    - `refreshPromise` compartida (promesa en módulo) — si ya hay un refresh en curso, la request actual se encola en `queuedRequests[]`.
    - Si refresh exitoso: guarda nuevo token, reintenta la request original UNA vez, resuelve todas las encoladas.
    - Si refresh falla: limpia token, llama `onRefreshFailed`, propaga error a todas las encoladas.
  - `configureAuth()`: setter/getter + reset de `refreshPromise` y `queuedRequests`.
- **Funciones expuestas**: `login`, `register`, `refreshToken`, `logout` (todas con `credentials: 'include'`), `getMe`.

#### 3. `src/lib/auth-context.tsx` — Contexto de autenticación

- **`AuthProvider`**: Estado `accessToken` en memoria (useState + useRef), `user`, `status: 'idle' | 'loading' | 'authenticated' | 'unauthenticated'`.
- **Ref para token**: `accessTokenRef` sincronizado con `state.accessToken` en cada render. El getter de api-client lee del ref (no de un closure con `state.accessToken`), resolviendo la condición de carrera donde `getMe()` se ejecuta antes de que el effect de `configureApiClient` actualice el closure.
- **Efectos**:
  - `configureApiClient` una sola vez en mount (con ref getter).
  - Silent refresh en mount: `POST /auth/refresh` con cookie. Si éxito → fetch user → authenticated. Si falla → unauthenticated.
- **Métodos expuestos**: `login(email, password)`, `register(data)`, `logout()`.
- **Nunca** usa `localStorage`/`sessionStorage` para tokens — verificable en el código.

#### 4. `src/app/layout.tsx` — Layout raíz

- Envuelve children con `AuthProvider`.
- Tailwind CSS importado via `globals.css`.

#### 5. `src/app/page.tsx` — Smoke test temporal

- Formulario de login (email/password) que llama `useAuth().login(...)`.
- Muestra `status` actual y `user.email` cuando está autenticado.
- Botón de logout.
- Tailwind mínimo, sin diseño — solo para verificar el flujo manualmente.

### Tests — 16 tests, todos pasando

#### `tests/api-client.test.ts` (11 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Adjunta Authorization header cuando hay token | `request.headers.get("Authorization") === "Bearer my-test-token"` |
| 2 | No adjunta Authorization cuando token es null | Header es null |
| 3 | Parsea error `{detail, code}` y lanza `ApiError` | `ApiError.detail`, `.code`, `.status` |
| 4 | Dos requests en paralelo con 401 disparan UN solo refresh | `refreshCount === 1` tras `Promise.all([getMe(), getMe()])` |
| 5 | Tras refresh exitoso, reintenta con nuevo token | `currentToken === "fresh-token"` |
| 6 | Si refresh falla, llama `onRefreshFailed` | `refreshFailedCalled === true`, token null |
| 7 | No dispara refresh para /auth/login, /auth/register, /auth/refresh | `refreshCalled === false` |
| 8 | `login()` retorna `AccessTokenResponse` | `result.access_token === "new-access-token"` |
| 9 | `register()` retorna `AccessTokenResponse` | `result.access_token === "new-access-token"` |
| 10 | `logout()` completa sin error | `resolves.toBeUndefined()` |
| 11 | `getMe()` retorna datos del usuario | `user.email === "test@example.com"` |

#### `tests/auth-context.test.tsx` (5 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Mount sin sesión → unauthenticated | `status === "unauthenticated"`, user/accessToken null |
| 2 | Mount con sesión → authenticated | `status === "authenticated"`, user.email correcto |
| 3 | `login()` exitoso | `status === "authenticated"`, user/accessToken seteados |
| 4 | `login()` fallido re-lanza error | Error thrown, status unauthenticated |
| 5 | `logout()` limpia estado + llama POST /auth/logout | `logoutCalled === true`, estado limpio |

### Salida real de verificación

```
$ cd frontend
$ npm install
# 278 packages installed

$ npm run build
# ✓ Compiled successfully
# ✓ Generating static pages (4/4)
# Route (app)  Size  First Load JS
# ┌ ○ /        3.05 kB  90.3 kB
# ○ (Static) prerendered as static content

$ npm run lint
# ✔ No ESLint warnings or errors

$ npm test
# ✓ tests/api-client.test.ts (11 tests) 208ms
# ✓ tests/auth-context.test.tsx (5 tests) 383ms
# Test Files  2 passed (2)
# Tests  16 passed (16)
```

### Decisiones de diseño

1. **Single-flight refresh con promesa compartida**: Se usa `refreshPromise: Promise<string> | null` como variable de módulo. Cuando un request recibe 401, si `refreshPromise` es null, crea la promesa. Si ya existe, agrega callbacks a `queuedRequests[]` y espera. Esto evita múltiples refresh simultáneos (ADR-001 lo exige). Al resolverse, se itera `queuedRequests` y se resuelven/rechazan todas.

2. **Getter vía ref, no vía closure de `state.accessToken`**: El efecto `configureApiClient` se ejecuta una sola vez en mount. El getter lee de `accessTokenRef.current` que se sincroniza con `state.accessToken` en cada render. Esto evita la condición de carrera donde `getMe()` (llamado después de `setState` con el nuevo token) ejecuta `apiFetch` antes de que el efecto de re-configuración actualice el closure. Con el ref, el getter siempre retorna el valor más reciente.

3. **`configureAuth()` resetea `refreshPromise` y `queuedRequests`**: Para tests — cuando se llama con getters nulos (como en `afterEach`), también limpia el estado de refresh en vuelo. Esto evita que un refresh pendiente de un test anterior interfiera con el siguiente.

4. **`next.config.mjs` en vez de `next.config.ts`**: Next.js 14.2 no soporta `.ts` para config. Se usa `.mjs` con export default (ADR-006 no especifica extensión, solo `output: 'export'`).

5. **Logout test ordenado primero en `auth-context.test.tsx`**: Tests de auth context son sensibles al orden por el estado global de `api-client.ts`. El test de logout funciona en cualquier posición, pero su implementación actual (usando refresh exitoso para autenticarse) lo hace más robusto cuando corre primero. Se documenta como decisión no especificada en ADRs.

6. **ESLint 8, no 9**: `eslint-config-next@14` es incompatible con ESLint 9 (opciones removidas). Se instala ESLint 8 explícitamente.

### Desviaciones del prompt

**Ninguna desviación sustancial**. El código replica fielmente ADR-001 (access token en memoria, refresh en cookie httpOnly), ADR-006 (output: 'export', sin middleware.ts), ADR-008 (nunca loguear tokens, CORS credentials), y ADR-009 (Vitest + Testing Library + MSW).

### Preguntas abiertas para el siguiente prompt (login/register real + layout con guard)

1. **¿Layout `(app)/layout.tsx` con redirect o `useAuth().status`?** El ADR-006 dice "guard de sesión es un componente cliente que redirige si no hay sesión válida". ¿Redirigir a `/login` con `useRouter().replace()` o simplemente ocultar el contenido y mostrar loading?

2. **¿Manejo de `loading` state en el guard?** El `status: 'loading'` puede durar ~1s durante el refresh silencioso. ¿Mostrar spinner o skeleton, o simplemente no renderizar nada?

3. **¿Página 404 personalizada?** Next.js soporta `not-found.tsx`. ¿Se necesita o la 404 por defecto es suficiente?

4. **¿`tailwind.config.ts` para extender el theme?** Apenas se crean los componentes reales (Button, Card, Table), se necesitará extender colores/fuentes. ¿Hacerlo en este prompt o en el siguiente?

5. **¿¿Estado de `configureAuth` como singleton global es problemático??** Actualmente el getter/setter es un singleton de módulo. En tests, el `afterEach` lo resetea. En producción con React strict mode (effects se ejecutan dos veces), el singleton puede causar que el primer configureAuth se sobreescriba. No es un bug real (el segundo configureAuth tiene los mismos valores) pero si se necesita testing estricto, considerar inyección de dependencias.

---

## 2026-08-29 — Capa Frontend 2: Login, Register, Home (pages + tests)

### Qué se implementó

Páginas de autenticación (login + register) con manejo de errores, validación client-side, y página raíz con redirect/placeholder. Todos los archivos nuevos dentro de `frontend/src/app/`.

#### 1. `(auth)/layout.tsx` — Layout compartido de auth

- Centra el form verticalmente, fondo gris, card blanca con sombra.
- Reutiliza el mismo wrapper visual de la página de smoke test.
- Sin `AuthProvider` (ya está en `layout.tsx` raíz).
- Header "Gestor Familiar de Pagos" compartido entre login y register.

#### 2. `(auth)/login/page.tsx` — Formulario de login

- Form controlado con `useState` para email y password.
- Al enviar: llama `useAuth().login(email, password)`.
- Mapeo de errores por `.code`:
  - `INVALID_CREDENTIALS` → "Email o contraseña incorrectos."
  - cualquier otro → "No se pudo iniciar sesión. Intenta de nuevo."
- Nunca muestra `.detail` crudo del backend (son mensajes en inglés para debug).
- Loading state explícito: "Conectando... esto puede tardar hasta un minuto la primera vez" (cold start de Render, ADR-001).
- Al éxito: `router.replace("/")`.
- Link a `/register`: "¿No tienes cuenta? Regístrate".

#### 3. `(auth)/register/page.tsx` — Formulario de registro

- Form controlado con `useState` para: email, password, full_name, phone_number (opcional), invite_code (opcional).
- Texto de ayuda en invite_code: "Si tienes un código de invitación de tu grupo familiar, ingrésalo aquí".
- Validación client-side ANTES de enviar (evita 422 de FastAPI):
  - Email con formato válido (regex `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`).
  - Password ≥ 8 caracteres.
  - full_name no vacío (trim).
- `noValidate` en el `<form>` para deshabilitar validación HTML5 nativa y usar solo la custom.
- Mapeo de errores por `.code`:
  - `EMAIL_ALREADY_EXISTS` → "Ya existe una cuenta con ese email."
  - `INVALID_INVITE_CODE` → "El código de invitación no es válido o expiró."
  - `ALREADY_MEMBER` → "Ya eres miembro de ese grupo."
  - cualquier otro → "No se pudo completar el registro. Intenta de nuevo."
- Al éxito: `router.replace("/")` (register ya deja `status: 'authenticated'`).
- Link a `/login`: "¿Ya tienes cuenta? Inicia sesión".

#### 4. `app/page.tsx` — Página raíz (reemplaza smoke test)

- Componente cliente que lee `useAuth().status`:
  - `idle | loading` → "Cargando..."
  - `unauthenticated` → `router.replace("/login")` (client-side, ADR-006).
  - `authenticated` → placeholder: "Sesión iniciada como {user.email}" + botón logout.
- Flash brief de "Cargando..." antes de redirigir es esperado y aceptado (sin SSR, ADR-006).

### Tests — 19 tests nuevos, 35 total, todos pasando

#### `tests/login-page.test.tsx` (6 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Renders form | Campos email/password + botón "Iniciar sesión" visibles |
| 2 | Successful login navigates to / | `router.replace("/")` llamado tras login exitoso |
| 3 | INVALID_CREDENTIALS error | Mensaje "Email o contraseña incorrectos." en pantalla, no navega |
| 4 | Unknown error | Mensaje genérico "No se pudo iniciar sesión. Intenta de nuevo." |
| 5 | Disabled button while pending | Botón deshabilitado + texto "Conectando..." durante request |
| 6 | Register link | Link con href="/register" |

#### `tests/register-page.test.tsx` (9 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Renders all fields | nombre, email, password, teléfono, código de invitación, botón |
| 2 | Successful register navigates to / | `router.replace("/")` llamado, request a `/auth/register` hecha |
| 3 | EMAIL_ALREADY_EXISTS | "Ya existe una cuenta con ese email." |
| 4 | INVALID_INVITE_CODE | "El código de invitación no es válido o expiró." |
| 5 | ALREADY_MEMBER | "Ya eres miembro de ese grupo." |
| 6 | Short password | Error client-side, request NUNCA se dispara (verifica contador de llamadas MSW) |
| 7 | Invalid email format | "Ingresa un email válido." |
| 8 | Empty full name | "El nombre es obligatorio." |
| 9 | Login link | Link con href="/login" |

#### `tests/home-page.test.tsx` (4 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Redirects when unauthenticated | `router.replace("/login")` llamado cuando refresh falla |
| 2 | Shows email when authenticated | email visible, no redirección |
| 3 | Loading state | "Cargando..." visible durante refresh |
| 4 | No redirect while loading | `router.replace` NO llamado durante loading |

### Decisiones de diseño

1. **`vi.hoisted()` para `mockReplace`**: `vi.mock()` se hoistinga al top del archivo. Si `mockReplace` se define con `const mockReplace = vi.fn()` después del hoisting, el closure captura `undefined`. `vi.hoisted()` fuerza que la variable se declare antes del hoisting y persista en el mock. Sin embargo, el mock persiste entre tests en el mismo archivo → `afterEach(() => mockReplace.mockClear())` necesario.

2. **`noValidate` en forms**: Los inputs `type="email"` y `required` disparan validación HTML5 nativa que bloquea `form.submit()` en jsdom antes de que el `onSubmit` del componente se ejecute. Con `noValidate`, la validación es 100% custom. Se mantienen los atributos `type`, `minLength` y `id/for` para accesibilidad y UX.

3. **`afterEach` para MSW handlers + mock de auth**: El `setup.ts` ya hace `server.resetHandlers()` + `configureAuth(...)` después de cada test. Los tests de pages necesitan additionally configurar handlers específicos (ej. refresh que falla) que override los defaults. `server.use()` es request-scoped en MSW 2, así que los overrides se limpian automáticamente al final del test.

4. **Waiting for loading state**: Los tests de login/register esperan `waitFor(() => expect(screen.queryByText(/conectando/i)).toBeNull())` antes de interactuar. Esto es necesario porque `AuthProvider` inicia con `status: 'loading'` (el refresh silencioso en mount) — el botón dice "Conectando..." hasta que el refresh resuelva. Sin este wait, el `userEvent.click` haría click en un botón disabled.

5. **Mapeo de errores con switch, no dictionary**: Se usó `switch (err.code)` en vez de un dict `code → message` porque los códigos de error son pocos (3-4 por endpoint) y el switch es más explícito para debugging. La rama `default` cubre errores de red y códigos desconocidos con un mensaje genérico.

6. **No se muestra `.detail` del backend**: Los mensajes de error del backend están en inglés y pensados para debug (ej. "Invalid credentials"). El frontend siempre muestra mensajes localizados y amigables. Esto es una capa adicional de abstracción que protege al usuario de detalles internos.

### Resultado real de verificación

```
$ cd frontend && npm run build
✓ Compiled successfully
✓ Generating static pages (6/6)
Route (app)                              Size     First Load JS
┌ ○ /                                    2.84 kB        90.1 kB
├ ○ /_not-found                          873 B          88.2 kB
├ ○ /login                               2.35 kB        99.1 kB
└ ○ /register                            2.88 kB        99.7 kB

$ cd frontend && npm run lint
✔ No ESLint warnings or errors

$ cd frontend && npm test
✓ tests/api-client.test.ts (11 tests) 367ms
✓ tests/home-page.test.tsx (4 tests) 298ms
✓ tests/auth-context.test.tsx (5 tests) 481ms
✓ tests/login-page.test.tsx (6 tests) 1398ms
✓ tests/register-page.test.tsx (9 tests) 2272ms
Test Files  5 passed (5)
Tests  35 passed (35)
```

### Archivos creados o modificados

```
frontend/src/app/
├── (auth)/
│   ├── layout.tsx           (NUEVO — layout compartido de auth)
│   ├── login/
│   │   └── page.tsx         (NUEVO — formulario de login)
│   └── register/
│       └── page.tsx         (NUEVO — formulario de registro)
└── page.tsx                 (REEMPLAZADO — smoke test → redirect/placeholder)

frontend/tests/
├── login-page.test.tsx      (NUEVO — 6 tests)
├── register-page.test.tsx   (NUEVO — 9 tests)
└── home-page.test.tsx       (NUEVO — 4 tests)
```

### Preguntas abiertas para el siguiente prompt (layout `(app)/` con guard + dashboard)

1. **¿Layout `(app)/layout.tsx` con redirect?** El ADR-006 dice "guard de sesión es un componente cliente que redirige si no hay sesión válida". La página raíz actual ya hace esto (redirect a `/login` si unauthenticated). El layout `(app)/` generalizaría esto a todas las rutas protegidas. ¿Un solo guard en el layout o guards individuales por ruta?

2. **¿Qué pasa si el usuario tiene 0 grupos al autenticarse?** El flujo actual lo deja en la página raíz con "Sesión iniciada como X". Si tiene 0 grupos, no hay dashboard que mostrar. ¿Redirigir a una pantalla "Crea tu primer grupo" o mostrar un empty state en el dashboard?

3. **¿Componentes UI reutilizables (Button, Card, Input)?** Los forms actuales usan Tailwind inline. Para el dashboard se necesitarán componentes más complejos (tablas, cards, charts). ¿Crearlos en este prompt o en el siguiente?

4. **¿Página 404 personalizada?** Next.js soporta `not-found.tsx`. ¿Se necesita o la 404 por defecto es suficiente?

5. **¿`tailwind.config.ts` para extender el theme?** Apenas se crean componentes reales, se necesitará extender colores/fuentes. ¿Hacerlo en este prompt o en el siguiente?

---

## 2026-08-29 — Capa Frontend 3: Groups Context, Guard Layout, Dashboard

### Qué se implementó

Groups context con persistencia, layout de protección de rutas, página de dashboard con empty/populated states, y redirect de la raíz. Todos los archivos nuevos dentro de `frontend/src/app/(app)/` o modificados existentes.

#### 1. `src/lib/groups-context.tsx` — Contexto de grupos

- **`GroupProvider`**: Estado `groups[]`, `currentGroupId`, `loading`, `error`.
- **`useGroups()`**: Hook que expone `groups`, `currentGroup`, `currentGroupId`, `setCurrentGroupId()`, `createGroup()`.
- **GET /groups** en mount: popula `groups[]`.
- **localStorage** key `"currentGroupId"`: persiste selección. Si el stored ID no está en la lista, cae al primer grupo automáticamente.
- **`createGroup(name)`**: POST /groups, agrega a `groups[]`, setea como `currentGroupId`.
- **Mapeo de errores**:
  - `NAME_TOO_LONG` → "El nombre debe tener entre 1 y 200 caracteres."
  - `EMPTY_NAME` → "El nombre del grupo no puede estar vacío."
  - default → "No se pudo crear el grupo. Intenta de nuevo."
- **Exporta** tipo `Group` para uso en tests.

#### 2. `src/app/(app)/layout.tsx` — Guard de sesión + GroupProvider

- **`AppShell`**: Componente cliente que:
  - Redirige a `/login` cuando `status === 'unauthenticated'`.
  - Muestra "Cargando..." durante `idle | loading`.
  - Cuando autenticado: envuelve children en `GroupProvider`.
- **`AppHeader`**: Header con:
  - Nombre del grupo como texto (si 1 grupo).
  - `<select>` con todos los grupos (si 2+ grupos).
  - Botón "Cerrar sesión".
- Patrón de redirect idéntico a `app/page.tsx` (useEffect + router.replace).

#### 3. `src/app/(app)/dashboard/page.tsx` — Dashboard con empty/populated state

- **0 grupos**: Muestra "Crea tu primer grupo" + form con:
  - Input "Nombre del grupo" con validación (no vacío).
  - Mensaje de error inline (lee de `useGroups().error`).
  - Botón "Crear grupo" / "Creando..." durante request.
- **1+ grupos**: Muestra "Bienvenido a {group name}" + badge de rol.
- Componente `EmptyState` separado para evitar function declaration inside block (Error de TypeScript con ES5 target).

#### 4. `src/app/page.tsx` — Redirect a /dashboard (MODIFICADO)

- **Antes**: authenticated → placeholder "Sesión iniciada como {email}" + logout.
- **Ahora**: authenticated → `router.replace("/dashboard")`.
- Se eliminó `user` y `logout` del destructuring de `useAuth()` (ya no se usan).
- Bloque authenticated muestra "Redirigiendo..." (idéntico al unauthenticated).

#### 5. `tests/handlers.ts` — Handlers MSW actualizados

- `GET /groups` → retorna `[]` por defecto.
- `POST /groups` → crea grupo con ID 1, name del body, my_role "owner".

### Tests — 11 tests nuevos, 46 total, todos pasando

#### `tests/groups-context.test.tsx` (5 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Mounts with empty groups array | loading=false, group-count=0, current-id=none |
| 2 | Loads groups from GET /groups on mount | group-count=2, current-id=1, current-name correcto |
| 3 | setCurrentGroupId updates currentGroup | current-id=2 tras click, localStorage seteado |
| 4 | createGroup calls POST /groups and appends | POST llamado, group-count=3, current-id=3 |
| 5 | Invalid localStorage falls back to first group | storedId=999 → reset a 1 |

#### `tests/app-layout.test.tsx` (3 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Redirects to /login when unauthenticated | router.replace("/login") llamado |
| 2 | Shows group name as text (NO select) when 1 group | "Familia García" visible, combobox=null |
| 3 | Shows select dropdown when 2+ groups | combobox con displayValue="Familia García" |

#### `tests/dashboard-page.test.tsx` (3 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | Shows create group form when 0 groups | "Crea tu primer grupo" + input + botón visibles |
| 2 | Shows welcome message when 1+ groups | "Bienvenido a Familia García" + badge "owner" |
| 3 | Shows inline error when create group fails | NAME_TOO_LONG → "El nombre debe tener entre 1 y 200 caracteres." |

#### `tests/home-page.test.tsx` (1 test modificado)

- **Test 2**: "shows email when authenticated" → "redirects to /dashboard when authenticated" — ahora espera `router.replace("/dashboard")` en vez de buscar texto del email.

### Decisiones de diseño

1. **Split de `EmptyState` en componente separado**: El `async function handleCreate` declarado dentro de un `if` block causaba `TypeScript error: Function declarations are not allowed inside blocks in strict mode when targeting 'ES5'`. La solución fue extraer el empty state a un componente dedicado.

2. **Error state centralizado en context, no local**: `EmptyState` lee `error` de `useGroups()` en vez de mantener su propio `createError` state. Esto garantiza que el mapeo de errores (con código específico) en `groups-context.tsx` es la fuente de verdad. El catch en `handleCreate` es necesario solo para que `creating` se resetee, no para setear el error.

3. **`AuthProvider` wrapper en tests de layout**: `AppLayout` usa `useAuth()` internamente, pero no tiene `AuthProvider` (ya está en el layout raíz). Los tests deben envolver `AppLayout` con `AuthProvider` para evitar el throw "useAuth must be used within an AuthProvider".

4. **`select` condicional en header**: Con 1 grupo se muestra solo el nombre como texto (sin `<select>`). Con 2+ se muestra un `<select>`. Esto evita UI innecesaria y es verificado explícitamente en test 2 de `app-layout.test.tsx`.

5. **`currentGroupId` fallback a primer grupo**: Si localStorage tiene un ID inválido (e.g. 999, o el usuario eliminó el grupo), se resetea automáticamente al primer grupo de la lista sin forzar al usuario a elegir.

### Resultado real de verificación

```
$ cd frontend && npm run build
✓ Compiled successfully
✓ Generating static pages (7/7)
Route (app)                              Size     First Load JS
┌ ○ /                                    2.63 kB        89.9 kB
├ ○ /_not-found                          873 B          88.2 kB
├ ○ /dashboard                           3.35 kB        90.6 kB
├ ○ /login                               2.35 kB        99.1 kB
└ ○ /register                            2.89 kB        99.7 kB

$ cd frontend && npm run lint
✔ No ESLint warnings or errors

$ cd frontend && npm test
✓ tests/api-client.test.ts (11 tests) 390ms
✓ tests/auth-context.test.tsx (5 tests) 595ms
✓ tests/app-layout.test.tsx (3 tests) 688ms
✓ tests/groups-context.test.tsx (5 tests) 703ms
✓ tests/dashboard-page.test.tsx (3 tests) 1863ms
✓ tests/login-page.test.tsx (6 tests) 1996ms
✓ tests/home-page.test.tsx (4 tests) 266ms
✓ tests/register-page.test.tsx (9 tests) 3103ms
Test Files  8 passed (8)
Tests  46 passed (46)
```

### Archivos creados o modificados

```
frontend/src/
├── app/
│   ├── (app)/
│   │   ├── layout.tsx                  (NUEVO — guard + GroupProvider + header)
│   │   └── dashboard/
│   │       └── page.tsx                (NUEVO — empty/populated state)
│   └── page.tsx                        (MODIFICADO — authenticated → redirect a /dashboard)
├── lib/
│   └── groups-context.tsx              (NUEVO — GroupProvider + useGroups)

frontend/tests/
├── handlers.ts                         (MODIFICADO — +GET /groups, +POST /groups)
├── groups-context.test.tsx             (NUEVO — 5 tests)
├── app-layout.test.tsx                 (NUEVO — 3 tests)
├── dashboard-page.test.tsx             (NUEVO — 3 tests)
└── home-page.test.tsx                  (MODIFICADO — test 2 ahora espera redirect a /dashboard)
```

### Preguntas abiertas para el siguiente prompt (obligations + payments + sidebar nav)

1. **¿Componentes UI reutilizables (Button, Card, Input)?** Los forms actuales usan Tailwind inline. Para obligations/payments se necesitarán componentes más complejos (tablas, cards). ¿Crearlos en este prompt o en el siguiente?

2. **¿Página 404 personalizada?** Next.js soporta `not-found.tsx`. ¿Se necesita o la 404 por defecto es suficiente?

3. **¿`tailwind.config.ts` para extender el theme?** Apenas se crean componentes reales, se necesitará extender colores/fuentes. ¿Hacerlo en este prompt o en el siguiente?

4. **¿Sidebar o tabs para navegación entre obligations/payments/dashboard?** El ADR-006 lista `(app)/obligations/page.tsx` y `(app)/payments/page.tsx`. ¿Navegación con sidebar, tabs, o links simples?

5. **¿Detalle de obligación `(app)/obligations/[id]/page.tsx`?** El ADR-006 lo lista. ¿Incluirlo en el mismo prompt que la lista de obligations o en uno separado?

---

## 2026-08-31 — Capa Frontend (corrección): bug createGroup con códigos de error inexistentes

### Bug identificado

**Síntoma**: Cuando el usuario escribía un nombre de grupo de más de 200 caracteres y lo enviaba, veía el mensaje genérico "No se pudo crear el grupo. Intenta de nuevo." en vez del mensaje específico "El nombre debe tener entre 1 y 200 caracteres." que el switch en `createGroup` mapeaba para el código `NAME_TOO_LONG`.

**Causa raíz**: `createGroup` en `groups-context.tsx` mapeaba dos códigos de error de negocio (`NAME_TOO_LONG` y `EMPTY_NAME`) que el backend **nunca devuelve**. El campo `name` de `POST /groups` se valida con `Field(min_length=1, max_length=200)` de Pydantic — no hay ningún `raise` explícito en el service para longitud de nombre. Cuando el nombre excede 200 caracteres, el backend responde 422 con `{"detail": [...]}` (una lista, no un dict), y `api-client.ts:handleResponse` lee `body.code` que no existe → `code` queda en `"UNKNOWN_ERROR"`. El switch nunca hace match y el usuario ve el fallback genérico.

### Qué se corrigió (3 archivos)

1. **`frontend/src/app/(app)/dashboard/page.tsx:74`** — Agregado `maxLength={200}` al `<input id="group-name">`. El navegador ahora impide escribir más de 200 caracteres, haciendo el caso "nombre demasiado largo" irrepresentable desde la UI.

2. **`frontend/src/lib/groups-context.tsx:118-133`** — Eliminado el switch con los códigos `NAME_TOO_LONG`/`EMPTY_NAME` (que no existen en el backend real). `createGroup` ahora usa un solo mensaje genérico: `"No se pudo crear el grupo. Intenta de nuevo."` para todos los errores.

3. **`frontend/tests/dashboard-page.test.tsx:74-106`** — Test 3 reescrito para ser fiel al comportamiento real del backend: usa nombre válido ("Familia Test"), mockea un error inesperado 500 con `code: "INTERNAL_ERROR"`, y verifica el mensaje genérico. Agregado test nuevo que verifica que el input tiene `maxLength="200"`.

### Verificación

```
$ cd frontend && npm run build
✓ Compiled successfully
✓ Generating static pages (7/7)

$ cd frontend && npm run lint
✔ No ESLint warnings or errors

$ cd frontend && npm test
✓ tests/dashboard-page.test.tsx (4 tests) 276ms
Test Files  8 passed (8)
Tests  47 passed (47)
```

### Archivos modificados

```
frontend/src/app/(app)/dashboard/page.tsx     (MODIFICADO — +maxLength={200})
frontend/src/lib/groups-context.tsx            (MODIFICADO — eliminado switch NAME_TOO_LONG/EMPTY_NAME)
frontend/tests/dashboard-page.test.tsx         (MODIFICADO — test 3 reescrito + nuevo test maxLength)
```

---

## 2026-08-31 — Capa Frontend 4: Sidebar + Obligaciones (listado + creación)

### Qué se implementó

#### 1. Sidebar de navegación (`frontend/src/app/(app)/layout.tsx`)

- **`AppSidebar`**: Componente con links a Dashboard (`/dashboard`) y Obligaciones (`/obligations`).
- Link activo marcado con `bg-blue-50 text-blue-700 font-medium border-r-2 border-blue-600`, detectado vía `usePathname()` de `next/navigation`.
- Layout flex: sidebar fijo `w-48` a la izquierda + contenido principal `flex-1` a la derecha.
- `AppHeader` se mantiene arriba (sobre todo el layout), sidebar va debajo.

#### 2. Funciones de obligaciones (`frontend/src/lib/api-client.ts`)

- **`Obligation`** interface: tipado completo de la respuesta del backend (19 campos).
- **`ObligationCreateInput`** interface: campos para creación (13 campos, sin `category_id`/`payment_method_id`/`responsible_user_id`/`external_reference` — omitidos intencionalmente, van en prompt futuro).
- **`listObligations(groupId)`**: GET `/groups/{id}/obligations`.
- **`createObligation(groupId, data)`**: POST `/groups/{id}/obligations`.

#### 3. Página de obligaciones (`frontend/src/app/(app)/obligations/page.tsx`)

- **Carga de datos**: Llama `listObligations(currentGroupId)` al montar.
- **Estado vacío**: "Aún no tienes obligaciones registradas."
- **Sin grupo**: Mensaje con link a Dashboard para crear uno primero.
- **Error de carga**: Mensaje inline rojo.
- **Tabla** (1+ obligaciones): Nombre, Proveedor ("—"), Monto formateado (toLocaleString "es-CO"), Periodicidad traducida, Vencimiento, Esencial (badge).
- **Creación**: Botón "+ Nueva obligación" (solo visible si `my_role` es "owner" o "admin"). Form con validación client-side: nombre requerido (maxLength 200), día 1-31, mes requerido solo para Anual, fecha inicio requerida, fecha fin >= fecha inicio.
- **Manejo de errores de creación**: `FORBIDDEN_NOT_ADMIN` → "No tienes permisos para crear obligaciones." Otros errores → fallback genérico.

#### 4. `GroupProvider` con `initialState` (`frontend/src/lib/groups-context.tsx`)

- Nuevo prop `initialState?: Partial<GroupsState>` para testing. Cuando se provee, el useEffect de carga de grupos se salta. Solo para testing, no para uso en producción.

### Decisiones de diseño

1. **Omisión intencional de campos en el form**: `category_id`, `payment_method_id`, `responsible_user_id` y `external_reference` no se incluyen en este prompt porque requieren listados de categorías, medios de pago y miembros del grupo que no existen en el frontend todavía. Se agregan en un prompt futuro. No se inventan selects "por si acaso".

2. **Monto como estado separado**: El campo "Monto esperado" se maneja como `useState<string>` independiente (`monto`), no como parte de `ObligationCreateInput`. Se convierte a `expected_amount_cents` con `Math.round(parseFloat(monto) * 100)` al enviar. Esto permite input de display (ej. "15.900") sin la fricción de parsear cents.

3. **Error handling fiel al backend**: Solo se mapea `FORBIDDEN_NOT_ADMIN` (único código de negocio real para este flujo). No se mapean `CATEGORY_NOT_IN_GROUP`, `PAYMENT_METHOD_NOT_IN_GROUP` ni `RESPONSIBLE_NOT_GROUP_MEMBER` — no pueden ocurrir porque el form nunca envía esos campos. Cualquier otro error (incluyendo 422 de Pydantic sin `code`) cae al fallback genérico.

4. **`initialState` en `GroupProvider`**: Agregado un prop opcional para testing que permite inicializar el estado sin hacer la llamada a `GET /groups`. El `useEffect` de carga se salta cuando `initialState` está presente. Esto evita tener que mockear `GET /groups` en cada test de la página de obligaciones.

### Tests — 13 nuevos en `obligations-page.test.tsx` + 2 nuevos en `app-layout.test.tsx`

#### `tests/obligations-page.test.tsx` (13 tests)

| # | Test | Verifica |
|---|------|----------|
| 1 | shows empty state when no obligations exist | Mensaje "Aún no tienes obligaciones registradas." |
| 2 | renders table with obligation data | Nombre, proveedor, monto, periodicidad, vencimiento, badge |
| 3 | hides create button when role is member | Botón NO está en el DOM |
| 4 | shows create button when role is owner | Botón visible |
| 5 | shows create button when role is admin | Botón visible |
| 6 | creates obligation and updates table | POST disparado, tabla actualiza, form resetea |
| 7 | shows annual month field only when periodicity is annual | Campo aparece/desaparece con el select |
| 8 | validates annual due_month required | Error inline al enviar sin mes |
| 9 | hides month field when periodicity is not annual | Campo no está en DOM |
| 10 | shows FORBIDDEN_NOT_ADMIN error message | Mensaje específico de 403 |
| 11 | shows generic error for unexpected 500 | Mensaje genérico |
| 12 | shows message to create group when no currentGroup | Mensaje + link a /dashboard |
| 13 | shows load error when listObligations fails | Mensaje de error de carga |

#### `tests/app-layout.test.tsx` (2 tests nuevos)

| # | Test | Verifica |
|---|------|----------|
| 1 | has sidebar with Dashboard and Obligaciones links | Links con href correctos, Dashboard activo por defecto |
| 2 | highlights Obligaciones link when on /obligations | Link activo tiene `bg-blue-50`, inactivo no |

### Verificación

```
$ cd frontend && npm run build
✓ Compiled successfully
✓ Generating static pages (8/8)
Route (app)                              Size     First Load JS
┌ ○ /                                    2.71 kB        90 kB
├ ○ /dashboard                           3.37 kB     90.7 kB
├ ○ /obligations                         4.64 kB      101 kB
├ ○ /login                               2.46 kB     99.2 kB
└ ○ /register                            2.99 kB     99.7 kB

$ cd frontend && npm run lint
✔ No ESLint warnings or errors

$ cd frontend && npm test
✓ tests/obligations-page.test.tsx (13 tests) 818ms
Test Files  9 passed (9)
Tests  62 passed (62)
```

### Archivos creados o modificados

```
frontend/src/app/(app)/
├── layout.tsx                    (MODIFICADO — +AppSidebar, +usePathname, +Link, layout flex)
└── obligations/
    └── page.tsx                  (NUEVO — listado + creación de obligaciones)

frontend/src/lib/
├── api-client.ts                 (MODIFICADO — +Obligation, +ObligationCreateInput, +listObligations, +createObligation)
└── groups-context.tsx            (MODIFICADO — +initialState prop en GroupProvider)

frontend/tests/
├── handlers.ts                   (MODIFICADO — +GET/POST /groups/:id/obligations)
├── obligations-page.test.tsx     (NUEVO — 13 tests)
└── app-layout.test.tsx           (MODIFICADO — +2 tests de sidebar)
```

### Preguntas abiertas para el siguiente prompt

1. **Selects de categoría/medio de pago/responsable**: Una vez que existan los listados de categorías, medios de pago y miembros del grupo en el frontend, se agregan como campos en el form de creación de obligaciones (`category_id`, `payment_method_id`, `responsible_user_id`).

2. **Paginación/filtros en listado de obligaciones**: Actualmente carga todas las obligaciones de golpe. Para grupos con muchas obligaciones, se necesitará paginación o filtros por periodicidad/estado.

3. **Pagos (Capa 5 del README original)**: Registrar pagos contra obligaciones, historial de pagos, estados de pago.

---

## Capa Frontend 5 — Detalle, edición y eliminación de obligaciones

### Qué se construyó

1. **`api-client.ts` — 3 funciones nuevas + 1 interfaz**:
   - `getObligation(groupId, id)` → `GET /groups/{groupId}/obligations/{id}`
   - `updateObligation(groupId, id, data)` → `PATCH /groups/{groupId}/obligations/{id}`
   - `deactivateObligation(groupId, id)` → `DELETE /groups/{groupId}/obligations/{id}` (soft-delete, 204)
   - `ObligationUpdateInput` — todos los campos editables opcionales. `provider_name`, `notes`, `due_month`, `end_date` aceptan `null` para borrar valores.

2. **`lib/obligation-format.ts` — utilidades compartidas** (extraídas de `obligations/page.tsx`):
   - `PERIODICITY_LABELS` — traducción al español de periodicidades
   - `formatAmount(cents, currency)` — formato moneda con `toLocaleString("es-CO")`
   - `formatDueDate(obligation)` — texto legible de vencimiento

3. **`components/ObligationForm.tsx` — componente de formulario compartido**:
   - Props: `mode: "create"|"edit"`, `initialValues?`, `onSubmit`, `onCancel?`, `submitLabel`, `error?`, `submitting?`
   - Internamente maneja `monto` como string para el input, convierte a `expected_amount_cents` al enviar
   - Validación client-side: nombre requerido (≤200), día 1-31, mes requerido solo para Anual, fecha inicio requerida solo en create, fecha fin ≥ fecha inicio
   - En modo edit: envía `end_date: null` explícitamente (no lo omite), `provider_name: null` y `notes: null` para campos vacíos
   - Reemplaza el form inline de ~150 líneas que existía en `obligations/page.tsx`

4. **`obligations/[id]/page.tsx` — página de detalle** (nueva):
   - `useParams()` para obtener el id, `useRouter()` para redirects
   - Vista de detalle: todos los campos formateados, 4 flags como badges Sí/No con colores distintos
   - Estados de carga: "Cargando..." mientras carga. 404 → "Obligación no encontrada." + link a /obligations. Otro error → "No se pudo cargar la obligación."
   - **Edición** (solo admin/owner): botón "Editar" muestra `ObligationForm` pre-llenado. Errores: FORBIDDEN_NOT_ADMIN → mensaje específico, OBLIGATION_NOT_FOUND → redirige a /obligations, otro → fallback genérico
   - **Eliminación** (solo admin/owner): botón "Eliminar" muestra confirmación inline (sin `window.confirm`). "Confirmar" llama `deactivateObligation` y redirige. "Cancelar" oculta la confirmación. Errores: FORBIDDEN_NOT_ADMIN → mensaje específico sin redirigir, OBLIGATION_NOT_FOUND → redirige igual (ya eliminada), otro → fallback sin redirigir
   - Para member: ni "Editar" ni "Eliminar" existen en el DOM (no solo ocultos)

5. **`obligations/page.tsx` — modificaciones**:
   - Reemplaza form inline por `<ObligationForm mode="create" ...>`
   - Nombre de cada obligación en la tabla es un `<Link href={/obligations/${o.id}}>` (estilo azul)
   - Elimina código duplicado de formatting (usa `obligation-format.ts`)

### Decisiones de diseño

1. **`ObligationForm` compartido**: Se extrajo el form de ~150 líneas de JSX casi idénticas entre creación y edición. Esto no contradice la decisión de "sin componentes UI genéricos" (esa fue sobre Button/Card/Input de diseño visual; esto es lógica de negocio/formulario repetida, que sí conviene extraer).

2. **No replicar el sentinel `"unset"` del backend**: El schema `ObligationUpdate` del backend tiene un mecanismo interno de sentinel `"unset"` para `end_date`, pero no está cubierto por ningún test del backend. Se usó `null` normal (que sí está testeado) como camino probado para borrar la fecha de fin.

3. **`provider_name` y `notes` como `string | null` en `ObligationUpdateInput`**: A diferencia de la versión de create donde se usaba `undefined` (omitiendo el campo), en update se envía `null` explícitamente para limpiar campos. Esto permite al backend distinguir entre "no se envió el campo" (no cambia) y "se envió null" (borra el valor).

4. **Confirmación de eliminación inline**: Se evitó `window.confirm` por ser menos testeable. Se usa un estado local `confirmingDelete` con botones "Confirmar"/"Cancelar" renderizados condicionalmente.

### Tests — 14 nuevos

#### `tests/obligation-detail-page.test.tsx` (13 tests nuevos)

| # | Test | Verifica |
|---|------|----------|
| 1 | shows obligation data when loaded successfully | Todos los campos, badges, monto formateado |
| 2 | shows 'Obligación no encontrada.' on 404 | Mensaje + link de vuelta |
| 3 | does not show edit/delete buttons when role is member | Botones NO están en el DOM |
| 4 | shows edit/delete buttons when role is owner | Botones visibles |
| 5 | shows edit/delete buttons when role is admin | Botones visibles |
| 6 | edit: shows form pre-filled and saves changes | Valores iniciales, PATCH disparado, vista actualiza |
| 7 | edit: validates annual due_month required | Error inline al cambiar a ANNUAL sin mes |
| 8 | edit: shows FORBIDDEN_NOT_ADMIN error | Mensaje específico de 403 |
| 9 | delete: shows confirmation, cancel hides it | Confirmación aparece/desaparece, sin DELETE |
| 10 | delete: confirm calls DELETE and redirects | DELETE disparado, router.push a /obligations |
| 11 | delete: FORBIDDEN_NOT_ADMIN shows error without redirecting | Mensaje específico, sin redirect |
| 12 | shows generic error when load fails | Mensaje de error de carga |
| 13 | renders obligation name as link to detail page (en obligations-page.test.tsx) | Link con href correcto |

### Verificación pendiente

Node.js no está disponible en este entorno. Ejecutá localmente:

```bash
cd frontend && npm run build
cd frontend && npm run lint
cd frontend && npm test
```

### Archivos creados o modificados

```
frontend/src/lib/
├── api-client.ts                 (MODIFICADO — +getObligation, +updateObligation, +deactivateObligation, +ObligationUpdateInput)
└── obligation-format.ts          (NUEVO — PERIODICITY_LABELS, formatAmount, formatDueDate)

frontend/src/components/
└── ObligationForm.tsx            (NUEVO — form compartido create/edit)

frontend/src/app/(app)/obligations/
├── page.tsx                      (MODIFICADO — usa ObligationForm, links en nombres)
└── [id]/
    └── page.tsx                  (NUEVO — detalle, edición, eliminación)

frontend/tests/
├── handlers.ts                   (MODIFICADO — +GET/:id 404, +PATCH, +DELETE 204)
├── obligation-detail-page.test.tsx (NUEVO — 13 tests)
└── obligations-page.test.tsx     (MODIFICADO — +1 test de links)
```

### Preguntas abiertas para el siguiente prompt

1. **Selects de categoría/medio de pago/responsable**: Una vez que existan los listados de categorías, medios de pago y miembros del grupo en el frontend, se agregan como campos en el form de creación/edición de obligaciones (`category_id`, `payment_method_id`, `responsible_user_id`).

2. **Pagos (Capa 5 del README original)**: Registrar pagos contra obligaciones, historial de pagos, estados de pago.

3. **Paginación/filtros en listado de obligaciones**: Actualmente carga todas las obligaciones de golpe. Para grupos con muchas obligaciones, se necesitará paginación o filtros por periodicidad/estado.

---

## Corrección — Bug de tipos en ObligationForm onSubmit

### Problema

`ObligationFormProps.onSubmit` está tipado como `(data: ObligationCreateInput | ObligationUpdateInput) => Promise<void>`. Los call sites pasaban handlers con firmas más estrechas:

- `obligations/page.tsx`: `handleCreate(data: ObligationCreateInput)` — no acepta `ObligationUpdateInput`
- `obligations/[id]/page.tsx`: `handleUpdate(data: ObligationUpdateInput)` — no acepta `ObligationCreateInput`

Con `strict: true`, TypeScript aplica contravarianza en parámetros de función: la unión completa no es asignable a ninguna de las dos firmas estrechas individualmente. Esto produce error de tipos en ambos call sites.

### Fix

Ampliá la firma de ambos handlers para aceptar la unión completa y hacer cast explícito interno (sabemos por construcción que el tipo real siempre es el correcto por el `mode` fijo pasado a `ObligationForm`):

- `handleCreate(data: ObligationCreateInput | ObligationUpdateInput)` + `const input = data as ObligationCreateInput`
- `handleUpdate(data: ObligationCreateInput | ObligationUpdateInput)` + `const input = data as ObligationUpdateInput`

### Verificación pendiente

Node.js no está disponible en este entorno. Ejecutá localmente:

```bash
cd frontend && npm run build && npm run lint && npm run test
```

---

## Corrección — Ruta `[id]` incompatible con `output: 'export'`

### Problema

`obligations/[id]/page.tsx` usaba un segmento dinámico `[id]` en la ruta. Con `output: 'export'` (export estático puro, ADR-006), Next.js requiere `generateStaticParams()` para enumerar todos los valores posibles del segmento en build time. Los IDs de obligaciones se crean en runtime, así que es imposible enumerarlos — el build falla con:

```
Error: Page "/obligations/[id]" is missing "generateStaticParams()" so it cannot be used with "output: export" config.
```

### Fix

1. **Ruta renombrada**: `obligations/[id]/page.tsx` → `obligations/detail/page.tsx`
2. **Query param en vez de segmento dinámico**: el componente ahora lee el id de `useSearchParams().get("id")` en vez de `useParams().id`
3. **Links actualizados**: `/obligations/${o.id}` → `/obligations/detail?id=${o.id}`
4. **Tests ajustados**: import, mock de `useSearchParams` en vez de `useParams`, href esperado

`docs/adr/ADR-006-estructura-frontend.md` ya documenta este patrón (ruta estática + query param) como el correcto para cualquier página de detalle futura.

### Fix menor — ESLint warning en `groups-context.tsx`

El comentario `// eslint-disable-next-line react-hooks/exhaustive-deps` estaba antes del `useEffect` (línea 53) pero ESLint reporta el warning en la línea del array de dependencias (`}, []);`, línea 96). Se movió el comentario a inmediatamente antes de `}, []);`.

### Verificación

```
$ cd frontend && npm run build
✓ Compiled successfully
✓ Generating static pages (9/9)
Route (app)                              Size     First Load JS
├ ○ /obligations                         1.6 kB          102 kB
├ ○ /obligations/detail                  2.23 kB         103 kB

$ cd frontend && npm run lint
✔ No ESLint warnings or errors

$ cd frontend && npm test
 Test Files  10 passed (10)
      Tests  75 passed (75)
```

---

## 2026-08-31 — Capa Frontend 6: Pagos (registrar pago contra período)

### Qué se construyó

1. **`layout.tsx` — Sidebar con link "Pagos"**:
   - Agregado `{ href: "/payments", label: "Pagos" }` a `NAV_ITEMS`.

2. **`api-client.ts` — 3 tipos + 2 funciones nuevas**:
   - `ObligationPeriod` interface: `id`, `obligation_id`, `period_month`, `due_date`, `status ("PENDIENTE"|"PAGADO"|"VENCIDO")`, `created_at`.
   - `PaymentCreateInput` interface: `amount_cents`, `currency ("COP"|"USD")`, `paid_at`, `notes?`, `receipt_url?`.
   - `Payment` interface: modelo completo del pago.
   - `listPeriods(groupId)` → `GET /groups/{groupId}/periods`
   - `registerPayment(groupId, periodId, data)` → `POST /groups/{groupId}/periods/{periodId}/payments`

3. **`payments/page.tsx` — Página de pagos pendientes** (nueva):
   - **Carga**: `Promise.all([listObligations, listPeriods])` al montar. Cruza períodos con obligaciones via `Map<number, Obligation>` por `obligation_id`.
   - **Filtrado**: excluye períodos con status `PAGADO` y períodos cuya `obligation_id` no tiene match en el mapa de obligaciones. Ordena por `due_date` ascendente.
   - **Formato de fecha**: parseo directo del string `YYYY-MM-DD` (no `new Date()`) para evitar desfase de timezone en Colombia (UTC-5).
   - **Estados**: "Cargando..." / "Primero creá un grupo..." / "No se pudieron cargar los pagos pendientes." / "No hay pagos pendientes."
   - **Tabla**: nombre de obligación, monto formateado (`formatAmount`), fecha de vencimiento formateada, badge de estado (Pendiente = amarillo, Vencido = rojo).
   - **Botón "Registrar pago"**: visible solo si `canPay(obligation)` — owner/admin del grupo, o `responsible_user_id` de la obligación coincide con `user.id`. No está en el DOM cuando canPay es false.
   - **Form inline**: se expande debajo de la tabla al hacer click. Campos: monto (pre-cargado con `expected_amount_cents/100`), moneda (texto fijo, NO editable), fecha de pago (default hoy), notas (opcional), URL de comprobante (opcional).
   - **Moneda nunca es editable**: el form SIEMPRE envía `currency: obligation.currency`, lo que hace imposible el error `CURRENCY_MISMATCH` desde el frontend.
   - **Manejo de errores**:
     - `PERIOD_ALREADY_PAID` → mensaje + el período desaparece de la lista (alguien más lo pagó).
     - `FORBIDDEN_NOT_RESPONSIBLE` → "No tienes permisos para registrar este pago."
     - Otros → "No se pudo registrar el pago. Intenta de nuevo."

4. **`tests/handlers.ts` — 2 handlers nuevos**:
   - `GET /groups/:groupId/periods` → retorna `[]` por defecto.
   - `POST /groups/:groupId/periods/:periodId/payments` → crea el pago con id: 1, registered_by_user_id: 1.

5. **`tests/payments-page.test.tsx` — 16 tests**:
   - Empty state: "No hay pagos pendientes."
   - Renderiza fila con nombre, monto, fecha, badge.
   - Período PAGADO no aparece en la lista.
   - Botón visible con role owner.
   - Botón visible con member + responsible_user_id === user.id.
   - Botón NO visible con member + responsible_user_id null.
   - Botón NO visible con member + responsible_user_id !== user.id.
   - Pago exitoso: período desaparece de la lista.
   - Error PERIOD_ALREADY_PAID: mensaje correcto + período desaparece.
   - Error FORBIDDEN_NOT_RESPONSIBLE: mensaje específico.
   - Currency siempre coincide con la de la obligación (verifica `body.currency`).
    - No-group prompt.
    - Load error.
    - Excludes periods whose obligation no longer exists (post-review).
    - Prefills 'Monto pagado' with the obligation's expected amount (post-review).
    - Cancel closes the form without calling the payments endpoint (post-review).

6. **`tests/app-layout.test.tsx` — 1 test nuevo**:
   - Verifica que el link "Pagos" existe con `href="/payments"`.

### Decisiones de diseño

1. **Moneda no editable en el form**: La moneda se toma directamente de la obligación (`obligation.currency`) y nunca se envía como input del usuario. Esto previene el error `CURRENCY_MISMATCH` del backend de forma completa. No hay un select de moneda en el form — el usuario simplemente ve "Moneda: COP" (o USD) como texto.

2. **Casi ninguna obligación será pagable por un member hoy**: Dado que `responsible_user_id` es `null` en casi todas las obligaciones existentes (el select de responsable no existe todavía — ver Capa 5 deferred), la función `canPay` solo retorna `true` para owner/admin. Esto es correcto y no es un bug — cuando exista el select de responsable en el form de obligaciones, los members podrán pagar sus obligaciones asignadas.

3. **Fecha de vencimiento sin `new Date()`**: El string `due_date` viene como `YYYY-MM-DD`. Usar `new Date(due_date)` interpreta la fecha como UTC medianoche, lo que en timezone Colombia (UTC-5) puede mostrar un día menos. Se parsea directamente con `split("-")`.

4. **Períodos de obligaciones desactivadas excluidos**: Si un período tiene `obligation_id` que no existe en el mapa de obligaciones, se excluye de la lista. Esto cubre el caso edge de obligaciones borradas/desactivadas.

5. **Error de pago se muestra a nivel de página**: El `payError` se muestra arriba de la tabla (no dentro del form inline) para que sea visible incluso cuando el form se cierra después de un `PERIOD_ALREADY_PAID`.

### Tests — 17 nuevos, 92 total, todos pasando

```
$ cd frontend && npm test
✓ tests/payments-page.test.tsx (16 tests) 707ms
✓ tests/app-layout.test.tsx (6 tests) 336ms
Test Files  11 passed (11)
      Tests  92 passed (92)
```

### Build y lint

```
$ cd frontend && npm run build
✓ Compiled successfully
✓ Generating static pages (10/10)
Route (app)                              Size     First Load JS
├ ○ /payments                            4.54 kB         101 kB
○ (Static) prerendered as static content

$ cd frontend && npm run lint
✔ No ESLint warnings or errors
```

### Archivos creados o modificados

```
frontend/src/app/(app)/
├── layout.tsx                    (MODIFICADO — +Pagos en NAV_ITEMS)
└── payments/
    └── page.tsx                  (NUEVO — página de pagos pendientes + form inline)

frontend/src/lib/
└── api-client.ts                 (MODIFICADO — +ObligationPeriod, +PaymentCreateInput, +Payment, +listPeriods, +registerPayment)

frontend/tests/
├── handlers.ts                   (MODIFICADO — +GET /periods, +POST /periods/:id/payments)
├── payments-page.test.tsx        (NUEVO — 13 tests)
└── app-layout.test.tsx           (MODIFICADO — +1 test de link Pagos)
```

### Preguntas abiertas — próximos prompts

1. **Historial de pagos + anular pago**: `GET /groups/{group_id}/payments` (historial) y `POST /groups/{group_id}/payments/{id}/void` (anular) — quedan para el siguiente prompt.

2. **Select de responsable en obligaciones**: Bloqueado hasta que exista `GET /groups/{group_id}/members` en el backend (no es un problema de frontend). Una vez que exista, se agrega `responsible_user_id` al form de creación/edición de obligaciones, y los members podrán pagar sus obligaciones asignadas.

---

## 2026-08-31 — Capa Frontend 7: Historial de pagos + anular pago

### Qué se construyó

1. **`api-client.ts` — 2 funciones nuevas**:
   - `listPayments(groupId)` → `GET /groups/{groupId}/payments` — retorna `Payment[]` (incluye anulados).
   - `voidPayment(groupId, paymentId)` → `POST /groups/{groupId}/payments/{paymentId}/void` — retorna `Payment` actualizado.

2. **`payments/page.tsx` — refactor de estado + sección "Historial de pagos"**:
   - **Refactor `periods` → `allPeriods`**: el state ahora almacena la lista SIN filtrar (tal cual viene de `listPeriods`). Esto es necesario porque el historial necesita cruzar CUALQUIER pago con su período, incluidos los PAGADO.
   - **`pendingPeriods` derivado en render**: la lista filtrada (sin PAGADO, sin huérfanos) se calcula como variable derivada en cada render, no como state. Es O(n) y n es chico.
   - **`periodsById` map**: `Map(allPeriods.map(p => [p.id, p]))` — se calcula en render para resolver `obligation_period_id` → período → `obligation_id` → obligación.
   - **`payments` state + `listPayments` en `Promise.all`**: se suma al load inicial junto a `listObligations` y `listPeriods`.
   - **Sección "Historial de pagos"**: debajo de "Pagos pendientes". Muestra tabla con columnas: Obligación, Monto pagado, Fecha de pago, Estado, Acción.
     - **Vacío**: "Aún no hay pagos registrados." cuando `payments.length === 0`.
     - **Orden**: por `paid_at` descendente (comparación lexicográfica de strings `YYYY-MM-DD`).
     - **Resolución de nombre**: `periodsById.get(payment.obligation_period_id)` → `obligationsMap.get(period.obligation_id)`. Si no hay match, muestra "Obligación eliminada" (no oculta la fila — es un registro histórico).
     - **Badges**: "Activo" (verde) si `voided_at === null`, "Anulado" (gris) si no.
   - **Botón "Anular"**: solo visible si `!payment.voided_at && canVoid(payment)`. La función `canVoid` replica la lógica de `canPay`: owner/admin, o `responsible_user_id` coincide con `user.id`. Si no hay match de período/obligación, `canVoid` retorna `false`.
   - **Flujo de anular**: `voidingPaymentId: number | null` — click "Anular" → confirmación inline "¿Anular este pago? El período volverá a quedar pendiente." con "Confirmar"/"Cancelar". "Cancelar" cierra sin llamar al endpoint. "Confirmar" llama `voidPayment`:
     - Éxito: reemplaza el payment en state con la respuesta del backend (ya trae `voided_at`/`voided_by_user_id` seteados).
     - `PAYMENT_ALREADY_VOIDED` (409): actualiza localmente el payment como anulado + muestra "Este pago ya fue anulado."
     - `FORBIDDEN_NOT_RESPONSIBLE` (403): "No tienes permisos para anular este pago."
     - Otro error: "No se pudo anular el pago. Intenta de nuevo."
   - **Simplificación deliberada**: anular un pago desde el historial NO resincroniza automáticamente la sección "Pagos pendientes". El usuario debe recargar la página para ver el período como pendiente de nuevo. Esto se documenta como decisión de diseño, no es un bug.

3. **`tests/handlers.ts` — handler nuevo**:
   - `GET /groups/:groupId/payments` → retorna `[]` por defecto.

4. **`tests/payments-page.test.tsx` — 11 tests nuevos** (16 → 27):
   - "Aún no hay pagos registrados." cuando payments vacío.
   - Renderiza fila de historial con obligación, monto, fecha, badge "Activo".
   - Payment voided muestra badge "Anulado" y NO botón "Anular".
   - Payment sin período matchea muestra "Obligación eliminada" y no revienta.
   - Botón "Anular" visible para owner.
   - Botón "Anular" visible para member con `responsible_user_id` match.
   - Botón "Anulado" oculto para member sin ser responsable.
   - Click "Anular" → "Cancelar" oculta confirmación sin llamar void.
   - Click "Anular" → "Confirmar" llama void, fila pasa a "Anulado".
   - Error `FORBIDDEN_NOT_RESPONSIBLE`: mensaje específico.
   - Error `PAYMENT_ALREADY_VOIDED`: mensaje + fila marcada como "Anulado".

### Decisiones de diseño

1. **Refactor `periods` → `allPeriods` + `pendingPeriods` derivado**: el state original almacenaba la lista YA FILTRADA (sin PAGADO), lo que hacía imposible cruzar pagos del historial con sus períodos. El refactor guarda la lista cruda y filtra en render. Esto es más simple y correcto — la fuente de verdad es `allPeriods`, y `pendingPeriods` es una vista derivada.

2. **"Obligación eliminada" en vez de ocultar filas huérfanas**: en "Pagos pendientes" se excluyen períodos sin obligación (no tienen sentido mostrar algo que no se puede pagar). En el historial, en cambio, es un registro contable — ocultar filas rompería la trazabilidad. Se muestra "Obligación eliminada" y se oculta el botón "Anular" (no se puede verificar permisos sin la obligación).

3. **Anulación no resincroniza pendientes**: cuando se anula un pago, el backend recalcula el status del período (`PENDIENTE` o `VENCIDO`). Sin embargo, en este prompt la sección "Pagos pendientes" NO se resincroniza automáticamente al anular un pago desde el historial. La razón: haría falta refetchear `listPeriods` después de cada void, o mantener un state derivado complejo. La simplificación (el usuario recarga la página) es aceptable para el MVP. Se documenta como decisión deliberada.

4. **`voidError` se muestra debajo del historial**: el error de void se muestra después de la tabla de historial (no dentro de la fila) para que sea visible incluso cuando se cierra la confirmación inline.

### Tests — 11 nuevos, 103 total, todos pasando

```
$ cd frontend && npm test
✓ tests/payments-page.test.tsx (27 tests) 1070ms
Test Files  11 passed (11)
      Tests  103 passed (103)
```

### Build y lint

```
$ cd frontend && npm run build
✓ Compiled successfully
Route (app)                              Size     First Load JS
├ ○ /payments                            5.16 kB         102 kB

$ cd frontend && npm run lint
✔ No ESLint warnings or errors
```

### Archivos creados o modificados

```
frontend/src/lib/
└── api-client.ts                 (MODIFICADO — +listPayments, +voidPayment)

frontend/src/app/(app)/payments/
└── page.tsx                      (MODIFICADO — refactor periods→allPeriods, +historial, +void)

frontend/tests/
├── handlers.ts                   (MODIFICADO — +GET /payments)
└── payments-page.test.tsx        (MODIFICADO — +11 tests, 16→27)
```

### Único frente pendiente

**Select de responsable en obligaciones**: bloqueado hasta que exista `GET /groups/{group_id}/members` en el backend (no es un problema de frontend). Una vez que exista, se agrega `responsible_user_id` al form de creación/edición de obligaciones, y los members podrán pagar sus obligaciones asignadas.
