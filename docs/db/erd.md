# ERD — Pendia (v3)

```
User ──< GroupMembership >── Group ──< GroupInviteCode
  │              │                │           │
  │  (responsible_user_id)        │           └── consumida por GroupMembership.joined_via_invite_code_id
  │              │                ├──< Category (group_id NULL = sistema, o del grupo)
  │              │                ├──< PaymentMethod
  │              │                └──< Obligation ──> Category
  │              │                        │        └──> PaymentMethod
  │              │                        │           currency: COP | USD
  │              │                        └──< ObligationPeriod ──< Payment (currency: COP | USD)
  │              │                                     │
  │              │                                     └──< NotificationEvent >── NotificationRule
  │              └───────────────────────────────────────────────────────────────────┘
  │
  └── phone_number, whatsapp_opt_in (destino de alertas, ADR-012)

AuditLog ──> User (actor), referencia genérica (entity_type, entity_id)
```

## Entidades

- **User**: cuenta global; `phone_number`/`whatsapp_opt_in` para alertas futuras.
- **Group**: la "familia".
- **GroupInviteCode** *(v3, ADR-014)*: código alfanumérico de 8 caracteres
  para unirse a un grupo, opcionalmente con expiración y/o límite de usos.
  El QR es solo una representación visual de una URL que contiene este
  código — no es una entidad ni se persiste como imagen.
- **GroupMembership**: puente `User`↔`Group` con `role`; registra si el
  ingreso fue vía código (`joined_via_invite_code_id`) o alta directa por
  un admin.
- **Category**: sistema (`group_id NULL`, 10 precargadas) o personalizada
  por grupo.
- **PaymentMethod**: efectivo, cuenta bancaria, billetera digital, débito,
  crédito, Bre-B, PSE.
- **Obligation**: v3 restringe `currency` a `COP`/`USD` (antes libre);
  conserva proveedor, referencia externa, suscripción, débito automático,
  esencialidad, vigencia y periodicidad ampliada (v2).
- **ObligationPeriod**: instancia por ciclo, `status` calculado.
- **Payment**: registro inmutable (anulable), `currency` también
  restringida a `COP`/`USD`.
- **NotificationRule** / **NotificationEvent**: terreno preparado para
  alertas (ADR-012), sin envíos activos en el MVP.
- **AuditLog**: trazabilidad genérica.

Ver DDL completo en [`schema.sql`](schema.sql) y datos iniciales en
[`seed.sql`](seed.sql).
