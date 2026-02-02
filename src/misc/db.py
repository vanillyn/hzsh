from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

Base = declarative_base()


class Infraction(Base):
    __tablename__ = "infractions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    moderator_id = Column(BigInteger, nullable=False)
    guild_id = Column(BigInteger, nullable=False)

    type = Column(String(20), nullable=False)  # warn, mute, kick, ban
    reason = Column(Text, nullable=False)
    duration = Column(Integer, nullable=True)  # in seconds

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)

    message_id = Column(BigInteger, nullable=True)
    dm_sent = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Infraction #{self.id} {self.type} for {self.user_id}>"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "moderator_id": self.moderator_id,
            "guild_id": self.guild_id,
            "type": self.type,
            "reason": self.reason,
            "duration": self.duration,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "active": self.active,
        }


class Ticket(Base):
    """support tickets"""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False, index=True)
    guild_id = Column(BigInteger, nullable=False)

    creator_id = Column(BigInteger, nullable=False)
    name = Column(String(100), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    archived = Column(Boolean, default=False)

    allowed_users = Column(Text, default="")
    mods_removed = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Ticket #{self.id} '{self.name}'>"

    def get_allowed_users(self):
        """get list of allowed user ids"""
        if not self.allowed_users:
            return []
        return [int(uid) for uid in self.allowed_users.split(",") if uid]

    def add_user(self, user_id):
        """add user to allowed list"""
        allowed = self.get_allowed_users()
        if user_id not in allowed:
            allowed.append(user_id)
            self.allowed_users = ",".join(str(uid) for uid in allowed)

    def remove_user(self, user_id):
        """remove user from allowed list"""
        allowed = self.get_allowed_users()
        if user_id in allowed:
            allowed.remove(user_id)
            self.allowed_users = ",".join(str(uid) for uid in allowed)

    def to_dict(self):
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "creator_id": self.creator_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "archived": self.archived,
            "allowed_users": self.get_allowed_users(),
            "mods_removed": self.mods_removed,
        }


class ModSession(Base):
    """active moderator sessions (op/sudo)"""

    __tablename__ = "mod_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    guild_id = Column(BigInteger, nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    permanent = Column(Boolean, default=False)

    def __repr__(self):
        return f"<ModSession user={self.user_id} perm={self.permanent}>"

    @property
    def is_expired(self):
        if self.permanent:
            return False
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at

    @property
    def time_remaining(self):
        if self.permanent or not self.expires_at:
            return None
        remaining = self.expires_at - datetime.utcnow()
        return max(0, int(remaining.total_seconds()))


class ModerationConfig(Base):
    __tablename__ = "moderation_config"

    guild_id = Column(BigInteger, primary_key=True)

    log_channel_id = Column(BigInteger, nullable=True)
    mute_channel_id = Column(BigInteger, nullable=True)
    ticket_category_id = Column(BigInteger, nullable=True)
    archive_category_id = Column(BigInteger, nullable=True)

    muted_role_id = Column(BigInteger, nullable=True)
    mod_role_id = Column(BigInteger, nullable=True)
    op_role_id = Column(BigInteger, nullable=True)

    def to_dict(self):
        return {
            "guild_id": self.guild_id,
            "log_channel_id": self.log_channel_id,
            "mute_channel_id": self.mute_channel_id,
            "ticket_category_id": self.ticket_category_id,
            "archive_category_id": self.archive_category_id,
            "muted_role_id": self.muted_role_id,
            "mod_role_id": self.mod_role_id,
            "op_role_id": self.op_role_id,
        }


class Database:
    def __init__(self, database_url="sqlite:///data/hazelrun.db"):
        Path("data").mkdir(exist_ok=True)

        self.engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )

        Base.metadata.create_all(self.engine)

        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)

    def get_session(self):
        """get a new database session"""
        return self.Session()

    def close_session(self, session):
        """close a database session"""
        session.close()


_db = None


def get_database():
    """get or create database instance"""
    global _db
    if _db is None:
        _db = Database()
    return _db


def get_session():
    return get_database().get_session()


def parse_duration(duration_str):
    if not duration_str:
        return None

    duration_str = duration_str.lower().strip()

    units = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }

    try:
        if duration_str[-1] in units:
            value = int(duration_str[:-1])
            unit = duration_str[-1]
            return value * units[unit]
        else:
            return int(duration_str)
    except (ValueError, IndexError):
        return None


def format_relative_time(seconds):
    """format seconds into relative time string"""
    if seconds is None:
        return "permanent"

    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    elif seconds < 604800:
        return f"{seconds // 86400}d"
    else:
        return f"{seconds // 604800}w"


def format_timestamp(dt, relative=True):
    """format datetime for discord"""
    if dt is None:
        return "never"

    timestamp = int(dt.timestamp())

    if relative:
        return f"<t:{timestamp}:R>"  # relative
    else:
        return f"<t:{timestamp}:F>"  # full


def get_expiry_time(duration_seconds):
    """get expiry datetime from duration in seconds"""
    if duration_seconds is None:
        return None
    return datetime.utcnow() + timedelta(seconds=duration_seconds)
