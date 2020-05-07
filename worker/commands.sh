sudo service apache2 stop
sudo docker system prune --volumes
sudo docker rm -f $(sudo docker ps -a -q)
sudo docker-compose build
# gedit docker-compose.yml
sudo docker-compose up

