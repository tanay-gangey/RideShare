import collections
import docker
import json
import pika
import requests

from datetime import datetime
from flask import jsonify, request
from model import Base, engine, Ride, Session, User
from requests.models import Response
from sqlalchemy import create_engine

# Create tables in database
Base.metadata.create_all(engine)
session = Session()

# Connecting to the RabbitMQ container
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rmq'))
channel = connection.channel()

# ------------------------------------------------------------------------------------

# Common Code [to Master & Slave]


def checkHash(password):
    if len(password) == 40:
        password = password.lower()
        charSet = {"a", "b", "c", "d", "e", "f"}
        numSet = {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0'}
        for char in password:
            if char not in charSet and char not in numSet:
                return False
        return True
    return False


def writeDB(req):
    data = req.get_json()
    # if the above line doesnt work try data = json.loads(req)
    if data["table"] == "User":
        # Add a new User
        if data["caller"] == "addUser":
            responseToReturn = Response()
            if checkHash(data["password"]):
                newUser = User(
                    username=data["username"], password=data["password"])
                session.add(newUser)
                session.commit()
                responseToReturn.status_code = 201
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())
        # Remove an existing User
        elif data["caller"] == "removeUser":
            session.query(User).filter_by(username=data["username"]).delete()
            session.query(Ride).filter_by(created_by=data["username"]).delete()
            session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

    elif data["table"] == "Ride":
        # Add a new Ride
        if data["caller"] == "createRide":
            source = int(data["source"])
            dest = int(data["destination"])
            responseToReturn = Response()
            noRows = 198
            if source in range(1, noRows + 1) and dest in range(1, noRows + 1):
                newRide = Ride(created_by=data["created_by"], username="", timestamp=data["timestamp"],
                               source=source, destination=dest)
                session.add(newRide)
                session.commit()
                responseToReturn.status_code = 201
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

        elif data["caller"] == "joinRide":
            rideExists = session.query(Ride).filter_by(ride_id=data["rideId"]).first()
            if rideExists.username:
                rideExists.username += ", " + data["username"]
            else:
                rideExists.username += data["username"]
            session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

        elif data["caller"] == "deleteRide":
            session.query(Ride).filter_by(ride_id=data["rideId"]).delete()
            session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())


# Wrapper for writeDB
def writeWrap(ch, method, props, body):
    writeResponse = writeDB(body)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    channel.basic_publish(exchange='syncQ', routing_key='', body=body)
    ch.basic_publish(exchange='', routing_key=props.reply_to, properties=pika.BasicProperties(
        correlation_id=props.correlation_id), body=str(writeResponse))
    return writeResponse

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------

# Slave Code

def timeAhead(timestamp):
    currTimeStamp = datetime.now().isoformat(' ', 'seconds')
    currTimeStamp = datetime.strptime(currTimeStamp, "%Y-%m-%d %H:%M:%S")
    convertedTimeStamp = datetime.strptime(timestamp, "%d-%m-%Y:%S-%M-%H")
    if currTimeStamp < convertedTimeStamp:
        return True
    return False

def readDB(req):
    # data = json.loads(req)
    data = request.get_json()
    if data["table"] == "User":
        checkUserSet = {"removeUser", "createRide"}
        if data["caller"] in checkUserSet:
            userExists = session.query(User).filter_by(username = data["username"]).all()
            responseToReturn = Response()
            if userExists:
                responseToReturn.status_code = 200
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())
        
        elif data["caller"] == "addUser":
            userExists = session.query(User).filter_by(username = data["username"]).all()
            responseToReturn = Response()
            if userExists:
                responseToReturn.status_code = 400
            else:
                responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())
        
    elif data["table"] == "Ride":
        if data["caller"] == "listUpcomingRides":
            rides = session.query(Ride).all()
            returnObj = []
            for ride in rides:
                if ride.source == data["source"] and ride.destination == data["destination"]:
                    if timeAhead(ride.timestamp):
                        newObj = {"rideId":ride.ride_id, "username":ride.created_by, "timestamp":ride.timestamp}
                        returnObj.append(newObj)
            responseToReturn = Response()
            if not returnObj:
                responseToReturn.status_code = 204
            else:
                responseToReturn.status_code = 200
            return (jsonify(returnObj), responseToReturn.status_code, responseToReturn.headers.items())
        
        elif data["caller"] == "listRideDetails":
            rides = Ride.query.all()
            userArray = []
            dictToReturn = dict()
            responseToReturn = Response()
            rideNotFound = True
            for ride in rides:
                if ride.ride_id == int(data["rideId"]):
                    rideNotFound = False
                    userArray = ride.username.split(", ")
                    if userArray[0] == "":
                        userArray.clear()
                    responseToReturn.status_code = 200
                    keyValues = [("rideId", ride.ride_id), ("created_by", ride.created_by),
                    ("users", userArray), ("timestamp", ride.timestamp), ("source", ride.source),
                    ("destination", ride.destination)]
                    dictToReturn = collections.OrderedDict(keyValues)
                    break
            if rideNotFound:
                responseToReturn.status_code = 204
            return (jsonify(dictToReturn), responseToReturn.status_code, responseToReturn.headers.items())

        elif data["caller"] == "deleteRide":
            rideExists = session.query(Ride).filter_by(ride_id = data["rideId"]).all()
            responseToReturn = Response()
            if rideExists:
                responseToReturn.status_code = 200
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

        elif data["caller"] == "joinRide":
            userExists = session.query(User).filter_by(username = data["username"]).all()
            rideExists = session.query(Ride).filter_by(ride_id = data["rideId"]).all()
            responseToReturn = Response()
            if userExists and rideExists:
                responseToReturn.status_code = 200
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())


# Wrapper for read
def readWrap(ch, method, props, body):
    readResponse = writeDB(body)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    ch.basic_publish(exchange='', routing_key=props.reply_to, properties=pika.BasicProperties(
        correlation_id=props.correlation_id), body=str(readResponse))
    return readResponse

# Consume from readQ for Slave
channel.basic_qos(prefetch_count=1)
# Sync database with master
channel.basic_consume(queue='syncQ', on_message_callback=writeWrap, auto_ack=True)
# Read after sync
channel.basic_consume(queue='readQ', on_message_callback=readWrap)
channel.start_consuming()
# -----------------------------------------------------------------------------------