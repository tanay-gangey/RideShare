from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Our postgres database:
#   Database Name: rideshare_db
#   Credentials: Username - ubuntu; Password: ride
dbURI = 'postgresql+psycopg2://ubuntu:ride@postgres_master:5432/postgres'
Base = declarative_base()
engine = create_engine(dbURI)

Session = sessionmaker(bind = engine)

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
