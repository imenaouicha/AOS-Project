#!/bin/bash
echo "🚀 Starting Covoiturage Infrastructure..."

docker-compose up -d

echo ""
echo "✅ Services démarrés:"
docker-compose ps

echo ""
echo "🌐 Accès:"
echo "  - Consul UI: http://localhost:8500"
echo "  - RabbitMQ: http://localhost:15672 (guest/guest)"
echo "  - PostgreSQL: localhost:5432"