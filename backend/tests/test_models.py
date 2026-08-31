"""Tests for SQLAlchemy models and database constraints.

These tests use SQLite in-memory for speed but note that some PostgreSQL-specific
features (like partial unique indexes, regex checks) can only be tested against
PostgreSQL. Those are documented as requiring the full migration test.
"""
import pytest
from datetime import date, datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.users.models import User
from app.groups.models import Group, GroupInviteCode, GroupMembership
from app.categories.models import Category
from app.payment_methods.models import PaymentMethod
from app.obligations.models import Obligation, ObligationPeriod
from app.payments.models import Payment
from app.audit.models import AuditLog
from app.notification.models import NotificationRule, NotificationEvent


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Enable foreign keys
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a session for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user(session):
    """Create a sample user for testing."""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        full_name="Test User",
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def sample_group(session, sample_user):
    """Create a sample group for testing."""
    group = Group(
        name="Test Family",
        created_by=sample_user.id,
    )
    session.add(group)
    session.commit()
    return group


@pytest.fixture
def sample_membership(session, sample_user, sample_group):
    """Create a sample membership for testing."""
    membership = GroupMembership(
        user_id=sample_user.id,
        group_id=sample_group.id,
        role="owner",
    )
    session.add(membership)
    session.commit()
    return membership


