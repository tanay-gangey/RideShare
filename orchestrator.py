import sys
import json, requests, collections
from datetime import datetime
from flask import Flask, request, jsonify
import pika

app = Flask(__name__)

response = None
corr_id = None
def on_response(ch, method, props, body):
	global response
	if(corr_id  = props.correlation_id):
		response = body
	


connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
result = channel.queue_declare(queue='', exclusive=True)
callback_queue = result.method.queue
channel.basic_consume(queue=callback_queue,on_message_callback = on_response,auto_ack=True)

@app.route('/api/v1/db/read', methods = ["POST"])
def readfromDB():
	global response,corr_id
	response = None
	corr_id = str(uuid.uuid4())
	data = request.get_json()
	channel.basic_publish(exchange='',routing_key='readQueue',properties=pika.BasicProperties(reply_to=callback_queue,correlation_id=corr_id), body=json.dumps(data))
	while response is None:
		connection.process_data_events()
	return response

@app.route('/api/v1/db/write', methods = ["POST"])
def writetoDB():
	global response,corr_id
	response = None
	corr_id = str(uuid.uuid4())
	data = request.get_json()
	channel.basic_publish(exchange='',routing_key='writeQueue',properties=pika.BasicProperties(reply_to=callback_queue,correlation_id=corr_id), body=json.dumps(data))
	while response is None:
		connection.process_data_events()
	return response



@app.route('/api/v1/db/clear', methods = ["POST"])
def clearDB():
	global response,corr_id
	response = None
	corr_id = str(uuid.uuid4())
	data = request.get_json()
	channel.basic_publish(exchange='',routing_key='writeQueue',properties=pika.BasicProperties(reply_to=callback_queue,correlation_id=corr_id), body=json.dumps(data))
	while response is None:
		connection.process_data_events()
	return response


if __name__ == '__main__':
    app.debug = True
    app.run(host = '0.0.0.0', port='80')
