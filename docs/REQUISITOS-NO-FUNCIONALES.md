# Requisitos no funcionales — Pendia

Cada RNF referencia el ADR que lo sustenta cuando aplica, y es verificable
(no aspiracional) — se puede escribir un test o un check de CI contra él.

## 1. Seguridad

| ID | Requisito | Verificación |
|---|---|---|
| RNF-SEG-01 | Ningún campo del sistema almacena PAN completo, CVV, PIN ni credenciales bancarias. | Grep de patrones prohibidos sobre `schema.sql` y modelos en CI (gate opcional, ADR-008). |
| RNF-SEG-02 | Contraseñas: mínimo 10 caracteres, sin máximo artificial bajo (permitir passphrases largas). Hasheadas con Argon2id, nunca en texto plano en logs. | Test unitario de `core/security.py`; revisión de que ningún `logger.info` incluya `password`. |
| RNF-SEG-03 | Rate limiting: máx. 10 intentos/min/IP en `/auth/login`, `/auth/register`, `/auth/refresh`. | Test de integración que dispara 11 requests y espera `429` en la última. |
| RNF-SEG-04 | Todo endpoint de negocio exige JWT válido y verifica pertenencia al grupo del recurso solicitado antes de ejecutar la operación. | Test de autorización cruzada por endpoint (ADR-009). |
| RNF-SEG-05 | Tráfico exclusivamente sobre HTTPS en producción; sin fallback a HTTP. | Verificación manual post-deploy + configuración de la plataforma (Cloudflare/Render). |
| RNF-SEG-06 | Secretos (`JWT_SECRET`, `DATABASE_URL` de producción) nunca en el repositorio ni en logs. | `git-secrets`/`gitleaks` como step opcional de CI; revisión de `.gitignore`. |
| RNF-SEG-07 | CORS restringido al origen exacto del frontend desplegado. | Test de integración que verifica el header `Access-Control-Allow-Origin` con un origen no autorizado y espera que no se refleje. |
| RNF-SEG-08 | Rate limiting también en `POST /groups/join` y en `POST /auth/register` cuando trae `invite_code`, mismo umbral que `/auth/login` (ADR-014). | Test de integración análogo a RNF-SEG-03 sobre `/groups/join`. |
| RNF-SEG-09 | Un código de invitación nunca puede asignar el rol `owner` (enforced por `CHECK` de base de datos, no solo por validación de API). | Test de integración: intentar crear un código con `role_to_assign=owner` espera `422`; test directo contra la constraint de DB en la suite de modelos. |

## 2. Rendimiento

| ID | Requisito | Verificación |
|---|---|---|
| RNF-PERF-01 | El endpoint de dashboard responde en menos de 500 ms (p95) con hasta 200 obligaciones y 5 años de historial de pagos por grupo (volumen esperado x50 el uso real de una familia). | Test de carga simple (`locust`/`k6`) contra un seed de datos representativo, corrido manualmente antes de cada release mayor. |
| RNF-PERF-02 | Las consultas de agregación del dashboard se resuelven en SQL (una query por bloque de métricas), nunca trayendo todas las filas a Python para sumarlas. | Revisión de código en el `code-review` del ADR-005; `EXPLAIN ANALYZE` documentado en el PR que introduce el endpoint. |
| RNF-PERF-03 | Cold start de Render Free (tras sleep por inactividad) es un escenario conocido y comunicado al usuario (loading state explícito ≥ 3s antes de mostrar error), no tratado como bug. | Prueba manual: dejar el backend dormir, medir tiempo de primera respuesta, verificar que el frontend muestre feedback y no un error genérico. |

## 3. Disponibilidad y resiliencia

| ID | Requisito | Verificación |
|---|---|---|
| RNF-DISP-01 | El sistema no promete SLA de alta disponibilidad (uso familiar, hosting free tier); se documenta explícitamente que Render Free puede dormir tras ~15 min de inactividad. | Nota visible en `README.md` de operación, no oculta al usuario final. |
| RNF-DISP-02 | Backup semanal automatizado con retención de 90 días, restaurable en un entorno local en menos de 15 minutos. | Ejercicio de restauración documentado en `security-checklist.md`, ejecutado al menos una vez antes de uso real continuo. |
| RNF-DISP-03 | El frontend maneja caídas del backend con un mensaje de error claro (no pantalla en blanco ni stack trace crudo). | Test de componente con `api-client.ts` mockeado para devolver error de red. |

## 4. Integridad y consistencia de datos

