# ADR-010: CI/CD

## Decisión

Un solo workflow `ci.yml`, jobs paralelos con paths-filter para no correr
backend en cambios solo de frontend y viceversa:

```
jobs:
  backend:
    if: cambios en backend/**
    steps: ruff (lint) → mypy (types) → pytest (con servicio postgres) → docker build
  frontend:
    if: cambios en frontend/**
    steps: eslint → tsc --noEmit → vitest → next build (output: export)
  migrations-check:
    if: cambios en backend/alembic/**
    steps: alembic upgrade head contra postgres efímero, falla si no aplica limpio
```

- Merge a `main` protegido: requiere los 3 jobs relevantes en verde (branch protection rule, configuración manual en GitHub, no en YAML).
- Deploy: Cloudflare Pages se dispara solo mismo por su integración Git nativa al hacer push a `main` (no requiere step de deploy en Actions). Render se configura con auto-deploy en push a `main` sobre `backend/**` igualmente nativo de la plataforma.
- Job adicional, cron semanal, independiente del pipeline de código: `backup.yml` (`pg_dump` → artifact/R2, ver ADR-007).

## Consecuencias

- Sin step de deploy propio en Actions: menos secretos que gestionar (no se
  necesita token de Cloudflare/Render en GH Actions para el MVP), a costa de
  perder control fino sobre el orden deploy-frontend-vs-backend — aceptable
  porque el contrato de API es versionado (ADR-004) y ambos lados toleran
  despliegues asíncronos mientras no se rompa compatibilidad hacia atrás
  dentro de `/api/v1`.
