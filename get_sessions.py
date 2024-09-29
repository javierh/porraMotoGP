import requests
import json

# Leer config.json para obtener MOTOGP_ID
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
MOTOGP_ID = config['MOTOGP_ID']

# Leer data.json para obtener el array de circuits
with open('data.json', 'r') as data_file:
    data = json.load(data_file)
circuits = data['circuits']

# Función para obtener información adicional del endpoint
def get_additional_info(event_id, category_id):
    url = f"https://api.motogp.pulselive.com/motogp/v1/results/sessions?eventUuid={event_id}&categoryUuid={category_id}"
    print(url)
    response = requests.get(url)
    if response.status_code == 200:
        try:
            return response.json()
        except json.JSONDecodeError:
            print(f"Failed to decode JSON response for event {event_id}")
            return None
    else:
        print(f"Failed to retrieve data for event {event_id}: {response.status_code}")
        return None

# Añadir información adicional a cada circuito
for circuit in circuits:
    event_id = circuit['id']
    additional_info = get_additional_info(event_id, MOTOGP_ID)
    if additional_info:
        filtered_sessions = [
            {'id': session['id'], 'type': session['type']}
            for session in additional_info
            if session['type'] in ['RAC', 'SPR']
        ]
        circuit['sessions'] = filtered_sessions

# Guardar el archivo data.json con la información actualizada
with open('data.json', 'w') as data_file:
    json.dump(data, data_file, indent=4)

print("Información adicional añadida a los circuitos en data.json")
