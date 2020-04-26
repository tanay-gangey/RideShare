import docker
import sys
import json, requests, collections
from datetime import datetime
from flask import Flask, request, jsonify
import pika

app = Flask(__name__)
client = docker.from_env()
c = docker.APIClient()

#add self parameter and add this function to the class and change the counter and timer variables
# i'm assuming the container parameter for this fn refers to the list of slave containers, it's a list of container objects 
#havent called this function anywhere btw, where would you call this?
def spawncheck(count,containers):
	mul_20 = count%20 
	mul_20+=1 #this is how many slaves we should have
	num_slaves = len(containers) #this is how many slaves we actually have 
	if(num_slaves>mul_20):#if there are more slaves than needed 
		while((num_slaves-mul20)!=0):#while the number we have is not equal to the number needed
			container[num_slaves-1].stop() #stop the last slave
			num_slaves-=1 #reduce number of slaves
	elif num_slaves<mul_20:
		while((mul20-num_slaves)!=0):#while the number we have is equal to the number needed
			#c.create_container() #https://docker-py.readthedocs.io/en/stable/api.html #not quite sure how this function works so i've attached the documentation
			container.run("slave image", detach = True)			
			#this might be useful while creating container according to my friend https://stackoverflow.com/questions/35110146/can-anyone-explain-docker-sock (they were accidently creating container
			#inside container so this show how to connect to correct socket
			num_slaves+=1 #increase num_slaves count

#im assuming that the container id comes in the data of the post request, i've added sample-getcontainerpid.py for reference if this is not the case
@app.route('/api/v1/crash/master', methods = ["POST"])
def killMaster():
	if request.method == "POST":
		container = request.get_json()["container"]
		container.kill()
		return 200
	return 405


#im assuming we get a list of containers,  i've added sample-getcontainerpid.py for reference if this is not the case, to get the list of just slave containers we'll need zookeeper idk how to do that
@app.route('/api/v1/crash/slave', methods = ["POST"])
def killSlave():
	if request.method == "POST":
		containers = request.get_json()["containers"]
		cntrdict = dict() #dictionary of containers and the pids, cause we have to kill slave with highest pid		
		for cntr in containers:
			ctrdict[cntr.id] = cntr.top()['Processes'][0][1] #cntr.id[:10] is the first 10 characters of the container id that are show when you do docker ps -a
		maxcid =list(cntrdict.keys())[list(cntrdict.values()).index(max(list(cntrdict.values())))] #gets the key of the max value. i.e. gets the container id of the highest pid container
		for cntr in containers:#iterate over list of containers
			if(cntr.id == maxcid):#if container id matches container id of container with max pid
				cntr.kill() #then kill that container
				break;
		return 200
	return 405

@app.route('/api/v1/worker/list', methods = ["GET"])
def getWorkers():
	if request.method == "GET":
		clist = c.containers() #list of containers
		pidlist = list()#list of pids
		for cntr in clist:
			pidlist.append(cntr.top()['Processes'][0][1])#getting all the pids
		pidlist.sort()#sorting the pids
		return jsonify(pidlist), 200
	return 405

