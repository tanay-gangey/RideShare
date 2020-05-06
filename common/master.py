from sqlalchemy import create_engine
from requests.models import Response
from model import Base, engine, Ride, Session, User
from flask import jsonify, request
from datetime import datetime
import collections
import docker
import json
import pika
import requests
import uuid


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
    data = json.loads(req)
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
            return (responseToReturn.text, responseToReturn.status_code)
        # Remove an existing User
        elif data["caller"] == "removeUser":
            session.query(User).filter_by(username=data["username"]).delete()
            session.query(Ride).filter_by(created_by=data["username"]).delete()
            session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code)

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
            return (responseToReturn.text, responseToReturn.status_code)

        elif data["caller"] == "joinRide":
            rideExists = session.query(Ride).filter_by(
                ride_id=data["rideId"]).first()
            if rideExists.username:
                rideExists.username += ", " + data["username"]
            else:
                rideExists.username += data["username"]
            session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code)

        elif data["caller"] == "deleteRide":
            session.query(Ride).filter_by(ride_id=data["rideId"]).delete()
            session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code)


# Wrapper for writeDB
def writeWrap(ch, method, props, body):
    body = json.dumps(eval(body.decode()))
    writeDB(body)
    channel.basic_publish(exchange='syncQ', routing_key='', body=body, properties=pika.BasicProperties(
        reply_to=props.reply_to,
        correlation_id=props.correlation_id,
        delivery_mode=2))
    # Commenting out below doesn't give response on Postman
    # Ideally we want to comment out below and get respsonse at orch from slave
    # ch.basic_publish(exchange='', routing_key=props.reply_to, properties=pika.BasicProperties(
    #     correlation_id=props.correlation_id), body=str(writeResponse))
    # ch.basic_ack(delivery_tag=method.delivery_tag)

# -----------------------------------------------------------------------------------


# Master Code
# Consume from writeQ for Master
channel.exchange_declare(exchange='syncQ', exchange_type='fanout')
# channel.basic_qos(prefetch_count=1)
channel.queue_declare(queue='writeQ', durable=True)
channel.basic_consume(queue='writeQ', on_message_callback=writeWrap)
channel.start_consuming()

# -----------------------------------------------------------------------------------
