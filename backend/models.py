from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class AppState(Base):
    """Singleton-style key/value store for app-level state (license, vault salt, install_uuid)."""

    __tablename__ = "app_state"
    key = Column(String(64), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_enc = Column(String(512), nullable=False)  # AES-256 encrypted
    proxy = Column(String(255))  # socks5://user:pass@host:port
    status = Column(String(20), default="active")  # active | suspended | banned
    chrome_profile_dir = Column(String(512))  # per-account Chrome user data dir
    cookies_json = Column(Text)  # serialized Selenium cookies
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)

    groups = relationship(
        "Group", back_populates="account", cascade="all, delete-orphan"
    )
    posts = relationship("Post", back_populates="account", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    fb_group_id = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    tag = Column(String(100))
    platform = Column(
        String(20), nullable=False, default="fb"
    )  # fb | threads | x | instagram
    platform_entity_id = Column(
        String(500), nullable=True
    )  # X community ID, Instagram handle, etc.
    rules = Column(Text)
    rules_scraped_at = Column(DateTime)
    last_post_at = Column(DateTime)
    post_count = Column(Integer, default=0)
    join_status = Column(String(20), default="joined")  # joined | pending | rejected
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="groups")
    post_records = relationship("PostRecord", back_populates="group")


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    content = Column(Text, nullable=False)
    images_json = Column(Text)  # JSON array of local file paths
    group_ids_json = Column(Text)  # JSON array of selected group IDs
    status = Column(
        String(20), default="queued"
    )  # queued | running | paused | completed | failed
    interval_sec = Column(Integer, default=90)
    auto_delete_days = Column(Integer)
    scheduled_at = Column(DateTime)  # NULL = immediate
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    total_groups = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="posts")
    records = relationship(
        "PostRecord", back_populates="post", cascade="all, delete-orphan"
    )


class PostRecord(Base):
    __tablename__ = "post_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"))
    group_name = Column(String(500), nullable=False)
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    fb_post_url = Column(String(1000))
    post_url = Column(
        String(1000), nullable=True
    )  # generic post URL for non-FB platforms
    status = Column(
        String(20), nullable=False
    )  # active | pending_delete | deleted | failed | delete_failed
    error_msg = Column(Text)
    posted_at = Column(DateTime)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="records")
    group = relationship("Group", back_populates="post_records")
