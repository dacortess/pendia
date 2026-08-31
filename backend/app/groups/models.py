"""Group and membership models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, BigInt

membership_role_enum = PG_ENUM(
    "owner", "admin", "member",
    name="membership_role",
    create_type=False,
)


class Group(Base):
    """Family group."""
    __tablename__ = "groups"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )
    
    def __repr__(self) -> str:
        return f"<Group(id={self.id}, name={self.name})>"


class GroupInviteCode(Base):
    """Invitation code to join a group (ADR-014)."""
    __tablename__ = "group_invite_codes"
    
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role_to_assign: Mapped[str] = mapped_column(
        membership_role_enum,
        nullable=False,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    max_uses: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        nullable=True,
    )
    uses_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    
    __table_args__ = (
        CheckConstraint(
            "role_to_assign <> 'owner'",
            name="chk_invite_code_not_owner",
        ),
        CheckConstraint(
            "max_uses IS NULL OR uses_count <= max_uses",
            name="chk_uses_within_max",
        ),
        Index(
            "idx_group_invite_codes_lookup",
            "code",
            postgresql_where=("is_active"),
        ),
    )
    
    def __repr__(self) -> str:
        return f"<GroupInviteCode(id={self.id}, code={self.code})>"


class GroupMembership(Base):
    """Membership between user and group."""
    __tablename__ = "group_memberships"
    
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(membership_role_enum, nullable=False)
    joined_via_invite_code_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("group_invite_codes.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )
    
    __table_args__ = (
        Index(
            "uq_one_owner_per_group",
            "group_id",
            unique=True,
            postgresql_where=("role = 'owner'"),
        ),
    )
    
    def __repr__(self) -> str:
        return f"<GroupMembership(user_id={self.user_id}, group_id={self.group_id}, role={self.role})>"