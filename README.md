# api-v2

## restart gunicorn
systemctl restart api-v2

doctl registry login
docker build -t registry.digitalocean.com/notello/api-dev:v1.xx .
docker push registry.digitalocean.com/notello/api-dev:v1.xx
kubectl edit deployment flask-restx-api-deployment
helm upgrade --install traefik traefik/traefik --namespace traefik --values traefik-helm-values.yaml
kubectl scale deployment flask-restx-api-deployment --replicas=0