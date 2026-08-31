# ADR-008: Seguridad

## Decisión

- **Password hashing**: Argon2id (`argon2-cffi`), no bcrypt — mejor
  resistencia a ataques con GPU/ASIC, parámetros de memoria configurables vía
  `core/security.py`.
- **JWT**: HS256, secret de 256 bits mínimo en `JWT_SECRET` (env var, nunca en
  código ni en el repo). Rotación de secret invalida todas las sesiones —
  aceptable, documentado como procedimiento manual de emergencia.
- **CORS**: allow-list exacta del dominio de Cloudflare Pages (no `*`),
  `allow_credentials=True` solo para ese origen.
- **Rate limiting**: `slowapi` (o equivalente) en `/auth/login`,
  `/auth/register`, `/auth/refresh` — ej. 10 intentos/min/IP — mitiga
  brute-force sin infra adicional (in-memory, suficiente al volumen de uso).
- **Validación de input**: Pydantic v2 en cada schema de entrada; nunca
  `**request.json()` sin validar.
- **Datos sensibles — regla dura**: ninguna tabla, columna, log ni
  `AuditLog.metadata` puede contener PAN completo, CVV, PIN o credenciales
  bancarias. Enforced también a nivel de code review (checklist en
  `ADR-009`/CI: grep de patrones tipo `card_number`, `cvv`, `pin` en el diff
  como gate adicional, opcional).
- **Auditoría**: toda mutación relevante (crear/editar/eliminar obligación,
  registrar pago, cambios de membresía) pasa por `audit.service.log_action`
  (ADR-005) con `actor_user_id`, `group_id`, acción y entidad.
- **HTTPS**: garantizado por Cloudflare Pages y Render por defecto, no
  requiere configuración manual de certificados.
- **Secretos**: GitHub Actions Secrets para CI; variables de entorno nativas
  de Render/Cloudflare Pages en runtime — nunca `.env` commiteado (ver
  `.env.*.example` en el repo, con placeholders).

## Consecuencias

- El rate limiting in-memory se pierde si Render reinicia la instancia
  (cold start tras sleep) — aceptable para el MVP; si se requiere persistente,
  migrar a Redis en V2 es un cambio aislado a `core/security.py`.
