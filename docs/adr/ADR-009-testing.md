# ADR-009: Estrategia de testing

## Decisión

**Backend**
- `pytest` + `pytest-asyncio` + `httpx.AsyncClient` contra la app FastAPI in-process (sin levantar servidor real).
- DB de test: Postgres real (no SQLite) vía contenedor Docker efímero en CI, para no ocultar diferencias de dialecto (ENUMs, `CITEXT`, constraints parciales del schema). Cada test corre dentro de una transacción que se revierte al final (fixture `conftest.py`), aislando tests entre sí sin recrear el schema por test.
- Cobertura mínima exigida en CI: unit tests de `service` (reglas de negocio: cálculo de `period_status`, invariante de un solo owner, enforcement de pertenencia a grupo) + integration tests de cada router (happy path + 401/403/404).
- Tests de autorización explícitos: por cada endpoint mutante, al menos un test que confirma que un `member` de OTRO grupo recibe 403/404 (nunca filtrar datos entre grupos — el riesgo #1 de este dominio).

**Frontend**
- `Vitest` + `@testing-library/react` para componentes críticos: formulario de obligación, tabla de dashboard, flujo de login/refresh.
- Mock de `api-client.ts` a nivel de MSW (Mock Service Worker) para tests de integración de página sin pegarle a un backend real.

**E2E**
- Fuera del MVP (confirmado por el documento fuente). Cuando se aborde: Playwright cubriendo los 6 flujos listados en la sección 19 (Registro, Login, Crear grupo, Agregar obligación, Registrar pago, Consultar dashboard).

## Consecuencias

- Requiere Postgres disponible en el job de CI del backend (servicio Docker
  del propio workflow, ver ADR-010) — más lento que SQLite in-memory, pero
  elimina falsos positivos por diferencias de dialecto que SQLite no puede
  reproducir (ENUMs nativos, `CITEXT`, índices parciales).
