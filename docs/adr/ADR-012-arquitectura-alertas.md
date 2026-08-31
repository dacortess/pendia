# ADR-012: Arquitectura de alertas de vencimiento/mora (preparación)

## Contexto

Se pide dejar el terreno listo para que, a futuro, el sistema dispare
alertas de "vence pronto" / "está vencido" consumibles por un bot de
WhatsApp que avise a todo el grupo familiar. No se activa envío alguno en
el MVP — esto es preparación de modelo + decisión de arquitectura, sin
construir el bot todavía.

## Restricción real de WhatsApp que condiciona todo lo demás

La API oficial de Meta (WhatsApp Cloud API) **no puede publicar mensajes
dentro de un grupo de WhatsApp** — solo puede enviar mensajes 1:1 a números
de teléfono individuales que hayan interactuado con la cuenta de negocio o
acepten una plantilla aprobada. "Avisar a todo el grupo" en la práctica
significa: **el sistema le envía el mismo mensaje a cada miembro que dio su
número y opt-in**, no que postea en un chat de grupo de WhatsApp compartido.

La alternativa que sí publicaría en un grupo real de WhatsApp son librerías
no oficiales (`whatsapp-web.js`, Baileys) que automatizan una cuenta
personal agregada al grupo familiar. Se descartan para este proyecto:
violan los términos de servicio de WhatsApp (riesgo de bloqueo del número),
y requieren mantener una sesión de navegador/socket persistente — no
encaja en Render Free (procesos duermen, no hay estado persistente
garantizado) sin pagar por un always-on.

**Decisión**: asumir la limitación 1:1 como parte del diseño, no pelear
contra ella. Se comunica al usuario final como "cada miembro que active
alertas de WhatsApp recibe su propio aviso", no "el bot escribe en el grupo".

## Arquitectura recomendada ($0)

```
GitHub Actions (cron diario, gratis)
        │
        ▼
POST /api/v1/internal/notifications/dispatch   (FastAPI, mismo backend)
        │  auth: header estático INTERNAL_API_KEY (no es JWT de usuario)
        ▼
1. Genera notification_events pendientes (idempotente por UNIQUE constraint)
2. Por cada evento PENDING: junta obligation_period + obligation + grupo
   + miembros con whatsapp_opt_in=true y phone_number no nulo
3. Llama a Meta WhatsApp Cloud API (free tier) por cada destinatario
4. Marca el evento SENT o FAILED con el detalle del error
```

- **Proveedor**: Meta WhatsApp Cloud API (oficial). Free tier vigente al
  momento de este análisis: conversaciones iniciadas por el negocio dentro
  de plantillas aprobadas tienen una franja gratuita mensual generosa para
  el volumen de una familia (decenas de mensajes/mes). **Verificar límites
  vigentes al momento de implementar** — las condiciones de free tier de
  Meta cambian; no asumir el número exacto de este documento como
  permanente.
- **No se levanta un servicio de bot separado**: el "bot" es simplemente
  código dentro del backend FastAPI que llama a la Graph API de Meta. Evita
  un tercer servicio, un tercer deploy, y una tercera factura potencial.
- **Disparador**: GitHub Actions `schedule: cron` (gratis, ya se usa para
  el backup semanal en `ADR-010`) golpea el endpoint interno una vez al día.
  Alternativa descartada: cron nativo de Render — no existe en el plan
  Free (requiere Background Worker de pago).
- **Autenticación del endpoint interno**: header `X-Internal-Key` verificado
  contra `INTERNAL_API_KEY` (env var / GitHub secret), **no** JWT de
  usuario — es tráfico servicio-a-servicio, no de una persona logueada.
  Este endpoint no debe exponerse en la documentación pública de la API
  (excluir de `/docs` en producción, ver `RNF` de seguridad).

## Por qué el modelo ya está listo sin activar nada

- `notification_rules` permite reglas por grupo o por obligación específica
  sin cambiar schema cuando se activen (ej. "avisar 5 días antes para el
  arriendo, 1 día para Netflix").
- `notification_events` es la cola/log: idempotente, auditable, y es
  exactamente lo que un bot (propio o de terceros) necesita **leer** —
  agnóstico a si termina siendo el propio backend quien llama a Meta o un
  servicio externo que hace `GET /internal/notifications/pending` y luego
  `PATCH /internal/notifications/{id}` para reportar el resultado. La
  decisión de *quién* llama a WhatsApp puede cambiar sin migrar de nuevo.
- `users.phone_number` + `whatsapp_opt_in` ya existen — activar alertas en
  V2 no requiere pedirle el teléfono a nadie de nuevo si se captura en el
  registro/perfil desde el MVP (aunque el campo quede sin uso funcional
  hasta entonces).

## Consecuencias

- Ningún envío ocurre en el MVP: `notification_rules`/`notification_events`
  quedan vacías hasta que se implemente el endpoint `dispatch` en V2.
- Cuando se active, el volumen esperado (una familia, unas pocas decenas de
  obligaciones) está muy por debajo de cualquier límite de free tier
  razonable — el riesgo de costo es prácticamente nulo.
- Si a futuro se requiere *sí* publicar en un grupo real de WhatsApp (no
  1:1), es un cambio de proveedor (a una librería no oficial o a un
  servicio de pago tipo Twilio con número dedicado), no un cambio de
  schema: `notification_events.channel` ya es un enum extensible.
