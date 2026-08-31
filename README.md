# Gestor Familiar de Pagos y Facturas — Documentación de arranque

Este repo, en este punto, es **solo planeación**. No hay código de
aplicación todavía — es intencional (ver mapa de decisiones).

## Índice

1. [`docs/00-MAPA-DECISIONES.md`](docs/00-MAPA-DECISIONES.md) — punto de entrada. Destino, decisiones tomadas, supuestos a validar, fuera de alcance.
2. `docs/adr/` — 15 ADR con el razonamiento y trade-offs de cada decisión estructural.
3. `docs/db/schema.sql` + `docs/db/erd.md` + `docs/db/seed.sql` — modelo de datos v3 (moneda COP/USD, invitación por código+QR, medios de pago de Colombia, categorías sistema+personalizadas, obligaciones enriquecidas, base de alertas), listo para generar los modelos de SQLAlchemy y la migración inicial de Alembic.
4. `docs/adr/ADR-004-api-contract.md` — contrato REST completo del MVP, incluyendo invitación por código/QR.
5. `docker-compose.yml`, `backend.env.example`, `frontend.env.example` — entorno local reproducible.
6. `.github/workflows/ci.yml` y `.github/workflows/backup.yml` — pipeline listo para copiar en cuanto exista código que lo dispare.
7. `docs/infra/security-checklist.md` — gate manual antes de exponer la app a la familia.
8. `docs/adr/ADR-011-decisiones-adicionales.md` — decisiones que el análisis original dejó fuera (anulación de pagos, timezone, recuperación de contraseña, concurrencia, observabilidad, etc.).
9. `docs/adr/ADR-012-arquitectura-alertas.md` — arquitectura $0 para alertas de vencimiento/mora vía WhatsApp (preparación de modelo, sin activar envíos en el MVP).
10. `docs/adr/ADR-013-modelo-datos-v2.md` — correcciones al modelo de datos: naming, periodicidad anual, medios de pago colombianos, categorías sistema+personalizadas, campos de obligación.
11. `docs/adr/ADR-014-invitacion-codigo-qr.md` — invitación a grupo por código alfanumérico de 8 caracteres + QR generado al vuelo.
12. `docs/adr/ADR-015-monedas-soportadas.md` — moneda restringida a `COP`/`USD`, sin conversión automática.
13. `docs/HISTORIAS-USUARIO.md` — 27 historias de usuario del MVP con criterios de aceptación, trazables a cada endpoint del contrato REST.
14. `docs/REQUISITOS-NO-FUNCIONALES.md` — RNF de seguridad, rendimiento, disponibilidad, integridad de datos, usabilidad, mantenibilidad, costo y privacidad, cada uno con su forma de verificación.

## Supuestos que requieren confirmación explícita (no bloquean empezar a programar, sí bloquean producción)

- **Rol por defecto del código de invitación familiar** (ADR-014): se asumió `member`. Si la familia prefiere que el código principal otorgue `admin` a todos, es un parámetro al crear el código, no un cambio de modelo.
- **Reset de contraseña sin proveedor de email** (ADR-011 #3): reset manual por un admin del grupo. Ver nota en `docs/adr/ADR-011-decisiones-adicionales.md`.

## Orden de implementación (capas, según sección 26 del brief original)

```
1. DB: modelos SQLAlchemy desde schema.sql + primera migración Alembic
2. Backend/Auth: core/security.py, auth/ (register, login, refresh, logout)
3. API: groups → categories/payment_methods → obligations → periods → payments → dashboard → audit
4. Frontend: auth-context + login/register → layout con guard → obligations CRUD → payments → dashboard
5. Testing: se escribe junto con cada capa (TDD por endpoint), no al final
6. Docker: docker-compose.yml ya listo, validar con `docker compose up`
7. CI/CD: ci.yml ya listo, activar branch protection en GitHub tras el primer push
8. Deploy: conectar repo a Cloudflare Pages y Render (dashboards de cada plataforma), configurar env vars de producción
```

Cada paso de este orden es, en términos de la skill de planeación usada, un
**ticket ejecutable**: sus bloqueadores son estrictamente los pasos
anteriores de esta lista, y cada uno cierra con su propio ciclo TDD +
code review antes de pasar al siguiente.
