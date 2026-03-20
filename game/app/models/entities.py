from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.datetime_utils import utc_now_naive
from app.models.base import Base
from app.models.enums import ChatMode, ParticipantStatus, SessionStatus


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=True)
    bank = Column(BigInteger, default=0, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False, server_default="false")
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    sessions = relationship("PlayerToSession", back_populates="player")

    __table_args__ = (
        CheckConstraint("bank >= 0", name="ck_players_bank_non_negative"),
    )


class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(64), unique=True, nullable=False, index=True)
    meta = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    sessions = relationship("GameSession", back_populates="deck")


class GameSession(Base):
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.lobby_open, nullable=False)
    chat_mode = Column(SQLEnum(ChatMode), default=ChatMode.group, nullable=False)
    count_players = Column(Integer, default=8, nullable=False)
    dealer_cards = Column(JSON, default=list, nullable=False)
    dealer_bet = Column(BigInteger, default=0, nullable=False)
    turn_version = Column(Integer, default=0, nullable=False)
    current_position = Column(Integer, nullable=True)
    current_hand_index = Column(Integer, nullable=True)
    current_timer = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    deck = relationship("Deck", back_populates="sessions")
    players = relationship("PlayerToSession", back_populates="session")
    states = relationship("State", back_populates="session")


class PlayerToSession(Base):
    __tablename__ = "player_to_session"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    position = Column(Integer, nullable=False)
    participant_status = Column(SQLEnum(ParticipantStatus), default=ParticipantStatus.joined, nullable=False)
    bet = Column(BigInteger, default=0, nullable=False)
    insurance_bet = Column(BigInteger, default=0, nullable=False)
    cards = Column(JSON, default=list, nullable=False)

    player = relationship("Player", back_populates="sessions")
    session = relationship("GameSession", back_populates="players")
    hands = relationship("PlayerHand", back_populates="player_to_session")

    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_session_position"),
        CheckConstraint("position >= 1 AND position <= 8", name="ck_player_position_range"),
    )


class State(Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    position = Column(Integer, nullable=False)
    action = Column(String(128), nullable=False)
    time = Column(DateTime, default=utc_now_naive, nullable=False)
    details = Column(JSON, default=dict, nullable=True)

    session = relationship("GameSession", back_populates="states")

    __table_args__ = (
        CheckConstraint("position >= 1 AND position <= 8", name="ck_state_position_range"),
    )


class PlayerHand(Base):
    __tablename__ = "player_hands"

    id = Column(Integer, primary_key=True)
    player_to_session_id = Column(Integer, ForeignKey("player_to_session.id", ondelete="CASCADE"), nullable=False)
    hand_index = Column(Integer, nullable=False)
    cards = Column(JSON, default=list, nullable=False)
    bet = Column(BigInteger, default=0, nullable=False)
    participant_status = Column(SQLEnum(ParticipantStatus), default=ParticipantStatus.joined, nullable=False)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    player_to_session = relationship("PlayerToSession", back_populates="hands")

    __table_args__ = (
        UniqueConstraint("player_to_session_id", "hand_index", name="uq_player_hand_index"),
        CheckConstraint("hand_index >= 0 AND hand_index <= 3", name="ck_player_hands_hand_index_range"),
    )


Index("ix_game_sessions_deck_id", GameSession.deck_id)
Index("ix_player_hands_player_to_session_id", PlayerHand.player_to_session_id)
Index("ix_players_telegram_id", Player.telegram_id)
Index(
    "uq_unfinished_session_per_deck",
    GameSession.deck_id,
    unique=True,
    postgresql_where=(GameSession.status != SessionStatus.closed),
)
