# Mapa de decisiones — Pendia

## Destino

Documentación técnica completa (arquitectura, modelo de datos, contrato de API,
estructura de repos, infra local/CI/CD) suficiente para empezar a implementar
por capas (DB → Backend/Auth → API → Frontend → Testing → Docker → CI/CD →
Deploy) sin decisiones estructurales pendientes. Fin del mapa = cero preguntas
de arquitectura abiertas antes del primer `git init`.

## Notas

- Dominio: gestión financiera familiar (obligaciones recurrentes, pagos, medios de pago no sensibles).
- Restricción dura: $0 de costo inicial (Cloudflare Pages Free / Render Free / Supabase Free).
- Monolito modular, NO microservicios. Un solo repo backend (FastAPI) + un solo repo o monorepo frontend (Next.js).
- Todas las decisiones que no requerían input de negocio se resolvieron aquí mismo (rol de arquitecto), documentadas como ADR con su justificación y trade-offs. Las que sí lo requerían quedan marcadas explícitamente como **supuesto a validar con la familia/product owner** dentro de su ADR.

## Decisiones tomadas

| # | Decisión | Ticket/ADR | Gist |
|---|---|---|---|
| 1 | Estrategia de autenticación cross-origin | [ADR-001](adr/ADR-001-auth.md) | Access token JWT en memoria (15 min) + refresh token httpOnly/Secure/SameSite=None, dominio del backend |
| 2 | Modelo de permisos y aislamiento por grupo | [ADR-002](adr/ADR-002-permisos.md) | RBAC simple `owner/admin/member` a nivel de `GroupMembership`, sin permisos granulares por recurso en MVP |
| 3 | Modelo de datos relacional | [ADR-003](adr/ADR-003-modelo-datos.md) | 8 entidades + tabla de períodos (`ObligationPeriod`) para representar historial mensual sin duplicar la obligación |
| 4 | Contrato de API REST | [ADR-004](adr/ADR-004-api-contract.md) | REST versionado `/api/v1`, recursos anidados por grupo, paginación cursor-less (offset+limit) para MVP |
| 5 | Estructura del backend FastAPI | [ADR-005](adr/ADR-005-estructura-backend.md) | Módulos por dominio (`app/<modulo>/{router,schemas,models,service,repository}.py`), DI vía `Depends` |
| 6 | Estructura del frontend Next.js | [ADR-006](adr/ADR-006-estructura-frontend.md) | App Router, `output: export` (sitio 100% estático/cliente), fetch a la API vía cliente tipado |
| 7 | Hosting e infraestructura | [ADR-007](adr/ADR-007-infra-hosting.md) | Cloudflare Pages (estático) + Render Free (API) + Supabase Postgres Free, sin Cloudflare Pages Functions |
| 8 | Seguridad y manejo de datos sensibles | [ADR-008](adr/ADR-008-seguridad.md) | Hashing Argon2id, últimos-4-dígitos únicamente, CORS estricto, rate limiting en `/auth/*` |
| 9 | Estrategia de testing | [ADR-009](adr/ADR-009-testing.md) | pytest + httpx (backend), Vitest + Testing Library (frontend), E2E fuera de MVP |
| 10 | CI/CD | [ADR-010](adr/ADR-010-cicd.md) | 1 workflow GH Actions con jobs paralelos `backend` / `frontend`, gate de migraciones Alembic |
| 11 | Flujo de invitación a grupo | [ADR-002](adr/ADR-002-permisos.md#invitación) | Alta directa por email (admin agrega usuario ya registrado) — **conservada como alternativa secundaria**; mecanismo primario ahora es código+QR, ver decisión 32 |
| 12 | Moneda y precisión monetaria | [ADR-003](adr/ADR-003-modelo-datos.md#moneda) | Montos en enteros (centavos); **moneda restringida a COP/USD**, ver decisión 33 |
| 13 | Comprobantes de pago (archivo) | [ADR-007](adr/ADR-007-infra-hosting.md#storage) | Fuera del MVP (confirmado por el propio roadmap, sección V2); columna `receipt_url` nullable ya reservada en el schema |
| 14 | Backups de Supabase Free | [ADR-007](adr/ADR-007-infra-hosting.md#backups) | Sin backup gestionado en free tier → `pg_dump` manual vía GH Actions cron semanal a artifact/otro storage |

| 15 | Corrección/anulación de pagos | [ADR-011](adr/ADR-011-decisiones-adicionales.md#1-corrección-anulación-de-pagos) | Sin UPDATE/DELETE; reversión (`voided_at`) + nuevo registro |
| 16 | Verificación de email | [ADR-011](adr/ADR-011-decisiones-adicionales.md#2-verificación-de-email--registro-sin-confirmación) | Ninguna en MVP; riesgo aceptado y documentado |
| 17 | Recuperación de contraseña | [ADR-011](adr/ADR-011-decisiones-adicionales.md#3-recuperación-de-contraseña-olvidé-mi-contraseña) | **Supuesto a validar:** reset manual por admin del grupo, sin email |
| 18 | Zona horaria de vencimientos | [ADR-011](adr/ADR-011-decisiones-adicionales.md#4-zona-horaria-para-cálculo-de-vencimientos) | Fija `America/Bogota` a nivel de conexión DB |
| 19 | `due_day` en meses cortos | [ADR-011](adr/ADR-011-decisiones-adicionales.md#5-due_day-en-meses-cortos-ej-día-31-en-febreroabril) | Clamping al último día del mes |
| 20 | Dashboard multi-moneda | [ADR-011](adr/ADR-011-decisiones-adicionales.md#6-agregación-del-dashboard-con-obligaciones-en-múltiples-monedas) | Desglose por moneda, sin conversión automática |
| 21 | Concurrencia en ediciones | [ADR-011](adr/ADR-011-decisiones-adicionales.md#7-concurrencia-optimista-en-ediciones) | Optimistic locking vía `updated_at` |
| 22 | Owner único que se va del grupo | [ADR-011](adr/ADR-011-decisiones-adicionales.md#8-qué-pasa-si-el-único-owner-abandona-el-grupo-o-pierde-acceso) | Bloqueo de baja hasta transferir ownership |
| 23 | Observabilidad mínima | [ADR-011](adr/ADR-011-decisiones-adicionales.md#9-observabilidad-mínima) | Logging estructurado + `request_id` + healthcheck |

| 24 | Renombre `responsible_membership_id` → `responsible_user_id` | [ADR-013](adr/ADR-013-modelo-datos-v2.md#1-renombrar-responsible_membership_id--responsible_user_id) | El nombre ahora describe lo que la columna realmente almacena |
| 25 | `due_day` + `due_month` para obligaciones anuales | [ADR-013](adr/ADR-013-modelo-datos-v2.md#2-due_day-pasa-a-ser-día-mes-no-solo-día-del-mes) | `due_month` nullable, obligatorio solo si `periodicity = ANNUAL` |
| 26 | Periodicidad ampliada | [ADR-013](adr/ADR-013-modelo-datos-v2.md#3-periodicidad-ampliada) | `MONTHLY, BIMONTHLY, QUARTERLY, SEMIANNUAL, ANNUAL` |
| 27 | Suscripción vs. débito automático | [ADR-013](adr/ADR-013-modelo-datos-v2.md#4-suscripción-vs-obligación-operativa) | Dos booleanos independientes: `is_subscription`, `auto_debit` |
| 28 | Medios de pago de Colombia | [ADR-013](adr/ADR-013-modelo-datos-v2.md#5-medios-de-pago--tipos-reales-de-colombia) | `CASH, BANK_ACCOUNT, DIGITAL_WALLET, DEBIT_CARD, CREDIT_CARD, BRE_B, PSE, OTHER` con `CHECK` de referencia por tipo |
| 29 | Campos enriquecidos de obligación | [ADR-013](adr/ADR-013-modelo-datos-v2.md#6-obligaciones--campos-que-le-faltaban-al-dominio-real) | `provider_name`, `external_reference`, `is_variable_amount`, `is_essential`, `end_date` |
| 30 | Categorías de sistema + personalizadas | [ADR-013](adr/ADR-013-modelo-datos-v2.md#7-categorías--sistema--personalizadas-por-grupo) | `group_id NULL` = sistema (10 precargadas en `seed.sql`), no nulo = del grupo |
| 31 | Arquitectura de alertas de vencimiento/mora | [ADR-012](adr/ADR-012-arquitectura-alertas.md) | Modelo preparado (`notification_rules`/`notification_events`) sin activar envíos; recomendación: WhatsApp Cloud API oficial + cron de GH Actions, 1:1 por miembro (no publica en grupos de WhatsApp) |
| 32 | Invitación a grupo por código alfanumérico + QR | [ADR-014](adr/ADR-014-invitacion-codigo-qr.md) | Código de 8 caracteres (alfabeto sin ambigüedades), QR generado al vuelo sobre el mismo código; resuelve la limitación de ADR-002 (invitado ya debía tener cuenta) |
| 33 | Monedas soportadas | [ADR-015](adr/ADR-015-monedas-soportadas.md) | `currency` restringida a `ENUM('COP','USD')`, sin conversión automática (mantiene ADR-011 #6) |

## No especificado todavía (fuera de esta ronda)

- Diseño detallado de notificaciones (V2, fuera de MVP por decisión ya tomada en el documento fuente).
- Diseño de reportes/presupuestos (V3).
- Cualquier decisión de integración bancaria (V3, fuera de scope).

## Fuera de alcance

- Automatización bancaria / Open Banking / conciliación automática — excluido explícitamente por el documento fuente (sección 9 y 22).
- Microservicios, IA, app móvil nativa — excluido explícitamente (sección 22).
