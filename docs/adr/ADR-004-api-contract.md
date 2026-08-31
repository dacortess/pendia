# ADR-004: Contrato de API REST

## Decisión

- Prefijo `/api/v1`. Versionado por path (no por header) — más simple de
  cachear/debuggear con curl, suficiente para un solo cliente conocido.
- Recursos de negocio **siempre anidados bajo grupo**, reforzando el
  aislamiento del ADR-002 a nivel de URL:
  `/api/v1/groups/{group_id}/obligations/...`
- Paginación: `?limit=&offset=` (default `limit=50`, máx `200`). Cursor-based
  se descarta por sobre-ingeniería al volumen esperado (decenas de filas por
  grupo, no miles).
- Errores: JSON `{"detail": "...", "code": "OBLIGATION_NOT_FOUND"}` — `code`
  estable para que el frontend mapee mensajes sin parsear texto libre.
- Filtrado de listados vía query params explícitos, no un DSL genérico
  (`?status=PENDIENTE&month=2026-09`).

## Endpoints (MVP)

```
POST   /api/v1/auth/register                          (acepta invite_code opcional, ADR-014)
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

GET    /api/v1/users/me

POST   /api/v1/groups
GET    /api/v1/groups                                 (grupos del usuario actual)
GET    /api/v1/groups/{group_id}
PATCH  /api/v1/groups/{group_id}                       (owner)
POST   /api/v1/groups/{group_id}/members               (agregar por email, admin+ — alternativa secundaria, ADR-014)
PATCH  /api/v1/groups/{group_id}/members/{user_id}      (cambiar rol, admin+)
DELETE /api/v1/groups/{group_id}/members/{user_id}      (admin+)

GET    /api/v1/groups/{group_id}/invite-codes                    (admin+, lista códigos activos/histórico)
POST   /api/v1/groups/{group_id}/invite-codes                    (admin+, crea código: role_to_assign, max_uses, expires_at)
PATCH  /api/v1/groups/{group_id}/invite-codes/{id}                (admin+, revocar: is_active=false)
GET    /api/v1/groups/{group_id}/invite-codes/{id}/qr             (admin+, imagen QR generada al vuelo)
GET    /api/v1/groups/join/preview?code=                          (sin auth, retorna solo groups.name)
POST   /api/v1/groups/join                                        (autenticado, body {code}, une al usuario actual)

GET    /api/v1/groups/{group_id}/categories
POST   /api/v1/groups/{group_id}/categories             (admin+)

GET    /api/v1/groups/{group_id}/payment-methods
POST   /api/v1/groups/{group_id}/payment-methods         (admin+)
PATCH  /api/v1/groups/{group_id}/payment-methods/{id}    (admin+)

GET    /api/v1/groups/{group_id}/obligations
POST   /api/v1/groups/{group_id}/obligations             (admin+)
GET    /api/v1/groups/{group_id}/obligations/{id}
PATCH  /api/v1/groups/{group_id}/obligations/{id}        (admin+)
DELETE /api/v1/groups/{group_id}/obligations/{id}        (admin+, soft: is_active=false)

GET    /api/v1/groups/{group_id}/periods?status=&month=  (listado con filtros para dashboard)
GET    /api/v1/groups/{group_id}/periods/{id}

POST   /api/v1/groups/{group_id}/periods/{id}/payments   (registrar pago)
GET    /api/v1/groups/{group_id}/payments?...            (historial)

GET    /api/v1/groups/{group_id}/dashboard?month=2026-08 (agregados por moneda: total, pagado, pendiente, vencen_esta_semana)
```

## Consecuencias

- El "registrar pago" cuelga del período (`/periods/{id}/payments`), no de la
  obligación directamente — coherente con el modelo del ADR-003 y evita que
  el cliente tenga que resolver a qué mes pertenece un pago.
- El endpoint de dashboard hace la agregación en SQL (no en Python) para
  evitar traer todas las filas y sumarlas en memoria — ver ADR-005 para dónde
  vive ese query.
