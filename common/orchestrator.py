import json
import pika
import requests
import uuid

from datetime import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)


class readWriteReq:
    def __init__(self, publishQueue):
        self.publishQ = publishQueue
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='rmq'))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue='', durable=True)
        self.callbackQ = result.method.queue
        self.channel.basic_consume(
            queue=self.callbackQ,
            on_message_callback=self.onResponse,
            auto_ack=True)

    def onResponse(self, ch, method, props, body):
        print(self.corID, props.correlation_id)
        if self.corID == props.correlation_id:
            self.response = body

    def publish(self, query):
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


@app.route('/api/v1/db/read', methods=["POST"])
def readDB():
    response = None
    if request.method == "POST":
        data = request.get_json()
        newReadReq = readWriteReq('readQ')
        response = newReadReq.publish(data).decode()
        response = eval(response)
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
        print("[x] Sent [Write] %r" % data)
        return response[0], response[1]
    return response[0], 405


@app.route('/api/v1/db/clear', methods=["POST"])
def clearDB():
    response = None
    if request.method == "POST":
        data = request.get_json()
        newClearReq = readWriteReq('writeQ')
        response = newClearReq.publish(data).decode()
        response = eval(response)
        print("[x] Sent [Clear] %r" % data)
        return response[0], response[1]
    return response[0], 405


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port='80')