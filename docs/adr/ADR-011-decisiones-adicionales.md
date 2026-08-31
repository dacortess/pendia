# ADR-011: Decisiones no cubiertas en la primera pasada

Aplicando el chequeo de "fog of war" (huecos que el mapa original dejó sin
ticket porque no eran visibles hasta modelar historias de usuario y flujos
completos). Cada punto se resuelve aquí mismo cuando es una decisión técnica
pura; se marca **supuesto a validar** cuando depende de negocio.

## 1. Corrección/anulación de pagos

El ADR-003 declaró `Payment` inmutable, pero no definió qué pasa si alguien
registra un pago con el monto o la fecha equivocada.

**Decisión**: no hay `UPDATE` ni `DELETE` sobre `payments`. Corrección =
**reversión + nuevo registro**: `POST /api/v1/groups/{group_id}/payments/{id}/void`
crea una fila de auditoría (`payment.voided`) y marca `payments.voided_at`
(columna nueva, nullable). El período vuelve a `PENDIENTE`/`VENCIDO` según
la fecha, y el usuario registra el pago correcto de nuevo. Mantiene el
historial íntegro para auditoría familiar ("¿por qué esto cambió?").

→ Actualizar `schema.sql`: agregar `voided_at TIMESTAMPTZ` a `payments`.

## 2. Verificación de email / registro sin confirmación

No se decidió si el registro exige confirmar el correo. Dado que el ADR-002
ya evita infraestructura de email en el MVP, mantener esa restricción aquí
también.

**Decisión**: sin verificación de email en el MVP. Riesgo aceptado y
documentado: cualquiera puede registrar una cuenta con un email que no le
pertenece (no hay impacto de negocio real en una app familiar de uso
cerrado, pero **si se expone públicamente el registro, revisar antes**).
Mitigación mínima: mensaje en el registro dejando claro que no hay
verificación todavía.

## 3. Recuperación de contraseña ("olvidé mi contraseña")

Ausente del análisis original — es una historia de usuario obligatoria que
el brief no mencionó explícitamente pero que todo sistema con login
requiere.

**Decisión (supuesto a validar)**: dado que no hay proveedor de email en el
MVP (ADR-002), el reset de contraseña en V1 lo ejecuta el `owner` u otro
`admin` del grupo desde `PATCH /api/v1/groups/{group_id}/members/{user_id}/reset-password`,
generando una contraseña temporal que se le comunica al usuario fuera de
banda (verbalmente, WhatsApp, etc. — es una familia). **Riesgo explícito**:
si el `owner` es quien olvida su contraseña y es el único admin, no hay
self-service — requiere intervención manual (ver punto 8). Si esto no es
aceptable para la familia, la alternativa es incorporar un proveedor SMTP
transaccional gratuito (Resend free tier: 3000 emails/mes) únicamente para
`password-reset`, sin construir todo un sistema de notificaciones.

## 4. Zona horaria para cálculo de vencimientos

`due_date < CURRENT_DATE` (ADR-003) es ambiguo sin timezone fija — Postgres
usa la del servidor, que en Supabase/Render no está garantizada como la de
Colombia.

**Decisión**: fijar `TimeZone = 'America/Bogota'` a nivel de sesión de
conexión (parámetro en el `DATABASE_URL` o `SET timezone` en el engine de
SQLAlchemy). Todas las comparaciones de vencimiento usan esa zona,
independiente de dónde corra el servidor físico.

## 5. `due_day` en meses cortos (ej. día 31 en febrero/abril)

No definido cómo generar `ObligationPeriod.due_date` cuando `due_day` no
existe en el mes.

**Decisión**: clamping al último día del mes (`min(due_day, último_día_del_mes)`),
igual que hacen la mayoría de sistemas de facturación recurrente
(Stripe Billing, por ejemplo). Documentar la regla en el docstring de la
función generadora de períodos.

## 6. Agregación del dashboard con obligaciones en múltiples monedas

El ADR-003 permite `currency` por obligación; el ADR-004 define un endpoint
de dashboard con totales, pero no qué pasa si el grupo tiene obligaciones en
COP y USD a la vez.

**Decisión**: el dashboard **no convierte** monedas (evita depender de una
API de tasas de cambio, fuera de alcance del MVP). Si un grupo tiene más de
una moneda activa, el endpoint retorna un desglose por moneda
(`totals: [{currency: "COP", total_cents, paid_cents, pending_cents}, ...]`)
en vez de un único total. El frontend renderiza una sección por moneda si
aplica — para el 99% de los casos (una familia, una moneda) es un array de
un solo elemento y no se nota la complejidad.

## 7. Concurrencia optimista en ediciones

Dos `admin` editando la misma obligación simultáneamente no estaba cubierto.

**Decisión**: columna `updated_at` ya existe en `obligations`; el `PATCH`
exige un header `If-Unmodified-Since` (o campo `expected_updated_at` en el
body) y responde `409 Conflict` si no coincide. Evita el clásico
"pisamos el cambio del otro" sin necesitar locks pesimistas.

## 8. Qué pasa si el único `owner` abandona el grupo o pierde acceso

No definido. **Decisión**: `DELETE /members/{user_id}` sobre el `owner`
está bloqueado por la API (`409`) mientras sea el único con ese rol; debe
transferir ownership primero (`PATCH .../members/{user_id}` con
`role: owner` sobre otro miembro, lo que degrada automáticamente al owner
anterior a `admin` en la misma transacción — invariante de "un solo owner"
del `schema.sql` se mantiene).

## 9. Observabilidad mínima

Ausente del set de ADR original.

**Decisión**: logging estructurado (JSON) vía `structlog` en el backend,
un `request_id` por request (middleware) propagado a cada log line y al
`AuditLog` para correlacionar. Sin APM/tracing en el MVP (Sentry free tier
queda como candidato de V2 si la tasa de errores en producción lo justifica).
Healthcheck simple `GET /api/v1/health` sin auth, usado para verificar que
Render no está dormido antes de reintentar operaciones críticas desde el
frontend.

## Actualización al mapa

Estos 9 puntos se agregan a `00-MAPA-DECISIONES.md` como decisiones 15-23.
Los puntos 2 y 3 quedan explícitamente como **supuestos a validar con la
familia** antes de considerar el sistema listo para uso continuo.
