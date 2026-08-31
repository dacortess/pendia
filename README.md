# Pendia

Aplicación web para gestionar obligaciones de pago (servicios, suscripciones, cuotas) de un grupo familiar: quién debe pagar qué, cuándo vence, con qué medio de pago, y un historial de lo ya pagado.

> Proyecto de portafolio. Backend y frontend completos y funcionando; ver [Licencia](#licencia) — código propietario, repo público solo como referencia.

## Qué resuelve

Una familia comparte gastos recurrentes (arriendo, servicios públicos, streaming, seguros) entre varias personas y varios medios de pago. Pendia centraliza eso:

- **Grupos con roles**: cada usuario puede pertenecer a varios grupos familiares, con rol `owner`, `admin` o `member` en cada uno. Los datos financieros están aislados por grupo.
- **Invitación por código + QR**: sumar a alguien a un grupo no requiere que ya tenga cuenta creada de antemano.
- **Obligaciones recurrentes**: se definen una vez (nombre, monto esperado, periodicidad — mensual, bimestral, trimestral, semestral, anual — día de vencimiento, categoría, medio de pago, responsable) y el sistema genera automáticamente los períodos de pago correspondientes.
- **Registro y anulación de pagos**: cualquier período pendiente se puede marcar como pagado (con su propia moneda, bloqueada a la de la obligación) y revertir si fue un error.
- **Categorías y medios de pago**: categorías del sistema + personalizadas por grupo, medios de pago con los tipos usados en Colombia (efectivo, cuenta bancaria, tarjeta débito/crédito, Nequi/Daviplata, Bre-B, PSE, otro).
- **Auditoría**: acciones sensibles (reseteo de contraseña, cambios de rol, transferencia de ownership) quedan registradas.

## Stack

| | |
|---|---|
| **Backend** | Python 3.10+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL 16, Argon2id (hash de contraseñas), PyJWT |
| **Frontend** | Next.js 14 (App Router, export estático), React 18, TypeScript, Tailwind CSS |
| **Testing** | pytest (257 tests, backend) · Vitest + Testing Library + MSW (118 tests, frontend) |
| **Infra local** | Docker Compose (PostgreSQL) |

## Arquitectura

Monorepo con dos aplicaciones independientes que solo se comunican por HTTP:

```
family-project/
├── backend/    → API REST (FastAPI), toda la lógica de negocio y persistencia
├── frontend/   → SPA estática (Next.js export), consume la API vía fetch
└── docs/adr/   → decisiones de arquitectura documentadas (15 ADR)
```

- **Auth cross-origin sin sesión de servidor**: access token JWT de vida corta (15 min, en memoria del cliente, nunca en `localStorage`) + refresh token opaco de larga duración en cookie `httpOnly`, con rotación en cada uso. Pensado para que frontend y backend vivan en dominios distintos (Cloudflare Pages / Render) sin depender de cookies same-site.
- **Autorización por membresía**: el rol (`owner` / `admin` / `member`) vive en la relación usuario-grupo, no en el usuario — la misma persona puede ser admin en un grupo y member en otro. Todo query de negocio filtra por grupo.
- **Frontend sin servidor propio**: `output: 'export'` de Next.js — build 100% estático, toda la lógica vive en la API. El frontend nunca hace SSR ni tiene acceso directo a la base de datos.
- **Base de datos**: PostgreSQL con migraciones versionadas en Alembic; ningún cambio de esquema se aplica a mano.

El razonamiento detrás de cada una de estas decisiones (y las alternativas descartadas) está en [`docs/adr/`](docs/adr/).

## Cómo correrlo localmente

Requisitos: Docker, Python 3.10+, Node.js 20+.

**1. Base de datos**

```bash
docker compose up -d postgres
```

**2. Backend**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp ../backend.env.example .env   # ajustar JWT_SECRET si es necesario

alembic upgrade head
python scripts/seed.py           # categorías del sistema, opcional

uvicorn app.main:app --reload --port 8000
```

La API queda en `http://localhost:8000/api/v1`, docs interactivas en `http://localhost:8000/docs`.

**3. Frontend**

```bash
cd frontend
cp ../frontend.env.example .env  # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm install
npm run dev
```

La app queda en `http://localhost:3000`.

**4. Tests**

```bash
# Backend (requiere Postgres arriba)
cd backend && pytest tests/ -v

# Frontend
cd frontend && npm test
```

## Licencia

Código propietario — todos los derechos reservados. Este repositorio es público solo como referencia/portafolio; no se otorga ningún permiso de uso, copia, modificación ni distribución. Ver [`LICENSE`](LICENSE).
