from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import *
from sqlalchemy.orm import *


db = SQLAlchemy()
class User(db.Model):
    '''
    Model for a User.
    '''
    __tablename__ = 'User'
    user_id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    username = db.Column(db.Text, unique = True, nullable = False)
    password = db.Column(db.String(40), nullable = False)

    # def __repr__(self):
    #     return f"User('{self.user_id}','{self.username}')"


class Ride(db.Model):
    '''
    Model for a Ride.
    '''
    __tablename__ = 'Ride'
    ride_id = db.Column(db.Integer, primary_key = True, nullable = False)
    created_by = db.Column(db.Text, nullable = False)
    username = db.Column(db.Text, nullable = True)
    timestamp = db.Column(db.Text, nullable = False)
    source = db.Column(db.Text, nullable = False)
    destination = db.Column(db.Text, nullable = False)


    # def __repr__(self):
    #     return f"Ride('{self.ride_id}','{self.created_by}', '{self.source}', '{self.destination}')"


'''class userRides(db.Model):
    \'''
    Model for table storing username to ride_id mappings.
    \'''
    __tablename__ = 'userRides'
    index_id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.Integer, ForeignKey(User.username))
    ride_id = db.Column(db.Column, ForeignKey(Ride.ride_id))
    user = relationship('User', backref='userRide')
    ride = relationship('Ride', backref='userRide2')'''