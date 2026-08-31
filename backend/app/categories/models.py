"""Category models (system and custom)."""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigInt


class Category(Base):
    """Category for organizing obligations (system or group-specific)."""
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    group_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    
    __table_args__ = (
        Index(
            "uq_category_name_per_group",
            "group_id",
            "name",
            unique=True,
            postgresql_where="group_id IS NOT NULL",
        ),
        Index(
            "uq_system_category_name",
            "name",
            unique=True,
            postgresql_where="group_id IS NULL",
        ),
    )
    
    @property
    def is_system(self) -> bool:
        """Check if this is a system category."""
        return self.group_id is None