# ADR-013: Correcciones al modelo de datos (v2)

Consolida las correcciones pedidas antes de continuar con las revisiones.
Reemplaza los fragmentos correspondientes de ADR-003. Ver `schema.sql` y
`erd.md` actualizados.

## 1. Renombrar `responsible_membership_id` → `responsible_user_id`

La columna almacenaba un `user_id` pero se llamaba `_membership_id`,
señalado como riesgo en la revisión anterior. Corregido: el nombre ahora
describe exactamente lo que contiene. La FK compuesta hacia
`group_memberships(user_id, group_id)` se mantiene sin cambios de
comportamiento — sigue impidiendo asignar como responsable a alguien que no
pertenece al grupo de la obligación.

## 2. `due_day` pasa a ser día-mes, no solo día del mes

**Problema**: un `SMALLINT 1-31` no alcanza para representar una obligación
**anual** con fecha fija (ej. seguro vehicular que vence cada 15 de marzo).

**Decisión**: se agrega `due_month SMALLINT (1-12)`, nullable, con
`CHECK` cruzado:

```sql
CONSTRAINT chk_due_month_only_if_annual CHECK (
    (periodicity = 'ANNUAL' AND due_month IS NOT NULL)
    OR (periodicity <> 'ANNUAL' AND due_month IS NULL)
)
```

- Para `MONTHLY`/`BIMONTHLY`/`QUARTERLY`/`SEMIANNUAL`: solo `due_day`
  importa (día dentro de cada ciclo); el mes de arranque del ciclo lo fija
  `start_date`.
- Para `ANNUAL`: `due_day` + `due_month` fijan la fecha exacta cada año
  (ej. `due_day=15, due_month=3` → 15 de marzo).
