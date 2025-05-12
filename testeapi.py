import json
import os
from datetime import datetime
from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Initialiser Flask
app = Flask(__name__)

# Lire le fichier JSON depuis les variables d'environnement
SERVICE_ACCOUNT_INFO = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
service = build("sheets", "v4", credentials=credentials)

# 🔹 ID du Google Sheet et plages de données
SPREADSHEET_ID = "1ALnHRydpnvafmIj6GZKsakPqhPcQPhiusSBmjp1I0TE"
RANGE_TAB1 = "Feuille 1!A:E"  # Colonnes pour les nouvelles requêtes
RANGE_TAB2 = "Feuille 2!A:H"  # Colonnes pour stocker l'historique et statistiques
RANGE_TAB3 = "Feuille 3!A:B"  # A = Appareil, B = Utilisateurs associés

# 📌 FORMATER LA DATE EN "JJ-MM-AA HH:MM:SS"
def get_formatted_datetime():
    return datetime.now().strftime("%d-%m-%y %H:%M:%S")

# 📌 FORMATER SEULEMENT L'HEURE "HH:MM:SS"
def get_formatted_time():
    return datetime.now().strftime("%H:%M:%S")

# 📌 Fonction pour récupérer les données actuelles de Feuille 2
def get_existing_data():
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_TAB2).execute()
    return result.get("values", [])

# 📌 Fonction pour récupérer les données actuelles de Feuille 3 (Tab3)
def get_existing_tab3():
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_TAB3).execute()
    return result.get("values", [])

# 📌 Route pour écrire des données (POST)
@app.route('/write', methods=['POST'])
def write_data():
    """ Ajoute une nouvelle requête utilisateur dans `Feuille 1`, met à jour `Feuille 2` et `Feuille 3`. """
    data = request.json.get('values', [])

    if not data:
        return jsonify({"error": "Aucune donnée fournie"}), 400

    # Ajout de l'horodatage
    current_date = get_formatted_datetime()

    # ✅ Ajout des nouvelles données à `Feuille 1`
    request_body = {"values": [[*row, current_date] for row in data]}  # Ajoute la date à chaque ligne
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_TAB1,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=request_body
    ).execute()

    # ✅ Mise à jour de `Feuille 2` et `Feuille 3`
    update_tab2(data, current_date)
    update_tab3(data)

    return jsonify({"message": "Données ajoutées et mises à jour avec succès !"})

# 📌 Mise à jour de Feuille 2 avec "Lastdateactiv"
def update_tab2(new_data, current_date):
    """ Met à jour `Feuille 2` en conservant l'ordre existant et en ajoutant les nouveaux utilisateurs en bas. """
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Feuille 2!A:I").execute()
    rows = result.get("values", [])

    tab2_data = {}
    existing_users = set()  # Liste des utilisateurs déjà présents dans la feuille

    for row in rows[1:]:  # Ignorer l'en-tête
        if len(row) >= 9:
            user = row[0].strip()  # Récupérer l'utilisateur (sans espaces)
            if user:
                existing_users.add(user)  # Stocker les utilisateurs déjà existants
                status, req_count, device_count, balance, mode, strategy, dates, last_date = row[1:]
                tab2_data[user] = [status, int(req_count), int(device_count), balance, mode, strategy, dates, last_date]

    new_entries = []  # Liste des nouveaux utilisateurs à ajouter en fin de tableau

    for new_entry in new_data:
        if len(new_entry) < 5:
            continue

        user, balance, mode, strategy = new_entry[0], new_entry[2], new_entry[3], new_entry[4]
        new_date = datetime.strptime(current_date, "%d-%m-%y %H:%M:%S")  # Convertir la date actuelle en datetime
        new_date_str = new_date.strftime("%d-%m-%y")  # Extraire uniquement la partie JJ-MM-AA
        new_time_str = new_date.strftime("%H:%M:%S")  # Extraire uniquement l'heure

        if user in tab2_data:
            # ✅ Mise à jour d'un utilisateur existant
            tab2_data[user][1] += 1  # Incrémenter le nombre de requêtes
            tab2_data[user][3] += f" {balance}"
            tab2_data[user][4] += f" {mode}"
            tab2_data[user][5] += f" {strategy}"

            # Comparer avec Lastdateactiv pour savoir comment ajouter la date dans la colonne "Date"
            last_date_str = tab2_data[user][7]  # Récupérer la dernière date activée (JJ-MM-AA)
            if last_date_str == new_date_str:
                tab2_data[user][6] += f" {new_time_str}"  # Ajouter uniquement l'heure
            else:
                tab2_data[user][6] += f" {current_date}"  # Ajouter la date complète

            # Mettre à jour la colonne "Lastdateactiv"
            tab2_data[user][7] = new_date_str
        else:
            # ✅ Nouvel utilisateur → L'ajouter en fin de tableau sans écraser les lignes existantes
            if user:  # Vérifier que l'utilisateur n'est pas vide
                new_entries.append([user, "Ok", 1, 1, balance, mode, strategy, current_date, new_date_str])

    # ✅ Re-construire le tableau avec en-tête + toutes les lignes à jour
    updated_values = [["Utilisateur", "Statut", "Nombre de requêtes", "Nombre d'appareils", "Balance", "Mode Mise", "Strategy", "Date", "Lastdateactiv"]]

    existing_users = set(tab2_data.keys())
    for row in rows[1:]:
        user = row[0].strip()
        if user in tab2_data:
            updated_values.append([user] + tab2_data.pop(user))  # Ligne mise à jour

    # Ajouter les nouveaux utilisateurs restants
    for user, details in tab2_data.items():
        updated_values.append([user] + details)

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range="Feuille 2!A:I",
        valueInputOption="RAW",
        body={"values": updated_values}
    ).execute()


