from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Enum, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

Base = declarative_base()


def utcnow() -> datetime:
    """Naive-UTC timestamp (datetime.utcnow is deprecated in Python 3.12+)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    google_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    username = Column(String, unique=True)
    created_at = Column(DateTime, default=utcnow)
    is_admin = Column(Boolean)

    bags = relationship("Bag", back_populates="user")
    discs = relationship("Disc", back_populates="user")
    rounds = relationship("Round", back_populates="user")
    throw_styles = relationship("UserThrowStyle", back_populates="user")
    user_stats = relationship("UserStat", back_populates="user")
    round_stats = relationship("RoundStat", back_populates="user")
    disc_stats = relationship("UserDiscStat", back_populates="user")
    throw_sessions = relationship("ThrowSession", back_populates="user")


class UserThrowStyle(Base):
    __tablename__ = "user_throw_style"

    throw_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    hand = Column(Enum('right', 'left', name='hand_enum'), nullable=False)
    throw_type = Column(Enum('backhand', 'forehand', name='throw_type_enum'), nullable=False)
    priority = Column(Integer, nullable=False)

    user = relationship("User", back_populates="throw_styles")


class UserStat(Base):
    __tablename__ = "user_stats"

    stat_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    c1_percent = Column(Float)
    c1x_percent = Column(Float)
    c2_percent = Column(Float)
    gir_c1 = Column(Float)
    gir_c2 = Column(Float)
    parked = Column(Float)
    computed_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="user_stats")


class UserDiscStat(Base):
    __tablename__ = "user_disc_stats"

    stat_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    disc_id = Column(Integer, ForeignKey("discs.disc_id"), nullable=False)
    # One row per (user, disc, style): forehand and backhand carry differently
    throw_style = Column(String, nullable=False, default="backhand", server_default="backhand")
    avg_distance = Column(Integer)
    max_distance = Column(Integer)
    sample_size = Column(Integer)
    measured_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="disc_stats")
    disc = relationship("Disc", back_populates="disc_stats")


class ThrowSession(Base):
    """A measuring session: one marked start point (e.g. a tee or field spot),
    reused across multiple measured throws."""
    __tablename__ = "throw_sessions"

    session_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    label = Column(String)
    start_latitude = Column(Float, nullable=False)
    start_longitude = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("User", back_populates="throw_sessions")
    throws = relationship("ThrowMeasurement", back_populates="session", cascade="all, delete-orphan")


class ThrowMeasurement(Base):
    __tablename__ = "throw_measurements"

    throw_id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("throw_sessions.session_id"), nullable=False)
    disc_id = Column(Integer, ForeignKey("discs.disc_id"), nullable=True)
    throw_style = Column(String)  # 'backhand' | 'forehand' (null = unknown/legacy)
    end_latitude = Column(Float, nullable=False)
    end_longitude = Column(Float, nullable=False)
    distance_ft = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    session = relationship("ThrowSession", back_populates="throws")
    disc = relationship("Disc")


class Bag(Base):
    __tablename__ = "bags"

    bag_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, onupdate=utcnow)

    user = relationship("User", back_populates="bags")
    bag_discs = relationship("BagDisc", back_populates="bag")
    rounds = relationship("Round", back_populates="bag")


class BagDisc(Base):
    __tablename__ = "bag_disc"

    bag_id = Column(Integer, ForeignKey("bags.bag_id"), primary_key=True)
    disc_id = Column(Integer, ForeignKey("discs.disc_id"), primary_key=True)

    bag = relationship("Bag", back_populates="bag_discs")
    disc = relationship("Disc", back_populates="bag_discs")


class DiscCatalog(Base):
    """Local cache of DiscIt search results: search here first, only hit the
    external API on a miss so we stay friendly with their rate limits."""
    __tablename__ = "disc_catalog"

    catalog_id = Column(Integer, primary_key=True)
    discit_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    brand = Column(String)
    category = Column(String)
    speed = Column(String)
    glide = Column(String)
    turn = Column(String)
    fade = Column(String)
    stability = Column(String)
    link = Column(String)
    pic = Column(String)
    color = Column(String)
    background_color = Column(String)
    fetched_at = Column(DateTime, default=utcnow, nullable=False)


class Disc(Base):
    __tablename__ = "discs"

    disc_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    disc_type = Column(Enum('putter', 'midrange', 'fairway_driver', 'distance_driver', name='disc_type_enum'), nullable=False)
    manufacturer = Column(String)
    name = Column(String)
    speed = Column(Float)
    glide = Column(Float)
    turn = Column(Float)
    fade = Column(Float)
    wear = Column(Float)
    weight = Column(Integer)
    color = Column(String)
    updated_at = Column(DateTime, onupdate=utcnow)

    user = relationship("User", back_populates="discs")
    bag_discs = relationship("BagDisc", back_populates="disc")
    disc_stats = relationship("UserDiscStat", back_populates="disc")


class Course(Base):
    __tablename__ = "courses"

    course_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String)
    state = Column(String)
    address = Column(String)
    total_par = Column(Integer)
    is_approved = Column(Boolean)

    holes = relationship("Hole", back_populates="course", cascade="all, delete-orphan")
    rounds = relationship("Round", back_populates="course")


class Hole(Base):
    __tablename__ = "holes"

    hole_id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    hole_number = Column(Integer, nullable=False)
    par = Column(Integer, nullable=False)
    distance = Column(Integer)
    elevation = Column(Integer)
    updated_at = Column(DateTime, onupdate=utcnow)
    is_approved = Column(Boolean)

    course = relationship("Course", back_populates="holes")
    nodes = relationship("HoleNode", back_populates="hole", cascade="all, delete-orphan")
    hole_hazards = relationship("HoleHazard", back_populates="hole", cascade="all, delete-orphan")
    round_holes = relationship("RoundHole", back_populates="hole")

class HoleNode(Base):
    __tablename__ = "hole_nodes"

    hole_node_id = Column(Integer, primary_key=True)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), nullable=False)
    node_type = Column(Enum('tee', 'landing_zone', 'mando', 'dogleg', 'basket', name='node_type_enum'), nullable=False)
    sequence = Column(Integer, nullable=False)
    label = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    centerline_distance = Column(Float, nullable=True)
    is_fairway = Column(Boolean, nullable=False, default=True, server_default="true")

    hole = relationship("Hole", back_populates="nodes")
    outgoing_edges = relationship("HoleEdge", foreign_keys="HoleEdge.from_node_id", back_populates="from_node", cascade="all, delete-orphan")
    incoming_edges = relationship("HoleEdge", foreign_keys="HoleEdge.to_node_id", back_populates="to_node", cascade="all, delete-orphan")

class HoleEdge(Base):
    __tablename__ = "hole_edges"

    hole_edge_id = Column(Integer, primary_key=True)
    from_node_id = Column(Integer, ForeignKey("hole_nodes.hole_node_id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("hole_nodes.hole_node_id"), nullable=False)
    distance = Column(Integer, nullable=False)
    fairway_width = Column(Integer)

    from_node = relationship("HoleNode", foreign_keys=[from_node_id], back_populates="outgoing_edges")
    to_node = relationship("HoleNode", foreign_keys=[to_node_id], back_populates="incoming_edges")
    edge_hazards = relationship("EdgeHazard", back_populates="edge", cascade="all, delete-orphan")

class HoleHazard(Base):
    __tablename__ = "hole_hazards"

    hazard_id = Column(Integer, primary_key=True)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), nullable=False)
    hazard_type = Column(String, nullable=False)
    # JSON array of [lat, lng] pairs tracing the hazard area (open ring)
    polygon = Column(Text)

    hole = relationship("Hole", back_populates="hole_hazards")


class EdgeHazard(Base):
    __tablename__ = "edge_hazards"

    hazard_id = Column(Integer, primary_key=True)
    hole_edge_id = Column(Integer, ForeignKey("hole_edges.hole_edge_id"), nullable=False)
    hazard_type = Column(String, nullable=False)

    edge = relationship("HoleEdge", back_populates="edge_hazards")

class Round(Base):
    __tablename__ = "rounds"

    round_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    bag_id = Column(Integer, ForeignKey("bags.bag_id"), nullable=False)
    played_at = Column(DateTime, default=utcnow, nullable=False)
    total_score = Column(Integer)
    # Chosen at round setup: how to score (discs | lies | detail | score)
    # and which holes to play (full | front9 | back9)
    tracking_mode = Column(String, default="lies", server_default="lies", nullable=False)
    layout = Column(String, default="full", server_default="full", nullable=False)

    user = relationship("User", back_populates="rounds")
    course = relationship("Course", back_populates="rounds")
    bag = relationship("Bag", back_populates="rounds")
    round_holes = relationship("RoundHole", back_populates="round")
    round_stats = relationship("RoundStat", back_populates="round")
    throws = relationship("RoundThrow", back_populates="round", cascade="all, delete-orphan")


class RoundHole(Base):
    __tablename__ = "round_holes"

    round_id = Column(Integer, ForeignKey("rounds.round_id"), primary_key=True)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), primary_key=True)
    score = Column(Integer, nullable=False)

    round = relationship("Round", back_populates="round_holes")
    hole = relationship("Hole", back_populates="round_holes")


class RoundThrow(Base):
    """Every throw of a live round: where it started, where it landed, what
    was thrown. Powers C1/C2 putting, fairway hits, and per-disc round stats."""
    __tablename__ = "round_throws"

    round_throw_id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("rounds.round_id"), nullable=False)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), nullable=False)
    throw_number = Column(Integer, nullable=False)
    disc_id = Column(Integer, ForeignKey("discs.disc_id"), nullable=True)
    throw_style = Column(String)  # 'backhand' | 'forehand' (null = unknown/legacy)
    start_latitude = Column(Float)
    start_longitude = Column(Float)
    end_latitude = Column(Float)
    end_longitude = Column(Float)
    distance_ft = Column(Float)
    # Zone-based detailed scoring (no GPS needed): where the throw landed and,
    # after an OB, where the penalty drop is taken
    landing_zone = Column(String)  # basket | c1 | c2 | fairway | off_fairway | ob
    drop_zone = Column(String)     # c1 | c2 | fairway | off_fairway | tee_pad
    is_holed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    round = relationship("Round", back_populates="throws")
    disc = relationship("Disc")


class RoundStat(Base):
    __tablename__ = "round_stats"

    stat_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    round_id = Column(Integer, ForeignKey("rounds.round_id"), nullable=False)
    c1_percent = Column(Float)
    c1x_percent = Column(Float)
    c2_percent = Column(Float)
    gir_c1 = Column(Float)
    gir_c2 = Column(Float)
    parked = Column(Float)
    computed_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="round_stats")
    round = relationship("Round", back_populates="round_stats")