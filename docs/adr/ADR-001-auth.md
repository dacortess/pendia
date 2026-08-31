# ADR-001: Estrategia de autenticación cross-origin

## Contexto

Frontend (Cloudflare Pages) y backend (Render) viven en **dominios distintos**.
No hay opción de cookie same-site clásica sin fricción. Opciones evaluadas:

1. JWT completo en `localStorage` — simple, pero expuesto a robo vía XSS (cualquier script inyectado exfiltra el token sin límite de vida).
2. Sesión server-side con cookie — requiere store de sesión (Redis/DB), overhead innecesario para el volumen (una familia).
3. Access token corto en memoria + refresh token en cookie httpOnly cross-site.

## Decisión

**Opción 3.**

- **Access token**: JWT, TTL 15 min, firmado HS256 con secret en env var (`JWT_SECRET`). Vive solo en memoria del cliente (estado de React, nunca en storage persistente). Se adjunta como `Authorization: Bearer <token>`.
- **Refresh token**: opaco (UUID v4 aleatorio, 32 bytes), TTL 30 días, persistido hasheado (SHA-256) en tabla `RefreshToken` (rotación: cada uso invalida el anterior y emite uno nuevo — previene replay). Entregado en cookie:
  ```
  Set-Cookie: refresh_token=<valor>; HttpOnly; Secure; SameSite=None; Path=/api/v1/auth/refresh; Max-Age=2592000
  ```
- CORS backend: `Access-Control-Allow-Origin` restringido al dominio exacto de Cloudflare Pages, `Access-Control-Allow-Credentials: true` (obligatorio para que el navegador envíe la cookie cross-site).
- Logout: borra el refresh token del cliente + invalida (borra o marca `revoked_at`) la fila en `RefreshToken`.
- Password hashing: Argon2id (ver ADR-008).

## Consecuencias

- Requiere endpoint `POST /api/v1/auth/refresh` idempotente-por-rotación y manejo de "refresh en vuelo" en el frontend (interceptor único, cola de requests mientras se refresca) para evitar condiciones de carrera con múltiples pestañas.
- `SameSite=None; Secure` exige HTTPS en ambos extremos — ya garantizado por Cloudflare Pages y Render.
- Si Render Free entra en sleep, el primer `refresh`/`login` tendrá latencia de cold start (~30-50s); el frontend debe mostrar loading state explícito, no fallar silenciosamente.