# 📌 Mise à jour de Feuille 3 (Détection des appareils partagés)
def update_tab3(new_data):
    """ Met à jour `Feuille 3` pour regrouper les utilisateurs par appareil. """
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_TAB3).execute()
    rows = result.get("values", [])

    tab3_data = {}
    for row in rows[1:]:
        if len(row) >= 2:
            appareil, users = row
            tab3_data[appareil] = users.split(", ")

    for new_entry in new_data:
        if len(new_entry) < 2:
            continue

        user, appareil = new_entry[0], new_entry[1]

        if appareil in tab3_data:
            if user not in tab3_data[appareil]:
                tab3_data[appareil].append(user)
        else:
            tab3_data[appareil] = [user]

    updated_values = [["Appareil", "Utilisateurs liés"]] + [[device, ", ".join(users)] for device, users in tab3_data.items()]
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_TAB3,
        valueInputOption="RAW",
        body={"values": updated_values}
    ).execute()

# 📌 Route pour lire les données (GET) dans `Feuille 2!A:B,J`
@app.route('/read', methods=['GET'])
def read_data():
    """ Récupère les colonnes A (Utilisateur), B (Statut) et J (Message) de `Feuille 2`. """
    sheet = service.spreadsheets()
    
    # Récupérer les colonnes A et B
    result1 = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Feuille 2!A:B").execute()
    values1 = result1.get("values", [])

    # Récupérer la colonne J (Message)
    result2 = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Feuille 2!J:J").execute()
    values2 = result2.get("values", [])

    # Fusionner les données (ajouter la colonne J aux résultats A et B)
    combined_data = []
    for i in range(len(values1)):  
        row = values1[i]  # Récupérer Utilisateur et Statut (A et B)
        message = values2[i][0] if i < len(values2) and len(values2[i]) > 0 else ""  # Récupérer Message (J)
        row.append(message)  # Ajouter le message dans la ligne
        combined_data.append(row)  # Ajouter la ligne complète

    return jsonify(combined_data)

# 📌 Route pour réinitialiser `Feuille 1` sans toucher `Feuille 2` et `Feuille 3`
@app.route('/reset', methods=['POST'])
def reset_database():
    service.spreadsheets().values().clear(spreadsheetId=SPREADSHEET_ID, range=RANGE_TAB1).execute()
    return jsonify({"message": "Feuille 1 réinitialisée avec succès !"})

# 📌 Route pour récupérer `Feuille 3`
@app.route('/read-tab3', methods=['GET'])
def read_tab3():
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_TAB3).execute()
    return jsonify(result.get("values", []))

# 📌 Charger les données de Feuille 4
def get_keys_data_tab4():
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Feuille 4!A:H"  # 🆗 inclut la colonne Message
    ).execute()
    return result.get("values", [])

# 📌 Charger les données de Feuille 5
def get_users_data_tab5():
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Feuille 5!A:E"  # Plage correspondant à Feuille 5
    ).execute()
    return result.get("values", [])

