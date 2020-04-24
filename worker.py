import sys
import json, requests, collections
from datetime import datetime
from flask import Flask, request, jsonify
import pika
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))

channel = connection.channel()

channel.queue_declare(queue='readQueue')
channel.queue_declare(queue='writeQueue')

def do_some_db_op(data):
    print(json.loads(data))

def on_read_request(ch, method, props, body):
    data = body

    response = do_some_db_op(data)

    ch.basic_publish(exchange='',routing_key=props.reply_to, properties=pika.BasicProperties(correlation_id = props.correlation_id),body=str(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
#slave does this
channel.basic_consume(queue='readQueue', on_message_callback=on_read_request)
#master does this i think
#channel.basic_consume(queue='writeQueue', on_message_callback=on_writereq)


print(" [x] Awaiting RPC requests")
channel.start_consuming()
