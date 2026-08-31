# Historias de usuario — Gestor Familiar de Pagos y Facturas (MVP)

Formato: `Como <rol>, quiero <acción>, para <beneficio>`, con criterios de
aceptación en Gherkin resumido. Rol referido según `GroupMembership.role`
(ADR-002) salvo que se indique "cualquier usuario autenticado".

Cada historia referencia el endpoint que la implementa (ADR-004) para
trazabilidad directa hacia el backlog de tickets.

---

## Épica 1 — Cuenta y autenticación

### HU-01 — Registro de cuenta
Como visitante, quiero crear una cuenta con email y contraseña, para poder
acceder al sistema.
- Dado un email no registrado y una contraseña válida, cuando envío el
  formulario, entonces se crea el usuario y quedo autenticado.
- Dado un email ya registrado, cuando intento registrarme, entonces recibo
  `409` con `code: EMAIL_ALREADY_EXISTS`.
- Dado una contraseña que no cumple la política (RNF-SEG-02), entonces el
  formulario rechaza el envío antes de llamar a la API.
- *Endpoint*: `POST /auth/register`.

### HU-02 — Inicio de sesión
Como usuario registrado, quiero iniciar sesión con email y contraseña, para
acceder a mis grupos.
- Dado credenciales correctas, entonces recibo access token + cookie de
  refresh y soy redirigido al dashboard.
- Dado credenciales incorrectas, entonces recibo `401` genérico (sin
  revelar si el email existe).
- Dado 10 intentos fallidos en 1 minuto desde la misma IP, entonces recibo
  `429` (RNF-SEG-03).
- *Endpoint*: `POST /auth/login`.

### HU-03 — Renovación de sesión transparente
Como usuario con sesión activa, quiero que mi sesión se renueve sola
mientras uso la app, para no tener que loguearme cada 15 minutos.
- Dado un access token expirado y un refresh token válido, cuando hago una
  request, entonces el cliente refresca automáticamente y reintenta sin que
  yo lo note.
- Dado un refresh token expirado o revocado, entonces soy redirigido a login.
- *Endpoint*: `POST /auth/refresh`.

### HU-04 — Cierre de sesión
Como usuario autenticado, quiero cerrar sesión, para que nadie más use mi
cuenta desde este dispositivo.
- Dado que cierro sesión, entonces el refresh token queda revocado en el
  servidor y el access token se descarta del cliente.
- *Endpoint*: `POST /auth/logout`.

