import json
import docker
import pika
import requests
import sys
import time
import uuid

from datetime import datetime
from flask import Flask, jsonify, request
from threading import Timer

from model import doInit, Base, Ride, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from kazoo.client import KazooClient


def createNewSlave():
    slaveDb = dockEnv.containers.run(
        "postgres",
        "-p 5432",
        network="worker_default",
        environment={"POSTGRES_USER": "ubuntu", "POSTGRES_PASSWORD": "ride"},
        ports={'5432': None},
        publish_all_ports=True,
        detach=True)

    slaveCon = dockEnv.containers.get(slaveDb.name)
    dbHostName = slaveCon.attrs["Config"]['Hostname']

    dockEnv.containers.run("worker_worker:latest",
                           'sh -c "sleep 20 && python3 -u worker.py"',
                           links={"rmq": "rmq"},
                           environment={"TYPE": "slave", "DBNAME": dbHostName, "CREATED":"NEW"},
                           network="worker_default",
                           detach=True)

# def createNewMaster():
#     masterDb = dockEnv.containers.run(
#         "postgres",
#         "-p 5432",
#         network="worker_default",
#         environment={"POSTGRES_USER": "ubuntu", "POSTGRES_PASSWORD": "ride"},
#         ports={'5432': None},
#         publish_all_ports=True,
#         detach=True)

#     masterCon = dockEnv.containers.get(masterDb.name)
#     dbHostName = masterCon.attrs["Config"]['Hostname']

#     dockEnv.containers.run("worker_worker:latest",
#                            'sh -c "sleep 20 && python3 -u worker.py"',
#                            links={"rmq": "rmq"},
#                            environment={"TYPE": "slave", "DBNAME": dbHostName, "CREATED":"NEW"},
#                            network="worker_default",
#                            detach=True)

respawn = True
noOfChildren = 0



def slaves_watch():
    flag = True
    children = zk.get_children('/root',watch=slaves_watch)
    for child in children:
        data, stat = zk.get('/root/'+str(child))
        if(data == "master"):
            flag = False
            break

    if(flag):
        minimum = min(children)
        zk.set("/root/"+str(minimum),b"master")
    else:
        if(respawn):
            if(noOfChildren > len(children)):
                createNewSlave()
            else:
                noOfChildren = len(children)


app = Flask(__name__)
dockEnv = docker.from_env()
dockClient = docker.DockerClient()
# dockEnv = docker.DockerClient(base_url='unix:///var/run/docker.sock')

zk = KazooClient(hosts='zoo:2181')
zk.start()


zk.ensure_path('/root')

children = zk.get_children('/root', watch=slaves_watch)

def syncDB(dbName):
    dbURI = doInit(dbName)
    engine = create_engine(dbURI)
    Session = sessionmaker(bind = engine)

    Base.metadata.create_all(engine)
    session = Session()
    rides = session.query(Ride).all()
    users = session.query(User).all()

    newrides = list()
    newusers = list()
    for ride in rides:
        newrides.append(ride.as_dict())

    for user in users:
        newusers.append(user.as_dict())

    user_ride = [newrides,newusers]
    print(rides,users)
    connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rmq'))
    channel = connection.channel()
    channel.exchange_declare(exchange='tempQ', exchange_type='fanout')
    channel.basic_publish(
            exchange='tempQ',
            routing_key='',
            body=json.dumps(user_ride))


class readWriteReq:
    def __init__(self, publishQueue):
        self.publishQ = publishQueue
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rmq'))
        self.channel = self.connection.channel()
        # expect response to this request in the responseQ
        tempQ = self.channel.queue_declare(queue='responseQ', durable=True)
        self.resQ = tempQ.method.queue
        result = self.channel.queue_declare(queue='', durable=True)
        self.callbackQ = result.method.queue

        self.channel.basic_consume(
            queue=self.resQ,
            on_message_callback=self.onResponse,
            auto_ack=True)

    def onResponse(self, ch, method, props, body):
        print(self.corID, props.correlation_id)
        if self.corID == props.correlation_id:
            self.response = body

    def publish(self, query):
        print("In publish")
        self.response = None
        self.corID = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.publishQ,
            properties=pika.BasicProperties(
                reply_to=self.callbackQ,
                correlation_id=self.corID,
                delivery_mode=2),
            body=query)
        while self.response is None:
            self.connection.process_data_events()
        self.connection.close()
        return self.response


