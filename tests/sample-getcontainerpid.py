import docker
import sys
import json, requests, collections
from datetime import datetime
from flask import Flask, request, jsonify
import pika

app = Flask(__name__)
client = docker.from_env()

def spawncheck(container):
	print(type(container))
	print(str(container))
	print(container.top()['Processes'][0][1])

container = client.containers.run('rabbitmq', detach=True, remove=True) #start a container
c = docker.APIClient()
print(c.containers()) #list of containers
#spawncheck(container) this also works
spawncheck(c[0])
container.stop()
#client.containers.list()
