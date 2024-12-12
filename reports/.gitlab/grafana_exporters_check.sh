if which docker-compose; then
  if docker-compose --version | grep "Docker Compose version"; then
    echo "docker-compose existing"
  else
    apt update
    apt install docker-compose -y
  fi
else
  apt update
  apt install docker-compose -y
fi

# before that you need to put files docker-compose.exporters.yml and Caddyfile in the directory /home/cicd

if [ "$( docker container inspect -f '{{.State.Status}}' nodeexporter )" == "running" ] && [ "$( docker container inspect -f '{{.State.Status}}' cadvisor )" == "running" ] && [ "$( docker container inspect -f '{{.State.Status}}' caddy )" == "running" ] ; then
          echo "nodeexporter, cadvisor and caddy are running"
        else 

          if [ "$( docker container inspect -f '{{.State.Status}}' nodeexporter )" == "running" ]; then
            echo "nodeexporter is running"
          else
            docker stop nodeexporter || true
            docker rm nodeexporter || true
          fi

          if [ "$( docker container inspect -f '{{.State.Status}}' cadvisor )" == "running" ]; then
            echo "cadvisor is running"
          else
            docker stop cadvisor || true
            docker rm cadvisor || true
          fi

          if [ "$( docker container inspect -f '{{.State.Status}}' caddy )" == "running" ]; then
            echo "caddy is running"
          else
            docker stop caddy || true
            docker rm caddy || true
          fi          

          rm -rf dockprom
          git clone https://github.com/stefanprodan/dockprom
          cp -f ./docker-compose.exporters.yml ./dockprom/docker-compose.exporters.yml 
          cp -f ./Caddyfile ./dockprom/caddy/Caddyfile 
          cd dockprom
          docker-compose -f docker-compose.exporters.yml up -d
          rm -rf docker-compose.exporters.yml
fi