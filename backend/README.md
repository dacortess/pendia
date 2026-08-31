# Backend — Gestor Familiar de Pagos y Facturas

## Requisitos

- Python 3.10+
- PostgreSQL 16 (para desarrollo local)
- Docker (para PostgreSQL via docker-compose)

## Setup

```bash
# 1. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp ../backend.env.example .env
# Editar .env si es necesario

# 4. Levantar PostgreSQL
cd ..
docker compose up -d postgres
cd backend

# 5. Correr migraciones
alembic upgrade head

# 6. Seed database
python scripts/seed.py

# 7. Correr tests
pytest tests/ -v
```

## Estructura

```
app/
├── database/      # Base y session
├── core/          # Configuración
├── users/         # Modelo User
├── groups/        # Modelo Group
├── categories/    # Modelo Category
├── payment_methods/
├── obligations/
├── payments/
├── audit/
└── notification/
```

## Comandos útiles

```bash
# Crear nueva migración después de modificar modelos
alembic revision --autogenerate -m "Descripción"

# Aplicar migraciones
alembic upgrade head

# Rollback última migración
alembic downgrade -1

# Ver estado de migraciones
alembic current
alembic history
```

## Tests

```bash
# Correr todos los tests
pytest tests/ -v

# Correr con coverage
pytest tests/ --cov=app --cov-report=html
```
