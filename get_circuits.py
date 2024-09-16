import requests
import json
import time
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

def get_coordinates(circuit_name):
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
        api_key = config['GOOGLE_MAPS_API_KEY']
    url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={circuit_name}&inputtype=textquery&fields=geometry&key={api_key}"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if 'candidates' in data and data['candidates']:
            location = data['candidates'][0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            print(f"No coordinates found for {circuit_name}")
            return None, None
    else:
        print(f"Failed to retrieve coordinates: {response.status_code}")
        return None, None

def get_timezone(circuit_name):
    lat, lon = get_coordinates(circuit_name)
    if lat is None or lon is None:
        return None
    
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
        api_key = config['TIMEZONE_API_KEY']
    url = f"http://api.timezonedb.com/v2.1/get-time-zone?key={api_key}&format=json&by=position&lat={lat}&lng={lon}"
    time.sleep(1.5) # Freeze for 1.5 second to avoid rate limiting of free accounts
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['zoneName']
    else:
        print(f"Failed to retrieve timezone data: {response.status_code}")
        return None

def get_circuits(season_id):
    url = f"https://api.motogp.pulselive.com/motogp/v1/results/events?seasonUuid={season_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        circuits = []
        
        for event in data:
            timezone = get_timezone(event.get('circuit')['name'])
            
            circuit_info = {
                'id': event.get('id'),
                'date_start': event.get('date_start').split('T')[0],  # Extract date part only
                'name': event.get('circuit')['name'],
                'timezone': timezone
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

def main():
    season_id = get_season_id()
    if season_id:
        circuits = get_circuits(season_id)
        update_data_json(circuits)
        print("Data updated successfully.")
    else:
        print("Season ID not found.")

if __name__ == "__main__":
    season_id = get_season_id()
    if season_id:
        circuits = get_circuits(season_id)
        update_data_json(circuits)
        for circuit in circuits:
            print(f"ID: {circuit['id']}, Name: {circuit['name']}, Date Start: {circuit['date_start']}, Timezone: {circuit['timezone']}")
