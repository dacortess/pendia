# ADR-002: Modelo de permisos, aislamiento por grupo e invitación

> **Actualizado por [ADR-014](ADR-014-invitacion-codigo-qr.md)**: el
> mecanismo primario de invitación pasó a ser código alfanumérico + QR,
> resolviendo la limitación de "el invitado debe registrarse antes" que
> tenía el flujo descrito abajo. El alta directa por email que sigue
> descrita aquí se conserva como alternativa secundaria, no se elimina.

## Contexto

Roles definidos por el documento fuente: `owner`, `admin`, `member`, uno o
varios grupos por usuario. Todo dato financiero debe aislarse por grupo.

## Decisión — Modelo de permisos

RBAC **plano por membresía**, sin permisos granulares por recurso en el MVP:

- El rol vive en `GroupMembership.role`, no en `User` (un usuario puede ser `admin` en un grupo y `member` en otro).
- Matriz de capacidades:

| Acción | owner | admin | member |
|---|---|---|---|
| Editar/eliminar el grupo | ✅ | ❌ | ❌ |
| Agregar/quitar miembros | ✅ | ✅ | ❌ |
| Cambiar rol de otro miembro | ✅ | ✅ (no puede tocar al owner) | ❌ |
| CRUD de obligaciones/categorías/medios de pago | ✅ | ✅ | ❌ |
| Registrar pago | ✅ | ✅ | ✅ (solo si es responsable de la obligación) |
| Ver dashboard/historial | ✅ | ✅ | ✅ |

- **Aislamiento**: toda query de negocio filtra por `group_id` derivado del JWT + la membresía activa (nunca del `group_id` que venga en el path/body sin verificar pertenencia). Dependencia FastAPI `get_current_membership(group_id: int)` valida pertenencia y retorna el rol antes de llegar al handler — punto único de enforcement, no repetido por endpoint.
- `owner` es único por grupo (el creador); no hay transferencia de ownership en MVP.

## Decisión — Invitación a grupo

**Supuesto a validar con la familia (no bloqueante para arrancar el desarrollo, sí antes de exponer el flujo a usuarios reales):**

MVP: el `admin`/`owner` agrega un usuario **ya registrado** por email exacto.
Si no existe cuenta con ese email, la API responde `404` con mensaje
"el usuario debe registrarse primero". **No hay envío de correos de
invitación** en el MVP (evita depender de un proveedor SMTP/transaccional,
mantiene el objetivo de $0 y reduce superficie de configuración).

Alternativa descartada por ahora: invitación por link con token de un solo
uso enviado por email — se deja como ticket de V2 si la familia necesita
agregar personas que aún no tienen cuenta antes de que ellas se registren.

## Consecuencias

- El registro de usuario es un paso previo obligatorio a ser agregado a un grupo; el onboarding debe comunicarlo claramente en la UI ("pídele a tu familiar que se registre con este correo").
- Sin esta limitación, el modelo de datos y el enforcement de permisos quedan más simples y auditable en una sola capa.
