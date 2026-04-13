# payment_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home(request):
    return HttpResponse("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Service - API Documentation</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
            }
            .header p {
                font-size: 1.1rem;
                opacity: 0.9;
            }
            .card {
                background: white;
                border-radius: 15px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .card h2 {
                color: #667eea;
                margin-bottom: 20px;
                border-bottom: 2px solid #eee;
                padding-bottom: 10px;
            }
            .status {
                display: flex;
                align-items: center;
                gap: 10px;
                background: #f5f5f5;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .status-led {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background-color: #4CAF50;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            .endpoint-table {
                width: 100%;
                border-collapse: collapse;
            }
            .endpoint-table th {
                background: #667eea;
                color: white;
                padding: 12px;
                text-align: left;
            }
            .endpoint-table td {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            .method {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 5px;
                font-size: 0.8rem;
                font-weight: bold;
                color: white;
            }
            .method-get { background: #4CAF50; }
            .method-post { background: #FF9800; }
            .method-put { background: #2196F3; }
            .method-delete { background: #f44336; }
            .url {
                font-family: monospace;
                font-size: 0.9rem;
            }
            .badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.7rem;
                font-weight: bold;
            }
            .badge-success { background: #d4edda; color: #155724; }
            .badge-info { background: #d1ecf1; color: #0c5460; }
            .footer {
                text-align: center;
                color: white;
                margin-top: 30px;
                font-size: 0.8rem;
                opacity: 0.8;
            }
            .info-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }
            .info-item {
                background: #f8f9fa;
                padding: 10px;
                border-radius: 8px;
                text-align: center;
            }
            .info-item strong {
                color: #667eea;
            }
            a {
                color: #667eea;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💰 Payment Service</h1>
                <p>Plateforme de Covoiturage Intelligent - Transport Inter-Villes en Algérie</p>
            </div>

            <div class="card">
                <div class="status">
                    <div class="status-led"></div>
                    <span><strong>Statut:</strong> Opérationnel</span>
                    <span style="margin-left: 20px;"><strong>Version:</strong> 1.0.0</span>
                    <span style="margin-left: 20px;"><strong>IP:</strong> 172.29.128.1</span>
                    <span style="margin-left: 20px;"><strong>Port:</strong> 8000</span>
                </div>

                <div class="info-grid">
                    <div class="info-item"><strong>💰 Portefeuilles</strong><br>Gérés</div>
                    <div class="info-item"><strong>💳 Transactions</strong><br>Traçables</div>
                    <div class="info-item"><strong>📄 Reçus PDF</strong><br>Générés</div>
                    <div class="info-item"><strong>🔄 Remboursements</strong><br>Automatiques</div>
                </div>
            </div>

            <div class="card">
                <h2>📋 Endpoints disponibles</h2>
                <table class="endpoint-table">
                    <thead>
                        <tr><th>Méthode</th><th>Endpoint</th><th>Description</th><th>Body (POST)</th></tr>
                    </thead>
                    <tbody>
                        <tr><td><span class="method method-get">GET</span></td><td class="url">/api/payments/health/</td><td>Vérifier l'état du service</td><td>-</td></tr>
                        <tr><td><span class="method method-get">GET</span></td><td class="url">/api/payments/wallet/</td><td>Consulter le portefeuille</td><td>-</td></tr>
                        <tr><td><span class="method method-post">POST</span></td><td class="url">/api/payments/wallet/add-balance/</td><td>Recharger le portefeuille</td><td><code>{"amount": 5000}</code></td></tr>
                        <tr><td><span class="method method-post">POST</span></td><td class="url">/api/payments/create/</td><td>Créer un paiement</td><td><code>{"booking_id": "uuid", "amount": 1500, "payment_method": "cash"}</code></td></tr>
                        <tr><td><span class="method method-post">POST</span></td><td class="url">/api/payments/confirm/</td><td>Confirmer un paiement</td><td><code>{"transaction_id": "uuid"}</code></td></tr>
                        <tr><td><span class="method method-get">GET</span></td><td class="url">/api/payments/transactions/</td><td>Historique des transactions</td><td>-</td></tr>
                        <tr><td><span class="method method-get">GET</span></td><td class="url">/api/payments/transactions/{id}/</td><td>Détails d'une transaction</td><td>-</td></tr>
                        <tr><td><span class="method method-get">GET</span></td><td class="url">/api/payments/transactions/{id}/receipt/</td><td>Télécharger le reçu PDF</td><td>-</td></tr>
                        <tr><td><span class="method method-post">POST</span></td><td class="url">/api/payments/transactions/{id}/refund/</td><td>Demander un remboursement</td><td><code>{"reason": "Annulation"}</code></td></tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>🎯 Méthodes de paiement</h2>
                <table class="endpoint-table">
                    <thead><tr><th>Code</th><th>Moyen</th></tr></thead>
                    <tbody>
                        <tr><td><span class="badge badge-info">cash</span></td><td>💰 Espèces (paiement au chauffeur)</td></tr>
                        <tr><td><span class="badge badge-info">cib</span></td><td>💳 Carte bancaire</td></tr>
                        <tr><td><span class="badge badge-info">edahabia</span></td><td>🏦 Edahabia</td></tr>
                        <tr><td><span class="badge badge-info">ccp</span></td><td>📮 CCP</td></tr>
                        <tr><td><span class="badge badge-info">wallet</span></td><td>👛 Portefeuille virtuel</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>📊 Statuts des transactions</h2>
                <table class="endpoint-table">
                    <thead><tr><th>Statut</th><th>Signification</th></tr></thead>
                    <tbody>
                        <tr><td><span class="badge badge-info">pending</span></td><td>⏳ En attente de confirmation</td></tr>
                        <tr><td><span class="badge badge-info">processing</span></td><td>🔄 En cours de traitement</td></tr>
                        <tr><td><span class="badge badge-success">completed</span></td><td>✅ Paiement confirmé</td></tr>
                        <tr><td><span class="badge badge-info">failed</span></td><td>❌ Échec du paiement</td></tr>
                        <tr><td><span class="badge badge-info">refunded</span></td><td>🔁 Remboursé</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>🔧 Administration</h2>
                <p>Accéder à l'interface d'administration : <a href="/admin/">http://172.29.128.1:8000/admin/</a></p>
                <p style="margin-top: 15px; font-size: 0.9rem; color: #666;">
                    <strong>Base URL:</strong> http://172.29.128.1:8000/api/payments/
                </p>
            </div>

            <div class="footer">
                <p>Payment Service - Projet WAMS 2025 | Transport Inter-Villes en Algérie</p>
            </div>
        </div>
    </body>
    </html>
    """)

urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    path('api/payments/', include('payments.urls')),
]