| ID | Requisito | Verificación |
|---|---|---|
| RNF-DATA-01 | Ningún pago se pierde o sobrescribe silenciosamente: toda corrección es una anulación + nuevo registro, nunca un `UPDATE` destructivo (ADR-011 #1). | Constraint a nivel de código: no exponer `PATCH`/`DELETE` sobre `payments` en el router. |
| RNF-DATA-02 | Los montos se almacenan y operan siempre como enteros (centavos), nunca `float`, en toda la cadena backend↔DB↔frontend. | Revisión de tipos en `schemas.py` (Pydantic) y en TypeScript (`amount_cents: number` documentado como entero, no decimal). |
| RNF-DATA-03 | Las ediciones concurrentes sobre la misma obligación no se pisan silenciosamente (ADR-011 #7). | Test de integración que simula dos `PATCH` con el mismo `expected_updated_at` y espera `409` en el segundo. |
| RNF-DATA-04 | Toda mutación relevante queda en `AuditLog` con actor, acción, entidad y timestamp. | Test que verifica una fila de `AuditLog` tras cada operación mutante crítica (crear/editar/anular pago, cambios de membresía). |
| RNF-DATA-05 | Ninguna obligación o pago puede persistirse con una moneda fuera de `{COP, USD}` — rechazado tanto en el borde de la API (Pydantic) como en la base de datos (`ENUM`). | Test de integración que envía `currency: "EUR"` y espera `422`; test de modelo que intenta el `INSERT` directo y espera error de tipo de Postgres. |
| RNF-DATA-06 | Un código de invitación no puede usarse más allá de `max_uses` ni después de `expires_at`, incluso bajo solicitudes concurrentes (dos personas usando el mismo código de un solo uso al mismo tiempo). | Test de integración con dos requests concurrentes contra un código `max_uses=1`; solo una debe tener éxito (`chk_uses_within_max` + `SELECT ... FOR UPDATE` o transacción serializable en el service). |

## 5. Usabilidad y accesibilidad

| ID | Requisito | Verificación |
|---|---|---|
| RNF-UX-01 | La aplicación es usable en español, con formato de moneda y fecha locales (COP, `dd/mm/yyyy`). | Revisión manual de copys y formateo (`Intl.NumberFormat('es-CO', ...)`). |
| RNF-UX-02 | Diseño responsive: usable en móvil (la familia probablemente consulte desde el celular), mínimo hasta 360px de ancho. | Revisión manual en DevTools + breakpoints de Tailwind. |
| RNF-UX-03 | Contraste de color y tamaño de texto cumplen WCAG 2.1 AA en las pantallas principales (dashboard, formularios). | Auditoría con Lighthouse/axe antes del primer release. |

## 6. Mantenibilidad y operabilidad

| ID | Requisito | Verificación |
|---|---|---|
| RNF-MANT-01 | Cobertura de tests: 100% de los `service` de reglas de negocio críticas (cálculo de `period_status`, invariante de un solo owner, enforcement de pertenencia a grupo) y de autorización por endpoint (ADR-009). | Reporte de cobertura en CI (`pytest --cov`), gate mínimo configurable (ej. 80% global, 100% en módulos listados). |
| RNF-MANT-02 | Logging estructurado (JSON) con `request_id` correlacionable end-to-end (ADR-011 #9). | Revisión manual de logs en un request de prueba; verificar que el `request_id` aparece en logs de aplicación y en `AuditLog.metadata`. |
| RNF-MANT-03 | `GET /api/v1/health` responde sin autenticación y sin tocar la base de datos, para distinguir "backend dormido" de "backend caído". | Test de integración simple. |
| RNF-MANT-04 | El código sigue una capa estricta router→service→repository→models (ADR-005); no hay SQL directo en routers ni lógica de negocio en modelos. | Enforced en `code-review` (checklist explícito), revisable por linters de arquitectura si se agregan luego (ej. `import-linter`). |
| RNF-MANT-05 | Migraciones de base de datos son reversibles o, si no lo son, están documentadas como tales en el mensaje de la migración. | Revisión manual de cada migración de Alembic antes de merge. |

## 7. Portabilidad y costo

| ID | Requisito | Verificación |
|---|---|---|
| RNF-COST-01 | El sistema opera a costo $0 mientras se mantenga dentro de los límites de las capas free de Cloudflare Pages, Render y Supabase (o Neon). | Revisión trimestral de los límites vigentes de cada proveedor (documentado, no automatizable). |
| RNF-COST-02 | Ningún componente acopla el código a un proveedor específico más allá de una variable de entorno (`DATABASE_URL` estándar, sin SDK propietario de Supabase en el backend). | Revisión de código: solo se usa el driver Postgres estándar (`psycopg`), no el SDK JS/REST de Supabase. |

## 8. Cumplimiento y privacidad (aplicado a nivel familiar, sin marco regulatorio formal)

| ID | Requisito | Verificación |
|---|---|---|
| RNF-PRIV-01 | Los datos de un grupo nunca son visibles, ni siquiera parcialmente, para usuarios que no pertenecen a ese grupo. | Suite de tests de aislamiento entre grupos (RNF-SEG-04, mismo mecanismo). |
| RNF-PRIV-02 | El usuario puede solicitar la eliminación de su cuenta; al eliminarla, sus datos personales (`email`, `full_name`) se anonimizan pero el `AuditLog`/historial financiero del grupo permanece íntegro para los demás miembros. | Historia de usuario y endpoint fuera del MVP inicial — queda como ticket explícito de V2 si se requiere antes de uso real prolongado. |

---

**Nota de alcance**: estos RNF cubren el MVP definido en `00-MAPA-DECISIONES.md`.
RNF de escalabilidad multi-tenant a gran escala, alta disponibilidad con
SLA formal, o cumplimiento regulatorio (habeas data / GDPR formal) quedan
fuera de alcance mientras el producto sea de uso familiar cerrado.
