from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
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

    c1_percent = Column(Float)
    c1x_percent = Column(Float)
    c2_percent = Column(Float)
    gir_c1 = Column(Float)
    gir_c2 = Column(Float)
    parked = Column(Float)

    bags = relationship("Bag", back_populates="user")
    discs = relationship("Disc", back_populates="user")


class Bag(Base):
    __tablename__ = "bags"

    bag_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    name = Column(String)
    is_active = Column(Boolean)

    user = relationship("User", back_populates="bags")
    bag_discs = relationship("BagDisc", back_populates="bag")


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
    speed = Column(Float)
    glide = Column(Float)
    turn = Column(Float)
    fade = Column(Float)
    wear = Column(Float)
    color = Column(String)
    weight = Column(Integer)
    disc_type = Column(String)
    manufacturer = Column(String)
    name = Column(String)
    throw_distance = Column(Integer)

    user = relationship("User", back_populates="discs")
    bag_discs = relationship("BagDisc", back_populates="disc")


class Course(Base):
    __tablename__ = "courses"

    course_id = Column(Integer, primary_key=True)
    name = Column(String)
    location = Column(String)
    total_par = Column(Integer)

    holes = relationship("Hole", back_populates="course")


class Hole(Base):
    __tablename__ = "holes"

    hole_id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)
    hole_number = Column(Integer)
    par = Column(Integer)
    distance = Column(Integer)
    elevation = Column(Integer)

    course = relationship("Course", back_populates="holes")
    nodes = relationship("HoleNode", back_populates="hole")
    hazards = relationship("Hazard", back_populates="hole")


class HoleNode(Base):
    __tablename__ = "hole_nodes"

    hole_node_id = Column(Integer, primary_key=True)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), nullable=False)
    node_type = Column(String)  # tee / landing_zone / mando / dogleg / basket
    label = Column(String, nullable=True)

    hole = relationship("Hole", back_populates="nodes")
    outgoing_edges = relationship("HoleEdge", foreign_keys="HoleEdge.from_node_id", back_populates="from_node")
    incoming_edges = relationship("HoleEdge", foreign_keys="HoleEdge.to_node_id", back_populates="to_node")


class HoleEdge(Base):
    __tablename__ = "hole_edges"

    hole_edge_id = Column(Integer, primary_key=True)
    from_node_id = Column(Integer, ForeignKey("hole_nodes.hole_node_id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("hole_nodes.hole_node_id"), nullable=False)
    distance = Column(Integer)
    required_line_shape = Column(String)

    from_node = relationship("HoleNode", foreign_keys=[from_node_id], back_populates="outgoing_edges")
    to_node = relationship("HoleNode", foreign_keys=[to_node_id], back_populates="incoming_edges")
    hazards = relationship("Hazard", back_populates="edge")

class Hazard(Base):
    __tablename__ = "hazards"

    hazard_id = Column(Integer, primary_key=True)
    hole_id = Column(Integer, ForeignKey("holes.hole_id"), nullable=False)
    hole_edge_id = Column(Integer, ForeignKey("hole_edges.hole_edge_id"), nullable=True)
    hazard_type = Column(String)

    hole = relationship("Hole", back_populates="hazards")
    edge = relationship("HoleEdge", back_populates="hazards")