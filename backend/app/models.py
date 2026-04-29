from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    google_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean)

    bags = relationship("Bag", back_populates="user")
    discs = relationship("Disc", back_populates="user")
    rounds = relationship("Round", back_populates="user")
    throw_styles = relationship("UserThrowStyle", back_populates="user")
    user_stats = relationship("UserStat", back_populates="user")
    round_stats = relationship("RoundStat", back_populates="user")
    disc_stats = relationship("UserDiscStat", back_populates="user")


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
    computed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="user_stats")


class UserDiscStat(Base):
    __tablename__ = "user_disc_stats"

    stat_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    disc_id = Column(Integer, ForeignKey("discs.disc_id"), nullable=False)
    avg_distance = Column(Integer)
    max_distance = Column(Integer)
    sample_size = Column(Integer)
    measured_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="disc_stats")
    disc = relationship("Disc", back_populates="disc_stats")


class Bag(Base):
    __tablename__ = "bags"

    bag_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="bags")
    bag_discs = relationship("BagDisc", back_populates="bag")
    rounds = relationship("Round", back_populates="bag")


class BagDisc(Base):
    __tablename__ = "bag_disc"

    bag_id = Column(Integer, ForeignKey("bags.bag_id"), primary_key=True)
    disc_id = Column(Integer, ForeignKey("discs.disc_id"), primary_key=True)

    bag = relationship("Bag", back_populates="bag_discs")
    disc = relationship("Disc", back_populates="bag_discs")


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
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

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

    holes = relationship("Hole", back_populates="course")
    rounds = relationship("Round", back_populates="course")


class Hole(Base):
    __tablename__ = "holes"

    hole_id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    hole_number = Column(Integer, nullable=False)
    par = Column(Integer, nullable=False)
    distance = Column(Integer)
    elevation = Column(Integer)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    is_approved = Column(Boolean)

    course = relationship("Course", back_populates="holes")
    nodes = relationship("HoleNode", back_populates="hole")
    hole_hazards = relationship("HoleHazard", back_populates="hole")
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

    hole = relationship("Hole", back_populates="nodes")
    outgoing_edges = relationship("HoleEdge", foreign_keys="HoleEdge.from_node_id", back_populates="from_node")
    incoming_edges = relationship("HoleEdge", foreign_keys="HoleEdge.to_node_id", back_populates="to_node")

class HoleEdge(Base):
    __tablename__ = "hole_edges"

    hole_edge_id = Column(Integer, primary_key=True)
    from_node_id = Column(Integer, ForeignKey("hole_nodes.hole_node_id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("hole_nodes.hole_node_id"), nullable=False)
    distance = Column(Integer, nullable=False)
    fairway_width = Column(Integer)

    from_node = relationship("HoleNode", foreign_keys=[from_node_id], back_populates="outgoing_edges")
    to_node = relationship("HoleNode", foreign_keys=[to_node_id], back_populates="incoming_edges")
    edge_hazards = relationship("EdgeHazard", back_populates="edge")

class HoleHazard(Base):
    __tablename__ = "hole_hazards"

    hazard_id = Column(Integer, primary_key=True)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), nullable=False)
    hazard_type = Column(String, nullable=False)

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
    played_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_score = Column(Integer)

    user = relationship("User", back_populates="rounds")
    course = relationship("Course", back_populates="rounds")
    bag = relationship("Bag", back_populates="rounds")
    round_holes = relationship("RoundHole", back_populates="round")
    round_stats = relationship("RoundStat", back_populates="round")


class RoundHole(Base):
    __tablename__ = "round_holes"

    round_id = Column(Integer, ForeignKey("rounds.round_id"), primary_key=True)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), primary_key=True)
    score = Column(Integer, nullable=False)

    round = relationship("Round", back_populates="round_holes")
    hole = relationship("Hole", back_populates="round_holes")


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
    computed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="round_stats")
    round = relationship("Round", back_populates="round_stats")