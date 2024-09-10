import requests
import json

def get_season_id():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            return config.get('SEASON_ID')
    except FileNotFoundError:
        print("config.json file not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

def get_circuits(season_id):
    url = f"https://api.motogp.pulselive.com/motogp/v1/results/events?seasonUuid={season_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        circuits = []
        
        for event in data:
            circuit_info = {
                'id': event.get('id'),
                'date_start': event.get('date_start').split('T')[0],  # Extract date part only
                'name': event.get('name')
            }
            circuits.append(circuit_info)
        
        return circuits
    else:
        print(f"Failed to retrieve data: {response.status_code}")
        return []

def update_data_json(circuits):
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        data = {}

    data['circuits'] = circuits

    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    season_id = get_season_id()
    if season_id:
        circuits = get_circuits(season_id)
        update_data_json(circuits)
        for circuit in circuits:
            print(f"ID: {circuit['id']}, Name: {circuit['name']}, Date Start: {circuit['date_start']}")