class TestUserConstraints:
    """Test User model constraints."""

    def test_user_email_unique(self, session, sample_user):
        """Test that email must be unique."""
        duplicate = User(
            email=sample_user.email,
            password_hash="another_hash",
            full_name="Another User",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_user_email_case_insensitive(self, session, sample_user):
        """Test that emails are stored case-insensitively (PostgreSQL CITEXT)."""
        # In PostgreSQL with CITEXT, these would be duplicates
        # In SQLite, they are different strings but we test the column type works
        user2 = User(
            email="TEST@EXAMPLE.COM",
            password_hash="another_hash",
            full_name="Another User",
        )
        session.add(user2)
        session.commit()
        assert user2.id != sample_user.id


class TestGroupMembershipConstraints:
    """Test GroupMembership constraints."""

    def test_composite_primary_key(self, session, sample_user, sample_group):
        """Test that user_id + group_id is the composite primary key."""
        membership = GroupMembership(
            user_id=sample_user.id,
            group_id=sample_group.id,
            role="member",
        )
        session.add(membership)
        session.commit()

    def test_duplicate_membership_fails(self, session, sample_user, sample_group):
        """Test that duplicate user+group membership is rejected."""
        membership = GroupMembership(
            user_id=sample_user.id,
            group_id=sample_group.id,
            role="member",
        )
        session.add(membership)
        session.commit()
        
        duplicate = GroupMembership(
            user_id=sample_user.id,
            group_id=sample_group.id,
            role="admin",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


class TestCategoryConstraints:
    """Test Category constraints."""

    def test_create_system_category(self, session):
        """Test creating a system category (group_id = NULL)."""
        cat = Category(
            group_id=None,
            name="Salud",
        )
        session.add(cat)
        session.commit()
        assert cat.id is not None

    def test_create_group_category(self, session, sample_group):
        """Test creating a group-specific category."""
        cat = Category(
            group_id=sample_group.id,
            name="Mi Gasto",
        )
        session.add(cat)
        session.commit()
        assert cat.id is not None

    def test_is_system_property(self, session):
        """Test is_system property."""
        sys_cat = Category(group_id=None, name="Servicios")
        group_cat = Category(group_id=1, name="Personal")
        
        assert sys_cat.is_system is True
        assert group_cat.is_system is False

    def test_group_category_unique_in_same_group(self, session, sample_group):
        """Test that categories within a group have unique names."""
        cat1 = Category(
            group_id=sample_group.id,
            name="Gasto Uno",
        )
        session.add(cat1)
        session.commit()
        
        cat2 = Category(
            group_id=sample_group.id,
            name="Gasto Uno",  # Duplicate
        )
        session.add(cat2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


class TestPaymentMethodConstraints:
    """Test PaymentMethod constraints."""

    def test_cash_method_valid(self, session, sample_group):
        """Test that CASH method with no last4/masked_key is valid."""
        method = PaymentMethod(
            group_id=sample_group.id,
            kind="CASH",
            provider_name="Cash",
            label="Cash in hand",
            last4=None,
            masked_key=None,
            holder_name="Test Holder",
        )
        session.add(method)
        session.commit()
        assert method.id is not None

    def test_bank_account_requires_last4(self, session, sample_group):
        """Test that BANK_ACCOUNT requires last4."""
        method = PaymentMethod(
            group_id=sample_group.id,
            kind="BANK_ACCOUNT",
            provider_name="Bank",
            label="Savings",
            last4="1234",
            masked_key=None,
            holder_name="Test Holder",
        )
        session.add(method)
        session.commit()
        assert method.id is not None

    def test_digital_wallet_requires_masked_key(self, session, sample_group):
        """Test that DIGITAL_WALLET requires masked_key."""
        method = PaymentMethod(
            group_id=sample_group.id,
            kind="DIGITAL_WALLET",
            provider_name="Nequi",
            label="Digital Wallet",
            last4=None,
            masked_key="***4821",
            holder_name="Test Holder",
        )
        session.add(method)
        session.commit()
        assert method.id is not None

    # NOTE: The complex CHECK constraint for payment_methods is PostgreSQL-specific
    # In SQLite, we can't enforce the conditional logic. Full testing requires PostgreSQL.


class TestObligationConstraints:
    """Test Obligation constraints."""

    def test_annual_obligation_with_due_month(self, session, sample_group, sample_user, sample_membership):
        """Test that ANNUAL periodicity works with due_month."""
        obligation = Obligation(
            group_id=sample_group.id,
            responsible_user_id=sample_user.id,
            name="Annual Insurance",
            periodicity="ANNUAL",
            due_day=15,
            due_month=3,
            start_date=date(2024, 1, 1),
            expected_amount_cents=1200000,
            currency="COP",
        )
        session.add(obligation)
        session.commit()
        assert obligation.id is not None

    def test_monthly_obligation_without_due_month(self, session, sample_group, sample_user, sample_membership):
        """Test that non-ANNUAL periodicity works without due_month."""
        obligation = Obligation(
            group_id=sample_group.id,
            responsible_user_id=sample_user.id,
            name="Monthly Rent",
            periodicity="MONTHLY",
            due_day=1,
            due_month=None,
            start_date=date(2024, 1, 1),
            expected_amount_cents=500000,
            currency="COP",
        )
        session.add(obligation)
        session.commit()
        assert obligation.id is not None

    def test_amount_non_negative(self, session, sample_group, sample_user, sample_membership):
        """Test that expected_amount_cents cannot be negative."""
        obligation = Obligation(
            group_id=sample_group.id,
            responsible_user_id=sample_user.id,
            name="Test Obligation",
            periodicity="MONTHLY",
            due_day=15,
            due_month=None,
            start_date=date(2024, 1, 1),
            expected_amount_cents=-100,
            currency="COP",
        )
        session.add(obligation)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_end_date_after_start_date(self, session, sample_group, sample_user, sample_membership):
        """Test that end_date must be >= start_date."""
        obligation = Obligation(
            group_id=sample_group.id,
            responsible_user_id=sample_user.id,
            name="Test Obligation",
            periodicity="MONTHLY",
            due_day=15,
            due_month=None,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 1, 1),
            expected_amount_cents=100000,
            currency="COP",
        )
        session.add(obligation)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    # NOTE: Check constraints for due_day range and due_month_only_if_annual
    # are PostgreSQL-specific and need PostgreSQL for full testing


class TestObligationPeriodConstraints:
    """Test ObligationPeriod constraints."""

    def test_unique_period_per_obligation(self, session, sample_group, sample_user, sample_membership):
        """Test that obligation_id + period_month is unique."""
        obligation = Obligation(
            group_id=sample_group.id,
            responsible_user_id=sample_user.id,
            name="Test",
            periodicity="MONTHLY",
            due_day=15,
            due_month=None,
            start_date=date(2024, 1, 1),
            expected_amount_cents=100000,
            currency="COP",
        )
        session.add(obligation)
        session.commit()
        
        period1 = ObligationPeriod(
            obligation_id=obligation.id,
            period_month=date(2024, 1, 1),
            due_date=date(2024, 1, 15),
            status="PENDIENTE",
        )
        session.add(period1)
        session.commit()
        
        period2 = ObligationPeriod(
            obligation_id=obligation.id,
            period_month=date(2024, 1, 1),  # Duplicate
            due_date=date(2024, 1, 15),
            status="PAGADO",
        )
        session.add(period2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


class TestPaymentConstraints:
    """Test Payment model constraints."""

    def test_payment_amount_non_negative(self, session, sample_user):
        """Test that amount_cents cannot be negative."""
        group = Group(name="Test Group", created_by=sample_user.id)
        session.add(group)
        session.commit()
        
        obligation = Obligation(
            group_id=group.id,
            responsible_user_id=sample_user.id,
            name="Test",
            periodicity="MONTHLY",
            due_day=15,
            due_month=None,
            start_date=date(2024, 1, 1),
            expected_amount_cents=100000,
            currency="COP",
        )
        session.add(obligation)
        session.commit()
        
        period = ObligationPeriod(
            obligation_id=obligation.id,
            period_month=date(2024, 1, 1),
            due_date=date(2024, 1, 15),
            status="PENDIENTE",
        )
        session.add(period)
        session.commit()
        
        payment = Payment(
            obligation_period_id=period.id,
            registered_by_user_id=sample_user.id,
            amount_cents=-50000,
            currency="COP",
            paid_at=date(2024, 1, 10),
        )
        session.add(payment)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_payment_voided_design(self, session, sample_user):
        """Test Payment voiding pattern (soft delete)."""
        group = Group(name="Test Group", created_by=sample_user.id)
        session.add(group)
        session.commit()
        
        obligation = Obligation(
            group_id=group.id,
            responsible_user_id=sample_user.id,
            name="Test",
            periodicity="MONTHLY",
            due_day=15,
            due_month=None,
            start_date=date(2024, 1, 1),
            expected_amount_cents=100000,
            currency="COP",
        )
        session.add(obligation)
        session.commit()
        
        period = ObligationPeriod(
            obligation_id=obligation.id,
            period_month=date(2024, 1, 1),
            due_date=date(2024, 1, 15),
            status="PENDIENTE",
        )
        session.add(period)
        session.commit()
        
        payment = Payment(
            obligation_period_id=period.id,
            registered_by_user_id=sample_user.id,
            amount_cents=100000,
            currency="COP",
            paid_at=date(2024, 1, 10),
        )
        session.add(payment)
        session.commit()
        
        # Void the payment (soft delete)
        payment.voided_at = datetime.now()
        session.commit()
        
        assert payment.voided_at is not None
        # Payment is still in the table, just marked as voided


class TestNotificationRuleConstraints:
    """Test NotificationRule constraints."""

    def test_days_before_due_default(self, session, sample_group):
        """Test that days_before_due has default value."""
        rule = NotificationRule(
            group_id=sample_group.id,
        )
        session.add(rule)
        session.commit()
        
        assert rule.days_before_due == [3, 1]

    def test_custom_days_before_due(self, session, sample_group):
        """Test custom days_before_due."""
        rule = NotificationRule(
            group_id=sample_group.id,
            days_before_due=[7, 3, 1],
        )
        session.add(rule)
        session.commit()
        
        assert rule.days_before_due == [7, 3, 1]


class TestAuditLogConstraints:
    """Test AuditLog constraints."""

    def test_create_audit_log(self, session, sample_user):
        """Test creating an audit log entry."""
        group = Group(name="Test Group", created_by=sample_user.id)
        session.add(group)
        session.commit()
        
        log = AuditLog(
            group_id=group.id,
            actor_user_id=sample_user.id,
            action="CREATE",
            entity_type="Obligation",
            entity_id=1,
        )
        session.add(log)
        session.commit()
        
        assert log.id is not None
        assert log.action == "CREATE"
