# Checklist de seguridad — pre-lanzamiento a la familia

- [ ] `JWT_SECRET` generado con `openssl rand -hex 32`, distinto entre dev/staging/prod.
- [ ] `.env` real en `.gitignore` (nunca commiteado); solo `.env.*.example` en el repo.
- [ ] CORS restringido al dominio exacto de producción (no `*`, no wildcard de subdominios sin necesidad).
- [ ] Rate limiting activo en `/auth/login`, `/auth/register`, `/auth/refresh`.
- [ ] Ningún campo de `payment_methods` almacena PAN completo, CVV o PIN (verificado contra `schema.sql`).
- [ ] Todo endpoint mutante tiene al menos un test de autorización cruzada entre grupos (ADR-009).
- [ ] `AuditLog` registrando altas/bajas de miembros y cambios de rol.
- [ ] Backup semanal (`backup.yml`) corriendo y verificado manualmente al menos una vez (restaurar el dump en local).
- [ ] HTTPS confirmado en dominios de Cloudflare Pages y Render (por defecto, pero verificar certificado válido tras el primer deploy).
- [ ] Secrets de producción (`PRODUCTION_DATABASE_URL`, `JWT_SECRET`) cargados como GitHub/Render/Cloudflare secrets, no en texto plano en ningún archivo del repo.
