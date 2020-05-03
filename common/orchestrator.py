import json
import docker
import pika
import requests
import sys
import uuid

from datetime import datetime
from flask import Flask, jsonify, request
from threading import Timer

app = Flask(__name__)
dockEnv = docker.from_env()
dockClient = docker.APIClient()


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
        Timer(120, spawnWorker).start()
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

    print("Opening file")
    # Find no. of read-counts
    fh = open("readCount", "r")
    count = int(fh.readline())
    fh.close()
    print("Read Count: ", count)
    workers = int(count/20) + 1
    # (?)
    containerList = dockEnv.containers.list(all)
    numContainers = len(containerList)

    newContList = []
    print(newContList)
    for image in containerList:
        print(image.attrs)
        print(image.attrs['Config'])
        if(image.attrs['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq', 'common_orchestrator']):
            newContList.append(image)

    if numContainers > workers:
        extra = numContainers - workers
        while extra:
            print("Removing worker")
            newContList[numContainers - 1].stop()
            numContainers -= 1
            extra -= 1

    elif numContainers < workers:
        extra = workers - numContainers
        while extra:
            print("Adding worker")
            dockEnv.containers.run("common_slave", ["python3", "slave.py"], links={
                                   "rmq": "rmq", "postgres": "postgres_slave"}, network="common_default", detach=True)
            numContainers += 1
            extra -= 1

    Timer(120, spawnWorker).start()


@app.route('/api/v1/crash/master', methods=["POST"])
def killMaster():
    if request.method == "POST":
        containerList = dockEnv.containers.list(all)
        # dictionary of containers and the pids, cause we have to kill slave with highest pid
        cntrdict = dict()
        for image in containerList:
            if(image.attrs['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq', 'common_orchestrator']):
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
            if(image.attrs['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq', 'common_orchestrator']):
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
            if image['Config']['Image'] not in ['zookeeper', 'python', 'postgres', 'rabbitmq', 'common_orchestrator']:
                pidlist.append(image.attrs['State']['Pid'])
        pidlist.sort()
        return jsonify(pidlist), 200
    return 405


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port='80', use_reloader=False)
