# ADR-014: Invitación a grupos por código alfanumérico + QR

## Contexto

ADR-002 había resuelto la invitación como "admin agrega por email a un
usuario ya registrado", con la limitación explícita de que la otra persona
debía registrarse primero por su cuenta sin ningún nexo. Se pide ahora un
mecanismo de código alfanumérico + QR — resuelve esa limitación de raíz:
la invitación deja de depender de que el invitado ya tenga cuenta.

## Decisión — Formato del código

**8 caracteres**, alfabeto de 32 símbolos sin ambigüedades visuales
(mayúsculas + dígitos, excluyendo `0/O`, `1/I/L`, similar a Crockford
Base32): `23456789ABCDEFGHJKMNPQRSTVWXYZ`.

- Espacio de combinaci32^8 ≈ 1,1 × 10¹² — descarta fuerza bruta práctica
  incluso sin rate limiting agresivo, pero igual se aplica rate limiting
  (ver Consecuencias).
- Se muestra al usuario agrupado `XXXX-XXXX` (solo visual; se almacena y
  se valida sin el guion).
- Suficientemente corto para transcribirse a mano si el QR falla (cámara
  rota, WhatsApp Web sin cámara, etc.) — el caso real de una familia.

## Decisión — QR

El QR **no es una entidad ni se persiste como imagen**: es una
representación visual de una URL de deep link que contiene el código,
generada **al vuelo** en el momento de la petición:

```
GET /api/v1/groups/{group_id}/invite-codes/{id}/qr
→ PNG/SVG generado en el momento, codificando:
  https://<frontend>/join?code=XXXXXXXX
```

Generación server-side con una librería estándar (`qrcode` en Python) —
sin dependencia de un servicio externo de terceros, cero costo, cero
latencia de red adicional.

## Decisión — Ciclo de vida del código

- `role_to_assign`: rol que recibe quien se una con ese código (`member`
  por defecto; un admin puede generar un código que asigne `admin`
  directamente si confía en quien lo va a usar). **Nunca `owner`** — DB
  constraint lo impide (`CHECK (role_to_assign <> 'owner')`).
- `max_uses`: `NULL` = código familiar reutilizable indefinidamente (el
  caso típico: un código fijo que la familia comparte una vez); un valor
  numérico permite códigos de un solo uso si se prefiere invitar persona
  por persona.
- `expires_at`: opcional; `NULL` = sin expiración.
- `is_active`: revocación manual sin borrar el historial (quién se unió con
  qué código queda intacto en `group_memberships.joined_via_invite_code_id`
  aunque el código se desactive después).
- Un admin/owner puede tener varios códigos activos simultáneamente por
  grupo (ej. uno permanente para la familia + uno temporal de un solo uso
  para un invitado puntual).

## Decisión — Flujo de uso

Dos entradas posibles, mismo código:

1. **Usuario ya registrado, logueado**: `POST /api/v1/groups/join {code}`
   — valida vigencia/usos/rol, crea la membresía, incrementa `uses_count`.
2. **Usuario nuevo**: `POST /api/v1/auth/register` acepta un campo opcional
   `invite_code`; si viene, el registro y el `join` ocurren en la **misma
   transacción** (evita el estado intermedio "me registré pero no sé cómo
   entrar al grupo" que tenía el flujo de ADR-002).

`GET /api/v1/groups/join/preview?code=XXXXXXXX` (sin auth) permite mostrar
"vas a unirte a Familia Pérez" antes de pedir registro/login — mejora de
UX, no expone datos financieros, solo `groups.name`.

## Relación con ADR-002

El flujo de "admin agrega por email a un usuario ya registrado" **no se
elimina**: sigue siendo válido para cuando el admin ya sabe que el invitado
tiene cuenta y prefiere no generar/compartir un código. El código+QR pasa a
ser el mecanismo **primario y recomendado** en la UI; el alta directa por
email queda como alternativa secundaria. `ADR-002` se marca como
actualizado por este documento en lo referente a invitación.

## Consecuencias

- Rate limiting en `POST /groups/join` y en `POST /auth/register` cuando
  trae `invite_code` (mismo mecanismo de ADR-008, RNF-SEG-03) — mitiga
  intentos de adivinar códigos, aunque la entropía ya lo hace poco
  práctico.
- El código es **globalmente único** (no por grupo) para poder resolverlo
  sin conocer de antemano a qué grupo pertenece — simplifica el lookup a
  un único índice.
- Compartir un código reutilizable (`max_uses = NULL`) por un canal
  inseguro (ej. publicado sin cuidado) permite que cualquiera con el
  código se una como `member` — riesgo aceptado y mitigable por el propio
  admin revocando (`is_active = false`) y generando uno nuevo si sospecha
  fuga. Se documenta en `security-checklist.md`.