def getReadCount():
    fh = open("readCount", "r")
    count = int(fh.readline())
    fh.close()
    print("Read Count: ", count)
    return count


def incCount():
    fh = open("readCount", "r+")
    count = int(fh.read())
    fh.seek(0)
    count += 1
    count = str(count)
    fh.write(count)
    fh.truncate()
    fh.close()


@app.route('/api/v1/db/read', methods=["POST"])
def readDB():
    response = None
    count = getReadCount()
    incCount()
    if not count:
        print("Starting Timer")
        Timer(60, spawnWorker).start()
    if request.method == "POST":
        data = request.get_json()
        data = json.dumps(data)
        newReadReq = readWriteReq('readQ')
        response = newReadReq.publish(data).decode()
        print(response)
        response = eval(response)
        del newReadReq
        print("[x] Sent [Read] %r" % data)
        return response[0], response[1]
    return response[0], 405


@app.route('/api/v1/db/write', methods=["POST"])
def writeDB():
    response = None
    if request.method == "POST":
        data = request.get_json()
        data = json.dumps(data)
        newWriteReq = readWriteReq('writeQ')
        response = newWriteReq.publish(data).decode()
        response = eval(response)
        del newWriteReq
        print("[x] Sent [Write] %r" % data)
        return response[0], response[1]
    return response[0], 405


@app.route('/api/v1/db/clear', methods=["POST"])
def clearDB():
    response = None
    if request.method == "POST":
        data = request.get_json()
        data = json.dumps(data)
        newClearReq = readWriteReq('writeQ')
        response = newClearReq.publish(data).decode()
        response = eval(response)
        del newClearReq
        print("[x] Sent [Clear] %r" % data)
        return response[0], response[1]
    return response[0], 405


def spawnWorker():
    # Find no. of read-counts
    fh = open("readCount", "r+")
    count = int(fh.readline())
    fh.seek(0)
    newCount = 0
    newCount = str(newCount)
    fh.write(newCount)
    fh.truncate()
    fh.close()
    # print("Read Count: ", count)
    workers = int(count/10) + 1
    # (?)
    containerList = dockEnv.containers.list(all)

    newContList = []
    for image in containerList:
        if(image.attrs['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq:3.8.3-alpine', 'worker_orchestrator']):
            newContList.append(image)

    numContainers = len(newContList)

    for contInd in range(numContainers):
        if newContList[contInd].name == 'worker_worker_1':
            newContList.pop(contInd)

    # remove master
    numContainers -= 1
    
    for cont in newContList:
        print(cont.name)

    if numContainers > workers:
        extra = numContainers - workers
        respawn = False
        while extra:
            print("Removing worker")
            contToRem = newContList[-1]
            #dbToRem = contToRem.attrs["Config"]["Env"][1].split("=")[1]
            #print(dbToRem)
            contToRem.stop()
            contToRem.remove()
            #dbToRem = eval(dbToRem)
            #dbToRem.stop()
            #dbToRem.remove()
            newContList.pop(-1)
            numContainers -= 1
            extra -= 1
        respawn = True

    elif numContainers < workers:
        extra = workers - numContainers
        while extra:
            print("Adding worker")
            slaveDb = dockEnv.containers.run(
                "postgres",
                "-p 5432",
                network="worker_default",
                environment={"POSTGRES_USER": "ubuntu",
                             "POSTGRES_PASSWORD": "ride"},
                ports={'5432': None},
                publish_all_ports=True,
                detach=True)

            slaveCon = dockEnv.containers.get(slaveDb.name)
            dbHostName = slaveCon.attrs["Config"]['Hostname']

            dockEnv.containers.run("worker_worker:latest",
                                   'sh -c "sleep 20 && python3 -u worker.py"',
                                   links={"rmq": "rmq"},
                                   environment={
                                       "TYPE": "slave", "DBNAME": dbHostName, "CREATED":"NEW"},
                                   network="worker_default",
                                   detach=True)
            
            #syncDB("postgres_worker")
            numContainers += 1
            extra -= 1



    Timer(60, spawnWorker).start()



