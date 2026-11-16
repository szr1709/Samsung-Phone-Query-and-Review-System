from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    func
)

from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Phone(Base):
    __tablename__ = "phones"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(150), nullable=False, unique=True)
    brand = Column(String(50), nullable=False, default="Samsung")
    release_date = Column(Date)
    source_url = Column(Text)
    image_url = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())

    specifications = relationship(
        "PhoneSpecification",
        back_populates="phone",
        cascade="all, delete-orphan"
    )

    prices = relationship(
        "PhonePrice",
        back_populates="phone",
        cascade="all, delete-orphan"
    )


class PhoneSpecification(Base):
    __tablename__ = "phone_specifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    phone_id = Column(
        BigInteger,
        ForeignKey("phones.id", ondelete="CASCADE"),
        nullable=False
    )

    category = Column(String(100), nullable=False)
    specification_name = Column(String(150), nullable=False)
    specification_value = Column(Text)

    phone = relationship(
        "Phone",
        back_populates="specifications"
    )

    __table_args__ = (
        UniqueConstraint(
            "phone_id",
            "category",
            "specification_name"
        ),
    )


class PhonePrice(Base):
    __tablename__ = "phone_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    phone_id = Column(
        BigInteger,
        ForeignKey("phones.id", ondelete="CASCADE"),
        nullable=False
    )

    price = Column(Numeric(12, 2))
    currency = Column(String(10), nullable=False, default="USD")
    source = Column(String(255))
    checked_at = Column(DateTime, server_default=func.now())

    phone = relationship(
        "Phone",
        back_populates="prices"
    )