# 📌 Mise à jour ou ajout de l'utilisateur dans Feuille 5
def update_or_add_user_in_tab5(user_id, key, statut, custom_msg):
    user_rows = get_users_data_tab5()
    header = user_rows[0] if user_rows else ["Utilisateur", "Clé", "Compteur", "Statut", "Message personnalisé"]
    user_data = user_rows[1:] if len(user_rows) > 1 else []

    # Chercher si l'utilisateur existe déjà
    found_user = False
    for idx, urow in enumerate(user_data):
        urow += [""] * (5 - len(urow))  # Remplir les données manquantes
        u_name, u_keys, u_count, u_status, u_msg = urow

        # Si l'utilisateur est trouvé dans la Feuille 5
        if u_name.strip() == user_id:
            found_user = True
            # Vérifier le statut de l'utilisateur
            if "bloqué" in u_status.lower():
                return False, u_msg if u_msg else "Utilisateur bloqué."

            u_count = int(u_count) if u_count.isdigit() else 0  # S'assurer que c'est bien un entier
            u_keys = u_keys.split() if u_keys else []  # Convertir les clés concaténées en liste
            if key not in u_keys:
                u_keys.append(key)  # Ajouter la nouvelle clé
            u_keys = " ".join(u_keys)  # Re-joindre les clés

            # Incrémenter le compteur des requêtes
            u_count += 1

            # Mettre à jour le statut si nécessaire
            if statut == "❌️ Bloquée":
                u_status = "❌️ Bloquée"
                u_msg = custom_msg  # Message personnalisé si bloqué
            else:
                u_status = "✅️ Active"

            # Mise à jour de la ligne dans le tableau
            user_data[idx] = [u_name, u_keys, str(u_count), u_status, u_msg]
            break
    else:
        # Si l'utilisateur n'existe pas encore dans la feuille, on l'ajoute
        user_data.append([user_id, key, "1", "✅️ Active", custom_msg])

    # Remettre les données mises à jour dans Feuille 5
    values_to_write = [header] + user_data
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range="Feuille 5!A:E",  # Plage correspondant à Feuille 5
        valueInputOption="RAW",
        body={"values": values_to_write}
    ).execute()
    return True, None  # Retourne True si l'utilisateur est actif, None pour le message

# 📌 Route de validation de clé
@app.route('/validate-key', methods=['POST'])
def validate_key():
    payload = request.json
    key = payload.get("key")
    user_id = payload.get("userId")

    if not key or not user_id:
        return jsonify({
            "valid": False,
            "message": "⛔ Clé ou utilisateur manquant."
        }), 400

    now = datetime.now()
    now_full = now.strftime("%d-%m-%y %H:%M:%S")
    now_date = now.strftime("%d-%m-%y")

    rows = get_keys_data_tab4()
    header = rows[0] if rows else ["Clé", "Compteur", "Limite", "Statut", "Utilisateur", "Dernière utilisation", "Historique", "Message"]
    data = rows[1:] if len(rows) > 1 else []

    updated_data = []
    found = False
    updated = False

    for row in data:
        row += [""] * (8 - len(row))  # A:H
        k, compteur, limite, statut, utilisateur, last_used, history, custom_msg = row

        if k == key:
            found = True
            compteur = int(compteur) if compteur.isdigit() else 0
            limite = int(limite) if limite.isdigit() else 0
            statut = statut.strip()
            custom_msg = custom_msg.strip() if custom_msg else ""

            # ❌ Si la clé est bloquée manuellement
            if "bloquée" in statut.lower():
                return jsonify({
                    "valid": False,
                    "message": custom_msg or "🚫 Clé bloquée par l'administrateur."
                })

            # ❌ Si la limite est atteinte
            if compteur >= limite:
                statut = "❌️ Bloquée"
                updated_data.append([k, str(compteur), str(limite), statut, utilisateur, last_used, history, custom_msg])
                updated = True
                break

            # 👤 Mise à jour utilisateur
            if utilisateur.strip() == "":
                utilisateur = user_id
            elif user_id not in utilisateur.split():
                utilisateur += f" {user_id}"

            # 🧮 Mise à jour compteur
            compteur += 1

            # 🕓 Historique
            if last_used == now_date:
                history += f" {now_full.split()[1]}"
            else:
                history += f" {now_full}"
            last_used = now_date

            # ✅ Ne pas modifier le statut ici (on respecte l’état manuel)
            updated_data.append([
                k,
                str(compteur),
                str(limite),
                statut,
                utilisateur.strip(),
                last_used,
                history.strip(),
                custom_msg
            ])
            updated = True
        else:
            updated_data.append(row)

    if not found:
        return jsonify({
            "valid": False,
            "message": "❌ Clé inconnue ou introuvable."
        }), 404

    if updated:
        # Mise à jour de Feuille 4
        values_to_write = [header] + updated_data
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="Feuille 4!A:H",
            valueInputOption="RAW",
            body={"values": values_to_write}
        ).execute()

        # Vérification et mise à jour dans Feuille 5
        valid, message = update_or_add_user_in_tab5(user_id, key, statut, custom_msg)
        if not valid:
            return jsonify({
                "valid": False,
                "message": message
            })
        
        return jsonify({"valid": True})

    return jsonify({
        "valid": False,
        "message": "⛔ Erreur inconnue lors de la mise à jour."
    })

# 📌 Lancer l'application Flask
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
