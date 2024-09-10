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

def get_riders(season_id):
    url = f"https://api.motogp.pulselive.com/motogp/v1/results/standings?seasonUuid={season_id}&categoryUuid=e8c110ad-64aa-4e8e-8a86-f2f152f6a942"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        riders = []
        
        for classification in data.get('classification', []):
            rider_info = {
                'id': classification['rider'].get('id'),
                'full_name': classification['rider'].get('full_name')
            }
            riders.append(rider_info)
        
        return riders
    else:
        print(f"Failed to retrieve data: {response.status_code}")
        return []

def update_data_json(riders):
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        data = {}

    data['rider'] = riders

    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    season_id = get_season_id()
    if season_id:
        riders = get_riders(season_id)
        update_data_json(riders)
        for rider in riders:
            print(f"ID: {rider['id']}, Full Name: {rider['full_name']}")
