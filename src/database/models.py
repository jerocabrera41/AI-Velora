import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.database.database import Base


# --- Enums ---


class BookingStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ResolutionType(str, enum.Enum):
    AUTOMATED = "automated"
    HUMAN_HANDOFF = "human_handoff"


class Platform(str, enum.Enum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# --- Models ---


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amenities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    policies: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    faq: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=True)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="hotel")
    room_types: Mapped[list["RoomType"]] = relationship(back_populates="hotel")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="hotel")

    def __repr__(self) -> str:
        return f"<Hotel {self.name}>"


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price_per_night: Mapped[float] = mapped_column(Float, nullable=False)
    max_guests: Mapped[int] = mapped_column(Integer, nullable=False)
    total_rooms: Mapped[int] = mapped_column(Integer, nullable=False)

    hotel: Mapped["Hotel"] = relationship(back_populates="room_types")

    def __repr__(self) -> str:
        return f"<RoomType {self.name} - ${self.price_per_night}/noche>"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    confirmation_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id"), nullable=False
    )
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(255), nullable=True)
    checkin_date: Mapped[str] = mapped_column(String(10), nullable=False)
    checkout_date: Mapped[str] = mapped_column(String(10), nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)
    num_guests: Mapped[int] = mapped_column(Integer, default=1)
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.CONFIRMED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    hotel: Mapped["Hotel"] = relationship(back_populates="bookings")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="booking"
    )

    def __repr__(self) -> str:
        return f"<Booking {self.confirmation_number} - {self.guest_name}>"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id"), nullable=False
    )
    guest_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bookings.id"), nullable=True
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform), default=Platform.TELEGRAM
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus), default=ConversationStatus.ACTIVE
    )
    resolution_type: Mapped[ResolutionType | None] = mapped_column(
        Enum(ResolutionType), nullable=True
    )

    hotel: Mapped["Hotel"] = relationship(back_populates="conversations")
    booking: Mapped["Booking | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} - {self.guest_phone}>"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message {self.role} - {self.content[:30]}>"


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id"), nullable=False
    )
    request_type: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<ServiceRequest {self.request_type} - {self.status}>"


class UpsellOffer(Base):
    __tablename__ = "upsell_offers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    offer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    hotel: Mapped["Hotel"] = relationship()
    conversions: Mapped[list["UpsellConversion"]] = relationship(
        back_populates="offer"
    )

    def __repr__(self) -> str:
        return f"<UpsellOffer {self.name} - ${self.price}>"


class UpsellConversion(Base):
    __tablename__ = "upsell_conversions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id"), nullable=False
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("upsell_offers.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offered"
    )
    offered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    offer: Mapped["UpsellOffer"] = relationship(back_populates="conversions")

    def __repr__(self) -> str:
        return f"<UpsellConversion {self.status}>"
