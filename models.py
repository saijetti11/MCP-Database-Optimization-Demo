from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String


# -----------------------------------
# BASE CLASS
# -----------------------------------
class Base(DeclarativeBase):
    pass


# -----------------------------------
# EMPLOYEE TABLE
# -----------------------------------
class Employee(Base):

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)

    name = Column(String)

    department = Column(String)