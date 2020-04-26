import sys
import json, requests, collections
from datetime import datetime
from flask import Flask, request, jsonify
import pika
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))

channel = connection.channel()

channel.queue_declare(queue='readQueue')
channel.exchange_declare(exchange='syncQueue', exchange_type='fanout')
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue
channel.queue_bind(exchange='syncQueue', queue=queue_name)


#if this flask thing doesnt work another way of setting up the database is in sharanya's screenshot, pl try that
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ubuntu:ride@user_db:5432/postgres' #might have to change this based on your docker file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    #clearData()
    db.create_all() 


def checkHash(password):
    if len(password) == 40:
        password = password.lower()
        charSet = {"a", "b", "c", "d", "e", "f"}
        numSet = {'1','2','3','4','5','6','7','8','9','0'}
        for char in password:
            if char not in charSet and char not in numSet:
                return False
        return True
    return False


def timeAhead(timestamp):
    currTimeStamp = datetime.now().isoformat(' ', 'seconds')
    currTimeStamp = datetime.strptime(currTimeStamp, "%Y-%m-%d %H:%M:%S")
    convertedTimeStamp = datetime.strptime(timestamp, "%d-%m-%Y:%S-%M-%H")
    if currTimeStamp < convertedTimeStamp:
        return True
    return False



def syncDB(req):
    #data = json.loads(req)
	data = req.get_json()
	#if the above line doesnt work try data = json.loads(req)
    if data["table"] == "User":
        # Add a new User
        if data["caller"] == "addUser":
            responseToReturn = Response()
            if checkHash(data["password"]):
                newUser = User(username = data["username"], password = data["password"])
                db.session.add(newUser)
                db.session.commit()
                responseToReturn.status_code = 201
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())
        # Remove an existing User     
        elif data["caller"] == "removeUser":
            User.query.filter_by(username = data["username"]).delete()
            Ride.query.filter_by(created_by = data["username"]).delete()
            db.session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

    elif data["table"] == "Ride":
        # Add a new Ride
        if data["caller"] == "createRide":
            source = int(data["source"])
            dest = int(data["destination"])
            responseToReturn = Response()
            if source in range(1, noRows + 1) and dest in range(1, noRows + 1):
                newRide = Ride(created_by = data["created_by"], username = "", timestamp = data["timestamp"],
                        source = source, destination = dest)
                db.session.add(newRide)
                db.session.commit()
                responseToReturn.status_code = 201
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

        elif data["caller"] == "joinRide":
            rideExists = Ride.query.filter_by(ride_id = data["rideId"]).first()
            if rideExists.username:
                rideExists.username += ", " + data["username"]
            else:
                rideExists.username += data["username"]
            db.session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

        elif data["caller"] == "deleteRide":
            Ride.query.filter_by(ride_id = data["rideId"]).delete()
            db.session.commit()
            responseToReturn = Response()
            responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())



def do_some_read_op(req):
	#data = json.loads(req)
	data = request.get_json()
    if data["table"] == "User":
        checkUserSet = {"removeUser", "createRide"}
        if data["caller"] in checkUserSet:
            userExists = User.query.filter_by(username = data["username"]).all()
            responseToReturn = Response()
            if userExists:
                responseToReturn.status_code = 200
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())
        
        elif data["caller"] == "addUser":
            userExists = User.query.filter_by(username = data["username"]).all()
            responseToReturn = Response()
            if userExists:
                responseToReturn.status_code = 400
            else:
                responseToReturn.status_code = 200
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())
        
    elif data["table"] == "Ride":
        if data["caller"] == "listUpcomingRides":
            rides = Ride.query.all()
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
            rideExists = Ride.query.filter_by(ride_id = data["rideId"]).all()
            responseToReturn = Response()
            if rideExists:
                responseToReturn.status_code = 200
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())

        elif data["caller"] == "joinRide":
            userExists = User.query.filter_by(username = data["username"]).all()
            rideExists = Ride.query.filter_by(ride_id = data["rideId"]).all()
            responseToReturn = Response()
            if userExists and rideExists:
                responseToReturn.status_code = 200
            else:
                responseToReturn.status_code = 400
            return (responseToReturn.text, responseToReturn.status_code, responseToReturn.headers.items())


def on_sync_request(ch, method, props, body):
    data = body	
    response = syncDB(data)
	return response

def on_read_request(ch, method, props, body):
    data = body
	
    response = do_some_read_op(data)

    ch.basic_publish(exchange='',routing_key=props.reply_to, properties=pika.BasicProperties(correlation_id = props.correlation_id),body=str(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)
	return response


channel.basic_qos(prefetch_count=1)
#slave does this
channel.basic_consume(queue=queue_name, on_message_callback=on_sync_request, auto_ack=True)#first sync the database
channel.basic_consume(queue='readQueue', on_message_callback=on_read_request)#then read


print(" [x] Awaiting RPC requests")
channel.start_consuming()
