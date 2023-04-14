docker stack rm bins
sleep 10
docker stack deploy -c docker-compose-stack.yaml bins