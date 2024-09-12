import requests
import json
import os

# Leer data.json para obtener el array de circuits
with open('data.json', 'r') as data_file:
    data = json.load(data_file)
circuits = data['circuits']
print(circuits)

# Función para obtener la clasificación de una sesión
def get_session_classification(session_id):
    url = f"https://api.motogp.pulselive.com/motogp/v1/results/session/{session_id}/classification?test=false"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to retrieve data for session {session_id}: {response.status_code}")
        return None

# Procesar cada circuito y sus sesiones
for circuit in circuits:
    circuit_name = circuit['name'].replace(' ', '_').replace('/', '_')
    results = []

    if 'sessions' not in circuit:
        print(f"No sessions found for circuit {circuit['name']}")
        continue

    for session in circuit['sessions']:
        if session['type'] in ['SPR', 'RAC']:
            session_id = session['id']
            classification = get_session_classification(session_id)
            if classification:
                top_3_riders = [
                    {
                        'position': rider['position'],
                        'full_name': rider['rider']['full_name'],
                        'team': rider['team']['name'],
                        'constructor': rider['constructor']['name']
                    }
                    for rider in classification['classification'] if rider['position'] in [1, 2, 3]
                ]
                results.append({
                    'session_id': session_id,
                    'session_type': session['type'],
                    'top_3_riders': top_3_riders
                })

    # Guardar los resultados en un archivo JSON
    results_file = f"results/results_{circuit_name}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=4)

    print(f"Resultados guardados en {results_file}")

print("Proceso completado.")
