                  
        which docker 
        if [ $? -eq 0 ]; then
          docker --version | grep "Docker version" 
          if [ $? -eq 0 ]; then
            echo "docker existing"
          else
            apt update
            apt install docker.io -y
          fi
        else
          apt update
          apt install docker.io -y
        fi

        if [ ! "$(docker network ls | grep nginx-proxy)" ]; then
          echo "Creating nginx-proxy network ..."
          docker network create nginx-proxy
        else
          echo "nginx-proxy network exists."
        fi

        if [ "$( docker container inspect -f '{{.State.Status}}' nginx-proxy )" == "running" ]; then
          echo "nginx-proxy is running"
        else
          mkdir -p /home/cicd/proxy\
          rm -rf /home/cicd/proxy/my_proxy.conf
          echo 'underscores_in_headers on; proxy_connect_timeout 600; proxy_send_timeout 600; proxy_read_timeout 600; send_timeout 600; fastcgi_read_timeout 300;' > /home/cicd/proxy/my_proxy.conf
          docker stop nginx-proxy || true
          docker rm nginx-proxy || true
          docker run --detach \
            --name nginx-proxy \
            --restart=always \
            --publish 80:80 \
            --publish 443:443 \
            --volume certs:/etc/nginx/certs \
            --volume vhost:/etc/nginx/vhost.d \
            -v /home/cicd/proxy/my_proxy.conf:/etc/nginx/conf.d/my_proxy.conf:ro \
            --volume html:/usr/share/nginx/html \
            --volume /var/run/docker.sock:/tmp/docker.sock:ro \
            --network=nginx-proxy \
            nginxproxy/nginx-proxy
        fi

        if [ "$( docker container inspect -f '{{.State.Status}}' nginx-proxy-acme )" == "running" ]; then
          echo "nginx-proxy-acme is running"
        else
          docker stop nginx-proxy-acme || true
          docker rm nginx-proxy-acme || true
          docker run --detach \
            --name nginx-proxy-acme \
            --restart=always \
            --volumes-from nginx-proxy \
            --volume /var/run/docker.sock:/var/run/docker.sock:ro \
            --volume acme:/etc/acme.sh \
            --env "DEFAULT_EMAIL=lepesevss@fanz.ee" \
            --network=nginx-proxy \
            nginxproxy/acme-companion
        fi
