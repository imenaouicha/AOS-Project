# 💰 Payment Service - Plateforme deCovoiturage
## 📡 Informations de connexion

| Information | Valeur |
|-------------|--------|
| **IP** | `192.168.1.36` |
| **Port** | `8000` |
| **Base URL** | `http://192.168.1.36:8000/api/payments/` |

## 📋 Endpoints API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health/` | Health check |
| GET | `/wallet/` | Voir portefeuille |
| POST | `/wallet/add-balance/` | Recharger (`{"amount": 5000}`) |
| POST | `/create/` | Créer paiement |
| POST | `/confirm/` | Confirmer paiement |
| GET | `/transactions/` | Historique |
| GET | `/transactions/{id}/receipt/` | Télécharger reçu PDF |
| POST | `/refund/cancel/` | Annuler et rembourser |
| GET | `/refund/rules/` | Voir règles remboursement |

## 🎯 Méthodes de paiement

| Code | Moyen |
|------|-------|
| `cash` | Espèces |
| `cib` | Carte bancaire |
| `edahabia` | Edahabia |
| `ccp` | CCP |
| `wallet` | Portefeuille |

## 📊 Règles de remboursement

| Délai | Remboursement |
|-------|---------------|
| +48h | 100% |
| 24-48h | 50% |
| -24h | 0% |
| Conducteur annule | 100% |

## 🚀 Test rapide

```bash
curl http://192.168.1.36:8000/api/payments/health/
