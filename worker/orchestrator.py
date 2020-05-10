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

master = "worker_worker_1"

def getSlavesCount():
    fh = open("slavesCount", "r")
    count = int(fh.readline())
    fh.close()
    return count

def incSlavesCount():
    fh = open("slavesCount", "r+")
    count = int(fh.read())
    fh.seek(0)
    count += 1
    count = str(count)
    print(count)
    fh.write(count)
    fh.truncate()
    fh.close()


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
    
    newCon = dockEnv.containers.run("worker_worker:latest",
                           'sh -c "sleep 20 && python3 -u worker.py"',
                           links={"rmq": "rmq"},
                           environment={"TYPE": "slave", "DBNAME": dbHostName, "CREATED":"NEW"},
                           network="worker_default",
                           detach=True,name="worker_worker_"+str(getSlavesCount()))
    # while(newCon.status != "running"):
    #     pass

    incSlavesCount()

respawn = True
noOfChildren = 0

zk = KazooClient(hosts='zoo:2181')
zk.start()

def slaves_watch(event):
    
    print("---------------------IM WATCHING YOUR SLAVES------------------------------")
    global noOfChildren, master
    global respawn
    flag = True
    children = zk.get_children('/root',watch=slaves_watch)
    for child in children:
        data, stat = zk.get('/root/'+str(child))
        data = data.decode("utf-8")
        print(data, type(data))
        if(data == "master"):
            flag = False
            break
    if(flag):
        print(children)
        children = list(map(int, children))
        minimum = min(children)
        print(minimum)
        
        zk.set("/root/"+str(minimum),b"master")
        master = "worker_worker_"+ str(minimum)
    
        createNewSlave()
    else:
        print(children)
        if(respawn):
            if(noOfChildren > len(children)):
                print("CREATING NEW SLAVE IN WATCH")
                createNewSlave()
            else:
                print("IM ELSE-ELSE")
                noOfChildren = len(children)
    print("no of children and len(children) respawn",noOfChildren,len(children),respawn,flag)
    

app = Flask(__name__)
dockEnv = docker.from_env()
dockClient = docker.DockerClient()
zk.create('/root',b'root')

children = zk.get_children('/root', watch=slaves_watch)

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
        data = {"table":"both", "caller":"clearData"}
        newClearReq = readWriteReq('writeQ')
        response = newClearReq.publish(data).decode()
        response = eval(response)
        del newClearReq
        print("[x] Sent [Clear] %r" % data)
        return response[0], response[1]
    return response[0], 405


def spawnWorker():
    global respawn,noOfChildren,master
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
        if newContList[contInd].name == master:
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
            contToRem.stop()
            contToRem.remove()
            noOfChildren-=1
            newContList.pop(-1)
            numContainers -= 1
            extra -= 1

    elif numContainers < workers:
        extra = workers - numContainers
        incSlavesCount()
        while extra:
            print("Adding worker")
            
            
            print("Container name is :",getSlavesCount())
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
            
            newCon = dockEnv.containers.run("worker_worker:latest",
                                   'sh -c "sleep 20 && python3 -u worker.py"',
                                   links={"rmq": "rmq"},
                                   environment={
                                       "TYPE": "slave", "DBNAME": dbHostName, "CREATED":"NEW"},
                                   network="worker_default",
                                   detach=True,name="worker_worker_"+str(getSlavesCount()))
            print(newCon.status)
            # while(newCon.status != "running"):
                
            #     pass

            incSlavesCount()
            #syncDB("postgres_worker")
            numContainers += 1
            extra -= 1



    Timer(60, spawnWorker).start()


@app.route('/api/v1/zoo/count',methods=["GET"])
def getSCount():
    fh = open("slavesCount", "r")
    count = int(fh.readline())
    fh.close()
    print("Slave Count: ", count)
    return json.dumps(count)


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
    global respawn
    respawn = True
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
        return {}, 200
    return {}, 405


# im assuming we get a list of containers,  i've added sample-getcontainerpid.py for reference if this is not the case, to get the list of just slave containers we'll need zookeeper idk how to do that
@app.route('/api/v1/crash/slave', methods=["POST"])
def killSlave():
    global respawn
    respawn = True
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
        return {}, 200
    return {}, 405


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
    print("Creating slave")
    slaveDb = dockEnv.containers.run(
        "postgres",
        "-p 5432",
        network="worker_default",
        environment={"POSTGRES_USER": "ubuntu", "POSTGRES_PASSWORD": "ride"},
        ports={'5432': None},
        publish_all_ports=True,
        detach=True)
    print(slaveDb.name)
    slaveCon = dockEnv.containers.get(slaveDb.name)
    dbHostName = slaveCon.attrs["Config"]['Hostname']
    

    slave = dockEnv.containers.run("worker_worker:latest",
                           'sh -c "sleep 20 && python3 -u worker.py"',
                           links={"rmq": "rmq"},
                           environment={"TYPE": "slave", "DBNAME": dbHostName, "CREATED":"NEW"},
                           network="worker_default",
                           detach=True,name="worker_worker_2")
    print("Initial status: ", slaveDb.status)
    print("Created Master/Slave")
    print(slave.name)
    containerList = dockEnv.containers.list(all)
    
  

    for image in containerList:
        print(image.attrs['Config']['Image'], ":", image.name)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port='80', use_reloader=False)
