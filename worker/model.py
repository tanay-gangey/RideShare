from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
# Our postgres database:
#   Credentials: Username - ubuntu; Password: ride

def doInit(dbName):
    dbURI = 'postgresql+psycopg2://ubuntu:ride@' + dbName + ':5432/postgres' 
    return dbURI

Base = declarative_base()

class User(Base):
    '''
    Model for a User.
    '''
    __tablename__ = 'User'
    user_id = Column(Integer, primary_key = True, autoincrement = True)
    username = Column(Text, unique = True, nullable = False)
    password = Column(String(40), nullable = False)

    def __repr__(self):
        return f"User('{self.user_id}','{self.username}')"

    def as_dict(self):
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Ride(Base):
    '''
    Model for a Ride.
    '''
    __tablename__ = 'Ride'
    ride_id = Column(Integer, primary_key = True, nullable = False)
    created_by = Column(Text, nullable = False)
    username = Column(Text, nullable = True)
    timestamp = Column(Text, nullable = False)
    source = Column(Text, nullable = False)
    destination = Column(Text, nullable = False)

    # def __repr__(self):
    #     return f"Ride('{self.ride_id}','{self.created_by}', '{self.source}', '{self.destination}')"

    def __repr__(self):
        return f"Ride('{self.ride_id}','{self.created_by}', '{self.source}', '{self.destination}')"

    def as_dict(self):
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}