### HU-05 — Restablecimiento de contraseña por un admin
*(Supuesto ADR-011 #3 — validar con la familia)*
Como admin u owner de un grupo, quiero generar una contraseña temporal para
un miembro que la olvidó, para que pueda volver a entrar.
- Dado que soy admin/owner del grupo del usuario, cuando genero el reset,
  entonces se crea una contraseña temporal y se invalidan todos sus refresh
  tokens activos.
- Dado que no soy admin/owner de ningún grupo en común con ese usuario,
  entonces recibo `403`.
- *Endpoint*: `PATCH /groups/{group_id}/members/{user_id}/reset-password`.

---

## Épica 2 — Grupos y miembros

### HU-06 — Crear grupo familiar
Como usuario autenticado, quiero crear un grupo, para empezar a registrar
las obligaciones de mi familia.
- Dado que envío un nombre de grupo, entonces se crea el grupo y quedo como
  `owner`.
- *Endpoint*: `POST /groups`.

### HU-07 — Agregar miembro al grupo por email (alternativa secundaria)
*(Ver HU-07b/HU-07c para el mecanismo primario — código + QR, ADR-014)*
Como admin u owner, quiero agregar a otro usuario ya registrado a mi grupo
por su email, para cuando ya sé que tiene cuenta y prefiero no compartir un
código.
- Dado un email de un usuario existente, cuando lo agrego, entonces queda
  como `member` por defecto en el grupo.
- Dado un email sin cuenta registrada, entonces recibo `404` con mensaje
  claro de que debe registrarse primero.
- Dado que ya es miembro del grupo, entonces recibo `409`.
- *Endpoint*: `POST /groups/{group_id}/members`.

### HU-07b — Generar código de invitación (con QR)
Como admin u owner, quiero generar un código alfanumérico para invitar
gente a mi grupo, para que se unan sin que yo tenga que saber de antemano
si ya tienen cuenta.
- Dado que genero un código, entonces recibo un código de 8 caracteres
  (formato `XXXX-XXXX`) y puedo pedir su QR.
- Dado que elijo `max_uses = null`, entonces el código es reutilizable
  indefinidamente hasta que lo revoque.
- Dado que elijo `role_to_assign = owner`, entonces la API rechaza la
  solicitud (`422`) — un código nunca otorga ownership (ADR-014).
- *Endpoints*: `POST /groups/{group_id}/invite-codes`,
  `GET /groups/{group_id}/invite-codes/{id}/qr`.

### HU-07c — Unirse a un grupo con un código o QR
Como visitante o usuario autenticado, quiero escanear un QR o ingresar un
código, para unirme al grupo familiar sin que un admin tenga que agregarme
manualmente.
- Dado que soy visitante sin cuenta y uso un código válido, cuando me
  registro con `invite_code`, entonces quedo creado y unido al grupo en la
  misma operación.
- Dado que ya tengo cuenta y estoy logueado, cuando envío el código a
  `POST /groups/join`, entonces quedo unido con el rol que el código
  define.
- Dado un código expirado, revocado o que ya alcanzó `max_uses`, entonces
  recibo `410` con mensaje claro.
- Dado que quiero ver a qué grupo me uniría antes de registrarme, entonces
  `GET /groups/join/preview?code=` me muestra solo el nombre del grupo.
- *Endpoints*: `POST /auth/register` (con `invite_code`),
  `POST /groups/join`, `GET /groups/join/preview`.

### HU-08 — Cambiar el rol de un miembro
Como admin u owner, quiero cambiar el rol de un miembro, para darle o
quitarle permisos de gestión.
- Dado que soy admin y el objetivo es el owner, entonces recibo `403` (un
  admin no puede degradar al owner).
- Dado que asigno `owner` a otro miembro siendo yo el owner actual, entonces
  yo quedo automáticamente como `admin` (invariante de un solo owner,
  ADR-011 #8).
- *Endpoint*: `PATCH /groups/{group_id}/members/{user_id}`.

### HU-09 — Quitar un miembro del grupo
Como admin u owner, quiero quitar a alguien del grupo, para revocarle
acceso a la información financiera familiar.
- Dado que el objetivo es el único `owner`, entonces recibo `409` (debe
  transferir ownership antes, ADR-011 #8).
- *Endpoint*: `DELETE /groups/{group_id}/members/{user_id}`.

### HU-10 — Ver mis grupos
Como usuario autenticado, quiero ver la lista de grupos a los que
pertenezco, para elegir cuál gestionar.
- *Endpoint*: `GET /groups`.

---

## Épica 3 — Catálogos (categorías y medios de pago)

### HU-11 — Crear categoría
Como admin u owner, quiero crear categorías (Servicios, Arriendo,
Suscripciones...), para clasificar las obligaciones.
- Dado un nombre duplicado dentro del mismo grupo, entonces recibo `409`.
- *Endpoint*: `POST /groups/{group_id}/categories`.

### HU-12 — Registrar medio de pago
Como admin u owner, quiero registrar una cuenta o tarjeta con solo sus
últimos 4 dígitos y titular, para asociarla a obligaciones sin exponer
datos sensibles.
- Dado que intento enviar un número completo de tarjeta o un CVV, entonces
  la API rechaza el campo (no existe en el schema — RNF-SEG-01).
- *Endpoint*: `POST /groups/{group_id}/payment-methods`.

### HU-13 — Desactivar un medio de pago
Como admin u owner, quiero desactivar un medio de pago que ya no se usa,
para que no aparezca al crear nuevas obligaciones sin perder el historial
de las que ya lo usaron.
- *Endpoint*: `PATCH /groups/{group_id}/payment-methods/{id}`.

---

## Épica 4 — Obligaciones

### HU-14 — Crear obligación recurrente
Como admin u owner, quiero registrar una obligación con su valor esperado,
moneda, periodicidad, día de vencimiento, responsable y medio de pago, para
que el sistema empiece a generarle períodos.
- Dado `due_day = 31` y el mes actual es febrero, entonces el período de
  ese mes vence el último día de febrero (ADR-011 #5).
- Dado que no asigno responsable, entonces la obligación queda sin
  responsable (permitido, ADR-003).
- Dado que elijo `currency = USD` (ej. una suscripción facturada en
  dólares), entonces el valor esperado y los pagos futuros de esa
  obligación quedan en USD; el selector solo ofrece `COP`/`USD` (ADR-015).
- Dado que elijo `periodicity = ANNUAL`, entonces debo indicar también
  `due_month` (ej. seguro que vence cada 15 de marzo); si no lo hago,
  recibo `422`.
- *Endpoint*: `POST /groups/{group_id}/obligations`.

### HU-15 — Editar obligación
Como admin u owner, quiero editar el valor, responsable o medio de pago de
una obligación, para reflejar cambios (ej. subió el arriendo).
- Dado que otro admin la modificó después de que yo cargué el formulario,
  entonces recibo `409` por conflicto de versión (ADR-011 #7) y debo
  recargar antes de reintentar.
- *Endpoint*: `PATCH /groups/{group_id}/obligations/{id}`.

### HU-16 — Desactivar obligación
Como admin u owner, quiero desactivar una obligación que ya no aplica (ej.
cancelé Netflix), para que deje de generar períodos futuros sin borrar su
historial.
- Dado que la desactivo, entonces no se generan nuevos `ObligationPeriod`
  después del mes en curso, pero los períodos pasados y sus pagos
  permanecen visibles en el historial.
- *Endpoint*: `DELETE /groups/{group_id}/obligations/{id}` (soft).

### HU-17 — Listar obligaciones del grupo
Como cualquier miembro, quiero ver todas las obligaciones activas del
grupo, para saber qué se paga cada mes.
- *Endpoint*: `GET /groups/{group_id}/obligations`.

---

## Épica 5 — Pagos

### HU-18 — Registrar pago de un período
Como cualquier miembro (si soy el responsable) o admin/owner (sobre
cualquier obligación), quiero registrar que pagué una obligación de un mes
específico, para que quede reflejado como pagado.
- Dado que soy `member` y no soy el responsable asignado de esa obligación,
  entonces recibo `403` (ADR-002).
- Dado que el período ya tiene un pago activo (no anulado), entonces recibo
  `409` — debo anular el anterior primero (ADR-011 #1).
- Dado que registro el pago, entonces el período pasa a `PAGADO` y queda
  una entrada en `AuditLog`.
- *Endpoint*: `POST /groups/{group_id}/periods/{id}/payments`.

### HU-19 — Anular un pago mal registrado
Como admin u owner, quiero anular un pago registrado por error, para
poder corregirlo sin perder trazabilidad de qué pasó.
- Dado que anulo un pago, entonces el período vuelve a `PENDIENTE` o
  `VENCIDO` según su fecha de vencimiento, y el pago original queda
  marcado `voided_at` (nunca se borra).
- *Endpoint*: `POST /groups/{group_id}/payments/{id}/void`.

### HU-20 — Ver historial de pagos
Como cualquier miembro, quiero ver el historial de pagos del grupo con
quién los registró y cuándo, para tener trazabilidad familiar.
- *Endpoint*: `GET /groups/{group_id}/payments`.

---

## Épica 6 — Dashboard y consultas

### HU-21 — Ver dashboard del mes actual
Como cualquier miembro, quiero ver un resumen del mes con total de
obligaciones, total pagado, total pendiente y cuántas vencen esta semana,
para tener una vista rápida del estado financiero familiar.
- Dado que el grupo tiene obligaciones en `COP` y `USD` a la vez, entonces
  el resumen muestra un desglose por moneda (máximo 2 bloques), sin
  convertir (ADR-011 #6, ADR-015).
- Dado que hoy es una fecha dentro de la semana de vencimiento de una
  obligación (calculado en `America/Bogota`, ADR-011 #4), entonces esa
  obligación aparece en "vencen esta semana".
- *Endpoint*: `GET /groups/{group_id}/dashboard?month=`.

### HU-22 — Consultar próximos vencimientos, pendientes y vencidos
Como cualquier miembro, quiero filtrar los períodos por estado
(`PENDIENTE`/`PAGADO`/`VENCIDO`) y por mes, para enfocarme en lo que falta
por pagar.
- *Endpoint*: `GET /groups/{group_id}/periods?status=&month=`.

---

## Épica 7 — Plataforma (no visible al usuario final, pero requerida para el MVP operativo)

### HU-23 — Entorno reproducible con Docker
Como desarrollador, quiero levantar todo el stack con un solo comando, para
poder desarrollar y probar sin configurar servicios manualmente.
- Dado `docker compose up`, entonces frontend, backend y Postgres quedan
  disponibles y conectados entre sí.

### HU-24 — Pipeline de CI en cada Pull Request
Como desarrollador, quiero que lint, tipos, tests y build corran
automáticamente en cada PR, para no mergear código roto.
- Dado un PR que modifica `backend/**`, entonces corre el job `backend`
  (lint, mypy, migraciones, tests, build de imagen).
- Dado un PR que modifica `frontend/**`, entonces corre el job `frontend`.

### HU-25 — Respaldo semanal de la base de datos
Como owner del sistema (rol técnico, no de negocio), quiero que la base de
datos se respalde automáticamente cada semana, para no perder el historial
financiero familiar ante un fallo de Supabase.
- Dado que pasa el cron semanal, entonces se genera un `pg_dump` y queda
  disponible como artifact descargable por 90 días.

---

## Fuera de esta ronda de historias (ya excluido del MVP en el mapa de decisiones)

Notificaciones, comprobantes adjuntos, reportes/presupuestos, integración
bancaria — no tienen historia de usuario aquí porque están fuera del
alcance del MVP (ver `00-MAPA-DECISIONES.md`).
