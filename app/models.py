from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)
    storage_limit = Column(Float, default=1.0)  # GB
    used_storage = Column(Float, default=0.0)

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    filename = Column(String)
    size = Column(Float)
    url = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
