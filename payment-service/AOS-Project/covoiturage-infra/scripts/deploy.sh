#!/bin/bash
echo "🚀 Deploying Frontend..."

cd ../covoiturage-frontend

# Build Docker image
docker build -t covoiturage-frontend .

# Stop and remove existing container
docker stop covoiturage-frontend 2>/dev/null || true
docker rm covoiturage-frontend 2>/dev/null || true

# Run new container
docker run -d \
  --name covoiturage-frontend \
  --network covoiturage-infra_covoiturage-net \
  -p 8000:8000 \
  -e DB_HOST=postgres \
  -e DB_PASSWORD=password \
  -e RABBITMQ_HOST=rabbitmq \
  -e CONSUL_HOST=consul \
  covoiturage-frontend

echo "✅ Frontend deployed on port 8000"