@app.route('/api/v1/db/sync',methods=["GET"])
def syncDB():
    print("IN SYNC SLAVE DB ACTUAL")
    mdbURI = doInit("postgres_worker")
    mengine = create_engine(mdbURI)
    mSession = sessionmaker(bind = mengine)

    Base.metadata.create_all(mengine)
    msession = mSession()
    rides = msession.query(Ride).all()
    users = msession.query(User).all()
    print(rides,users)
    newrides = list()
    newusers = list()
    for ride in rides:
        newrides.append(ride.as_dict())

    for user in users:
        newusers.append(user.as_dict())
    return json.dumps([newrides,newusers])


@app.route('/api/v1/crash/master', methods=["POST"])
def killMaster():
    if request.method == "POST":
        containerList = dockEnv.containers.list(all)
        # dictionary of containers and the pids, cause we have to kill slave with highest pid
        cntrdict = dict()
        for image in containerList:
            if(image.attrs['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq:3.8.3-alpine', 'worker_orchestrator']):
                # if('slave' not in image['Config']['Image'])
                cntrdict[image] = image.attrs['State']['Pid']
        # gets the key of the min value. i.e. gets the container id of the lowest pid container
        mincid = list(cntrdict.keys())[
            list(cntrdict.values()).index(min(list(cntrdict.values())))]
        mincid.kill()
        mincid.remove(v=True)
        return 200
    return 405


# im assuming we get a list of containers,  i've added sample-getcontainerpid.py for reference if this is not the case, to get the list of just slave containers we'll need zookeeper idk how to do that
@app.route('/api/v1/crash/slave', methods=["POST"])
def killSlave():
    if request.method == "POST":
        containerList = dockEnv.containers.list(all)
        # dictionary of containers and the pids, cause we have to kill slave with highest pid
        cntrdict = dict()
        for image in containerList:
            if(image.attrs['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq:3.8.3-alpine', 'worker_orchestrator']):
                cntrdict[image] = image.attrs['State']['Pid']
        # gets the key of the max value. i.e. gets the container id of the highest pid container
        maxcid = list(cntrdict.keys())[
            list(cntrdict.values()).index(max(list(cntrdict.values())))]
        maxcid.kill()  # kill that container
        maxcid.remove(v=True)
        return 200
    return 405


@app.route('/api/v1/worker/list', methods=["GET"])
def getWorkers():
    if request.method == "GET":
        containerList = dockEnv.containers.list(all)  # list of containers
        pidlist = list()
        for image in containerList:
            if image.attrs['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq:3.8.3-alpine', 'worker_orchestrator']:
                pidlist.append(image.attrs['State']['Pid'])
        pidlist.sort()
        return jsonify(pidlist), 200
    return 405


with app.app_context():
   
    slaveDb = dockEnv.containers.run(
        "postgres",
        "-p 5432",
        network="worker_default",
        environment={"POSTGRES_USER": "ubuntu", "POSTGRES_PASSWORD": "ride"},
        ports={'5432': None},
        publish_all_ports=True,
        detach=True)

    slaveCon = dockEnv.containers.get(slaveDb.name)
    dbHostName = slaveCon.attrs["Config"]['Hostname']
    
    fh = open("slavesCount","r+")
    count = int(fh.readline())
    fh.seek(0)
    newCount = 1
    newCount = str(newCount)
    fh.write(newCount)
    fh.truncate()
    fh.close()
    containerList = dockEnv.containers.list(all)

    dockEnv.containers.run("worker_worker:latest",
                           'sh -c "sleep 20 && python3 -u worker.py"',
                           links={"rmq": "rmq"},
                           environment={"TYPE": "slave", "DBNAME": dbHostName, "CREATED":"NEW"},
                           network="worker_default",
                           detach=True)
    print("Initial status: ", slaveDb.status)
    print("Created Master/Slave")
 
    for image in containerList:
        print(image.attrs['Config']['Image'], ":", image.name)
    # while(slaveDb.status != "running"):
        # print(slaveDb.status)
        # print(image.attrs)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port='80', use_reloader=False)
a