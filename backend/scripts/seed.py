"""Script to seed the database with system categories.

Usage:
    python scripts/seed.py
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.categories.models import Category
from app.core.config import settings


SYSTEM_CATEGORIES = [
    ("Servicios del hogar", "home"),
    ("Suscripciones", "tv"),
    ("Salud", "heart"),
    ("Educación", "book"),
    ("Seguros", "shield"),
    ("Transporte", "car"),
    ("Créditos y deudas", "credit-card"),
    ("Alimentación", "shopping-cart"),
    ("Entretenimiento", "film"),
    ("Otros", "more-horizontal"),
]


def seed_system_categories():
    """Insert system categories (idempotent)."""
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        for name, icon in SYSTEM_CATEGORIES:
            existing = session.query(Category).filter_by(
                group_id=None,
                name=name,
            ).first()
            
            if existing:
                print(f"  ✓ {name} (already exists)")
                continue
            
            category = Category(
                group_id=None,
                name=name,
                icon=icon,
            )
            session.add(category)
            print(f"  + {name}")
        
        session.commit()
        print(f"\nSeeded {len(SYSTEM_CATEGORIES)} system categories successfully")
    except Exception as e:
        session.rollback()
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    print("Seeding system categories...")
    seed_system_categories()
