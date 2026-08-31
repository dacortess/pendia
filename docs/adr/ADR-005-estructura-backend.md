# ADR-005: Estructura del backend FastAPI

## Decisión

Módulo por dominio, cada uno con la misma forma interna (facilita
navegación y evita el "god file" de routers):

```
backend/
├── app/
│   ├── main.py                     # instancia FastAPI, monta routers, middlewares CORS
│   ├── core/
│   │   ├── config.py                # Settings (pydantic-settings) desde env vars
│   │   ├── security.py              # hashing Argon2id, firma/verificación JWT
│   │   └── deps.py                  # get_db, get_current_user, get_current_membership
│   ├── database/
│   │   ├── session.py                # engine, SessionLocal
│   │   └── base.py                   # Base declarativa SQLAlchemy
│   ├── auth/
│   │   ├── router.py
│   │   ├── schemas.py                # Pydantic: RegisterIn, LoginIn, TokenPair
│   │   └── service.py                # lógica de negocio (sin SQL directo)
│   ├── users/
│   │   ├── router.py / schemas.py / models.py / repository.py
│   ├── groups/
│   │   ├── router.py / schemas.py / models.py / service.py / repository.py
│   ├── obligations/
│   │   ├── router.py / schemas.py / models.py / service.py / repository.py
│   ├── payments/
│   │   ├── router.py / schemas.py / models.py / service.py / repository.py
│   ├── payment_methods/
│   ├── categories/
│   ├── dashboard/
│   │   ├── router.py                 # solo lectura, queries de agregación
│   │   └── repository.py
│   └── audit/
│       ├── models.py
│       └── service.py                 # log_action(...), llamado desde otros services
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py                    # fixtures: db de test (transacción por test), client
│   ├── auth/  groups/  obligations/  payments/  dashboard/
├── Dockerfile
├── pyproject.toml                     # ruff + mypy + pytest config
└── requirements.txt / poetry.lock
```

Reglas de capa (aplican de arriba hacia abajo, nunca al revés):

`router` (HTTP, valida input, llama service, serializa output)
→ `service` (reglas de negocio, transacciones, llama repository)
→ `repository` (SQLAlchemy puro, sin lógica de negocio)
→ `models` (tablas SQLAlchemy, sin comportamiento)

`audit.service.log_action` se invoca explícitamente desde cada `service` que
mute estado (no vía middleware genérico) — más verboso, pero cada
invocación deja claro con precisión qué se auditó, evitando side-effects
implícitos difíciles de rastrear.

Inyección de dependencias: `Depends(get_db)` por request (una sesión SQLAlchemy
por request, cerrada en el `finally` del generador); `Depends(get_current_membership)`
parametrizado por `group_id` del path, centraliza el chequeo de pertenencia
del ADR-002.

## Consecuencias

- Onboarding de un módulo nuevo (ej. `notifications` en V2) es copiar la
  forma existente, no inventar una nueva.
- Los tests de servicio pueden mockear el `repository` sin tocar Postgres;
  los tests de router usan la DB de test real vía `httpx.AsyncClient` (ver ADR-009).
