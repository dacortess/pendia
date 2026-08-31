# ADR-015: Monedas soportadas — COP y USD

## Contexto

ADR-003 había dejado `currency CHAR(3)` como texto libre "ISO-4217,
default COP" sin restringir valores — cualquier código de 3 letras pasaba
la validación de columna. Se pide ahora selección explícita entre COP y
USD (familias con gastos dolarizados: suscripciones internacionales,
Netflix/Spotify facturados en USD, remesas, etc., son el caso real que
motiva esto).

## Decisión

`CHAR(3)` reemplazado por `ENUM supported_currency ('COP', 'USD')` en
`obligations.currency` y `payments.currency`. La UI presenta un selector de
2 opciones (no un dropdown de 150 países) al crear/editar una obligación.

- **Sin conversión automática**: se mantiene la decisión de ADR-011 #6 —
  el dashboard no convierte USD↔COP (evita depender de una API de tasas de
  cambio). El endpoint de dashboard sigue devolviendo un desglose por
  moneda (`totals: [{currency: "COP", ...}, {currency: "USD", ...}]`),
  ahora acotado a máximo 2 entradas en vez de N.
- **`payments.currency` se sigue copiando desde la obligación al momento
  del pago** (no se deriva por join), preservando el historial si en el
  futuro se ampliara el catálogo de monedas.

## Por qué ENUM y no un catálogo en tabla aparte

Con solo 2 valores y sin necesidad de metadata adicional (símbolo, decimales
— ambas monedas usan 2 decimales, ya cubierto por el manejo en centavos), una
tabla `currencies` sería sobre-ingeniería. Si en el futuro se necesita un
tercer valor, `ALTER TYPE supported_currency ADD VALUE 'EUR'` es una
migración trivial de una línea — el costo de "no usar tabla" es bajo y
reversible.

## Consecuencias

- Cualquier intento de insertar una moneda fuera de `{COP, USD}` falla en
  la base de datos, no solo en la validación de Pydantic — segunda capa de
  defensa.
- Los schemas de Pydantic (`obligations/schemas.py`) deben usar un
  `Literal["COP", "USD"]` o `enum.Enum` espejo del tipo de Postgres, para
  que el error de validación ocurra en el borde de la API con un mensaje
  claro, antes de llegar a la base de datos.