- **Meses cortos**: la regla de clamping de ADR-011 #5 (`min(due_day,
  último_día_del_mes)`) sigue aplicando igual para el mes calculado, ya sea
  mensual o anual.

## 3. Periodicidad ampliada

`periodicity` pasa de `{'MONTHLY'}` a
`{'MONTHLY','BIMONTHLY','QUARTERLY','SEMIANNUAL','ANNUAL'}` — cubre
matrículas semestrales, pólizas anuales, seguros trimestrales, etc.,
sin necesidad de modelarlos como "obligación mensual con meses saltados".

**Nota de implementación para el generador de `ObligationPeriod`** (no es
DDL, es lógica de servicio a construir): el intervalo entre períodos, en
meses, se deriva de la periodicidad: `MONTHLY=1, BIMONTHLY=2, QUARTERLY=3,
SEMIANNUAL=6, ANNUAL=12`. El generador avanza `start_date` en saltos de ese
tamaño.

## 4. Suscripción vs. obligación operativa

Se agregan dos columnas booleanas independientes (no un solo enum, porque
son dos ejes distintos de la misma obligación):

- **`is_subscription`**: es una suscripción digital/medio (Netflix,
  Spotify, revista digital, curso online) — informativo, útil para
  reportes futuros ("cuánto gasta la familia en suscripciones").
- **`auto_debit`**: se cobra automáticamente al medio de pago asociado, sin
  que un miembro tenga que "hacer" el pago manualmente. Una suscripción
  típicamente tiene `auto_debit=true`, pero no es 1:1 — un plan de
  medicina prepagada también puede tener domiciliación automática sin ser
  una "suscripción" en el sentido coloquial. Separar los dos campos evita
  forzar esa equivalencia falsa.

Efecto en UX futura (no en el MVP de historias ya escritas): si
`auto_debit=true`, el recordatorio de una alerta (ADR-012) debería decir
"verifica que se haya cobrado" en vez de "recuerda pagar".

## 5. Medios de pago — tipos reales de Colombia

`payment_method_kind` pasa de `{'BANK_ACCOUNT','CARD'}` a:

```
CASH, BANK_ACCOUNT, DIGITAL_WALLET, DEBIT_CARD, CREDIT_CARD, BRE_B, PSE, OTHER
```

- **`CASH`**: sin `last4` ni `masked_key` — no hay nada que enmascarar.
- **`BANK_ACCOUNT` / `DEBIT_CARD` / `CREDIT_CARD`**: siguen usando `last4`
  (CHAR(4), límite físico de columna como salvaguarda estructural contra
  guardar un número completo por error).
- **`DIGITAL_WALLET`** (Nequi, Daviplata...), **`BRE_B`** (llave: celular,
  correo o documento) y **`PSE`**: usan `masked_key` (TEXT, tope de 20
  caracteres) porque su identificador no es un número de 4 dígitos sino un
  celular/correo/llave que debe mostrarse enmascarado (ej. `***-***-4821`),
  nunca completo.
- **`OTHER`**: sin restricción, para lo que no encaje (ej. cheque,
  consignación en efectivo a tercero).

El `CHECK constraint chk_payment_method_reference` fuerza en la base de
datos que cada `kind` tenga el campo de referencia correcto poblado — no
depende de que el service lo recuerde validar.

## 6. Obligaciones — campos que le faltaban al dominio real

Se agregan:

| Campo | Propósito |
|---|---|
| `provider_name` | Entidad a quien se le paga ("Claro", "Colsanitas", "Banco X") — distinto de `category_id`, que es la clasificación del gasto. |
| `external_reference` | N° de cuenta/contrato/matrícula/póliza — lo que la familia necesita a mano para pagar o reclamar. |
| `is_variable_amount` | `true` en servicios que fluctúan cada ciclo (agua, luz, gas) — `expected_amount_cents` pasa a ser una referencia/estimado, no el monto exacto esperado, cuando este flag es `true`. |
| `is_essential` | Prioridad familiar — insumo para reportes/alertas futuras (ej. "no puedes cancelar esto sin plan B"), no afecta lógica del MVP actual. |
| `end_date` | Vigencia con plazo fijo (crédito a 24 meses, arriendo a término fijo). `NULL` = indefinida. El generador de períodos no crea `ObligationPeriod` más allá de `end_date`. |

## 7. Categorías — sistema + personalizadas por grupo

**Problema original**: solo existía `Category` por grupo, sin catálogo base
ni forma de compartir categorías comunes entre grupos.

**Decisión**:

- `categories.group_id` nullable: `NULL` = categoría del **sistema**
  (precargada una sola vez vía `seed.sql`: Servicios del hogar,
  Suscripciones, Salud, Educación, Seguros, Transporte, Créditos y deudas,
  Alimentación, Entretenimiento, Otros); no `NULL` = categoría
  **personalizada** creada por ese grupo.
- Columna generada `is_system` (`GENERATED ALWAYS AS (group_id IS NULL)
  STORED`) — evita que el service tenga que recordar la convención en cada
  query; se filtra/muestra directo.
- `obligations.category_id` sigue siendo nullable — una obligación puede no
  tener categoría — y editable vía `PATCH` (ya cubierto por HU-15).
- **Invariante no expresable como FK simple, enforced en el service**: si
  `category.group_id` no es `NULL`, debe ser igual al `group_id` de la
  obligación que la usa (un grupo no puede usar la categoría personalizada
  de otro grupo). Se documenta aquí como contrato de `obligations/service.py`
  y debe tener su propio test de autorización cruzada (mismo patrón que
  RNF-SEG-04).
- Un grupo puede crear categorías propias sin colisionar con el catálogo
  del sistema: la unicidad de nombre está separada por índice parcial
  (`uq_category_name_per_group` vs. `uq_system_category_name`), así que
  nada impide que un grupo cree "Salud" propia además de la de sistema si
  quisiera personalizarla — aunque la UI debería sugerir usar la del
  sistema primero para no duplicar sin necesidad.

## Actualización al mapa

Estos 7 puntos se agregan a `00-MAPA-DECISIONES.md` como decisiones 24-30.
