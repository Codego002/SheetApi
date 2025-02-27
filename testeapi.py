from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Initialiser Flask
app = Flask(__name__)

# Chemin vers le fichier JSON du compte de service
SERVICE_ACCOUNT_FILE = "/storage/emulated/0/Documents/Python /mineral-style-452116-r7-e214479af6cc.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build("sheets", "v4", credentials=credentials)

SPREADSHEET_ID = "1ALnHRydpnvafmIj6GZKsakPqhPcQPhiusSBmjp1I0TE"

# Route pour lire les données
@app.route('/read', methods=['GET'])
def read_data():
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="A1:D10").execute()
    return jsonify(result.get("values", []))

# Route pour écrire des données
@app.route('/write', methods=['POST'])
def write_data():
    data = request.json['values']  # Exemple : [["Alice", "alice@email.com"]]
    
    sheet = service.spreadsheets()
    request_body = {"values": data}

    # Ajouter à la première ligne vide (mode append)
    response = sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=request_body
    ).execute()

    return jsonify({"message": "Données ajoutées !", "response": response})

# Route pour modifier des données
@app.route('/update', methods=['PUT'])
def update_data():
    range_to_update = request.json['range']  # Exemple : "B2"
    new_value = request.json['values']  # Exemple : [["Nouveau Nom"]]

    sheet = service.spreadsheets()
    request_body = {"values": new_value}

    # Mettre à jour une cellule précise
    response = sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_to_update,
        valueInputOption="RAW",
        body=request_body
    ).execute()

    return jsonify({"message": "Donnée mise à jour !", "response": response})

# Démarrer le serveur Flask
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)