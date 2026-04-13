# 💰 Payment Service

Service de paiement pour la plateforme de covoiturage.

## 🚀 Installation rapide

```bash
git clone https://github.com/imane-gg/payment-service.git
cd payment-service
cp .env.example .env
# Modifier .env avec vos informations
docker-compose up -d --build

## 🔗 Endpoints API

Base URL: `http://localhost:8000/api/payments/`

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health/` | Health check |
| GET | `/wallet/` | Voir portefeuille |
| POST | `/wallet/add-balance/` | Recharger (`{"amount": 5000}`) |
| POST | `/create/` | Créer paiement |
| POST | `/confirm/` | Confirmer paiement |
| GET | `/transactions/` | Historique |