# ADR-003: Modelo de datos relacional

> **Actualizado por [ADR-013](ADR-013-modelo-datos-v2.md)**: los campos de
> `Obligation` (proveedor, referencia externa, suscripción, débito
> automático, periodicidad ampliada), `PaymentMethod` (tipos colombianos) y
> `Category` (sistema + personalizada) descritos abajo corresponden a la
> v1. Ver ADR-013 para el modelo vigente; esta ADR se conserva como
> registro histórico de las decisiones de estructura período/pago que
> siguen vigentes sin cambios.

## Contexto

El documento fuente pide historial mensual por obligación recurrente
("Agosto → Pagado, Septiembre → Pendiente...") sin especificar cómo modelar
los períodos. Dos opciones:

1. Generar filas de `Payment` "fantasma" en estado `PENDIENTE` para cada mes futuro.
2. Separar el **concepto de período** (`ObligationPeriod`) del **hecho de pago** (`Payment`): un período puede no tener pago aún.

## Decisión — Períodos vs. Pagos

**Opción 2.** `ObligationPeriod` representa "Internet — Septiembre 2026" con su
`due_date` y `status` derivado (`PENDIENTE`/`PAGADO`/`VENCIDO`); `Payment` es
el registro inmutable de que un pago ocurrió contra un período. Esto evita
mutar/duplicar filas de pago cuando el sistema solo necesita saber "qué falta
por vencer", y dejará espacio limpio para V3 (conciliación automática) sin
tocar el historial ya escrito: la conciliación simplemente crea o vincula un
`Payment` a un `ObligationPeriod` existente.

Generación de períodos: **lazy**, no cron. Al leer el dashboard/listado, el
backend garantiza (upsert idempotente) que existan `ObligationPeriod` desde
`Obligation.start_date` hasta el mes actual + 1. Evita job en background para
el MVP (innecesario con Render Free durmiendo).

## Decisión — Moneda

> **Superseded por [ADR-015](ADR-015-monedas-soportadas.md)**: `currency`
> ya no es texto libre ISO-4217, quedó restringida a un
> `ENUM('COP', 'USD')`. El resto de esta sección (montos en
> enteros/centavos) sigue vigente sin cambios.

Columna `currency` (CHAR(3), ISO-4217, default `'COP'`) en `Obligation` y en
`Payment.amount` se replica la moneda para no depender de un join histórico si
la obligación cambia de moneda en el futuro. **Montos en enteros** (columna
`amount_cents BIGINT`), nunca `FLOAT`/`NUMERIC` con aritmética de punto
flotante en la capa de aplicación — evita el clásico bug de redondeo en
sumas del dashboard.

## Decisión — Responsable

`Obligation.responsible_user_id` (FK compuesta nullable a
`GroupMembership(user_id, group_id)` — nombre corregido en ADR-013, la v1
lo llamaba `responsible_membership_id` pero almacenaba un `user_id`, nombre
que mentía sobre su contenido), único responsable principal, tal como el
documento fuente permite para el MVP. **No** se crea tabla puente
`ObligationResponsible` todavía: agregar multi-responsable después es un
`ALTER TABLE` + tabla nueva, no una reescritura, así que no se paga ese
costo por adelantado (YAGNI).

## Esquema

Ver [`db/schema.sql`](../db/schema.sql) para el DDL completo y
[`db/erd.md`](../db/erd.md) para el diagrama relacional.

## Consecuencias

- El estado `VENCIDO` de un período es **calculado**, no almacenado como
  fuente de verdad: se deriva de `due_date < CURRENT_DATE AND NOT EXISTS
  (Payment que lo cubra)`. Se persiste como columna denormalizada
  (`status`) actualizada en el mismo upsert lazy, para no calcularlo en cada
  lectura del dashboard con window functions costosas — trade-off explícito
  performance-vs-normalización, aceptable al volumen de una familia.
