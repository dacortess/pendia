# ADR-007: Infraestructura, hosting, storage y backups

## Decisión — Hosting

Confirma y detalla lo ya decidido en el documento fuente:

- **Frontend**: Cloudflare Pages, build estático (ADR-006), deploy en cada push a `main` vía integración Git nativa de Cloudflare (no necesita job propio en GH Actions más allá de que el build pase).
- **Backend**: Render Free (Web Service, Docker). Cold start aceptado como trade-off conocido.
- **DB**: Supabase Postgres Free como principal. Neon como alternativa si Supabase cambia condiciones de su free tier antes del deploy definitivo — la capa de acceso (SQLAlchemy + `DATABASE_URL` estándar) no acopla a ninguno de los dos, así que el switch es solo una env var.

## Storage (comprobantes) {#storage}

Fuera del MVP (confirmado, ver mapa de decisiones). Cuando se aborde en V2:
candidato natural es Supabase Storage (mismo proveedor que la DB, free tier
incluido), evitando integrar un tercer proveedor (S3) solo para esto.

## Backups {#backups}

Supabase Free no incluye point-in-time recovery ni backups automáticos
gestionados. Decisión: **job semanal en GH Actions** (`schedule: cron`) que
ejecuta `pg_dump` contra la `DATABASE_URL` y sube el artefacto comprimido a
un bucket gratuito (ej. GitHub Releases del propio repo, privado, o
Cloudflare R2 free tier si se prefiere fuera del repo). Se documenta en
`ADR-010` como job separado del pipeline de CI de código.

**Advertencia explícita**: hasta que ese job exista, la única copia de los
datos es la instancia de Supabase Free — no tratar la DB como respaldada
hasta implementar el punto 12 del roadmap (backups) antes de poner la app en
uso real y continuo por la familia.

## Consecuencias

- Ningún componente de infraestructura exige tarjeta de crédito para
  arrancar, cumpliendo el objetivo de $0.
- El día que se migre a un tier pago (objetivo futuro del documento fuente),
  el único cambio estructural es reemplazar Render por un servicio sin sleep
  y activar backups gestionados de Supabase — no hay refactor de código.
