import json
import requests
import os
from datetime import datetime
import pytz

# Función para obtener el circuito más próximo por fecha de inicio
def get_next_circuit(data):
    current_date = datetime.now(pytz.utc).date()
    circuits = data['circuits']
    circuits.sort(key=lambda x: datetime.strptime(x["date_start"], "%Y-%m-%d").date())
    for circuit in circuits:
        circuit_date = datetime.strptime(circuit["date_start"], "%Y-%m-%d").date()
        if circuit_date > current_date:
            return circuit
    return None

# Función para obtener las sesiones filtradas
def get_filtered_sessions(circuit_id, motogp_id):
    url = f"https://api.motogp.pulselive.com/motogp/v1/results/sessions?eventUuid={circuit_id}&categoryUuid={motogp_id}"
    response = requests.get(url)
    if response.status_code == 200:
        sessions = response.json()
        filtered_sessions = [
            {"date": session["date"], "id": session["id"]}
            for session in sessions
            if session["type"] == "Q" and session["number"] == 2
        ]
        return filtered_sessions
    else:
        print(f"Error al obtener las sesiones: {response.status_code}")
        return []

# Función para obtener la clasificación de una sesión
def get_classification(session_id):
    url = f"https://api.motogp.pulselive.com/motogp/v1/results/session/{session_id}/classification?test=false"
    response = requests.get(url)
    if response.status_code == 200:
        classification_data = response.json()
        filtered_classification = [
            {
                "position": entry["position"],
                "full_name": entry["rider"]["full_name"],
                "best_lap_time": entry["best_lap"]["time"]
            }
            for entry in classification_data["classification"]
        ]
        return filtered_classification
    else:
        print(f"Error al obtener la clasificación para la sesión {session_id}: {response.status_code}")
        return []

# Función principal
def main():
    # Leer los datos desde el archivo data.json
    with open('data.json', 'r') as file:
        data = json.load(file)

    # Obtener el circuito más próximo por fecha de inicio
    next_circuit = get_next_circuit(data)
    if not next_circuit:
        print("No se encontró un circuito próximo.")
        return

    circuit_id = next_circuit['id']
    circuit_name = next_circuit['name'].replace(' ', '_').replace('/', '_')  # Formatear el nombre del circuito

    # Leer config.json para obtener MOTOGP_ID
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    MOTOGP_ID = config['MOTOGP_ID']

    # Obtener las sesiones filtradas
    filtered_sessions = get_filtered_sessions(circuit_id, MOTOGP_ID)

    if not filtered_sessions:
        print("No se encontraron sesiones filtradas.")
        return

    # Ordenar las sesiones por fecha y obtener la más próxima a la fecha actual
    current_date = datetime.now(pytz.utc).date()
    filtered_sessions.sort(key=lambda x: abs(datetime.strptime(x["date"], "%Y-%m-%dT%H:%M:%S%z").date() - current_date))
    next_session = filtered_sessions[0]

    # Obtener la clasificación de la sesión más próxima
    classification = get_classification(next_session["id"])

    # Crear el directorio si no existe
    os.makedirs('grid', exist_ok=True)

    # Datos combinados para guardar en el archivo
    combined_data = {
        "session": next_session,
        "classifications": classification
    }

    # Nombre del archivo de salida
    output_file = f'grid/grid_{circuit_name}.json'
    # Guardar los datos combinados en un archivo JSON
    with open(output_file, 'w') as f:
        json.dump(combined_data, f, indent=4)
    print(f"Datos combinados guardados en {output_file}")

if __name__ == '__main__':
    main()
