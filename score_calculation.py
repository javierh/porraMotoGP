import json
import os
from datetime import datetime

# Leer data.json para obtener el array de circuits
with open('data.json', 'r') as data_file:
    data = json.load(data_file)
circuits = data['circuits']

# Función para obtener el circuito más próximo a la fecha actual
def get_next_circuit(circuits):
    today = datetime.now()
    next_circuit = min(
        (circuit for circuit in circuits if datetime.strptime(circuit['date_start'], '%Y-%m-%d') >= today),
        key=lambda x: datetime.strptime(x['date_start'], '%Y-%m-%d') - today
    )
    return next_circuit

# Puntos por posición
points_sprint = {1: 12, 2: 9, 3: 7}
points_race = {1: 25, 2: 20, 3: 16}

# Leer predicciones de los participantes
def read_predictions(file_name):
    try:
        with open(file_name, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Leer resultados de las posiciones
def read_results(file_name):
    try:
        with open(file_name, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Calcular puntos para cada participante
def calculate_points(predictions, classification, points):
    points_by_user = {}
    for prediction in predictions:
        user_id = prediction['user_id']
        user_name = prediction.get('username', 'Unknown')  # Manejo de errores para username
        user_points = 0
        for pos, rider in enumerate(classification[:3], start=1):
            predicted_riders = prediction['sprint_race'] if points == points_sprint else prediction['race']
            if rider['full_name'] in predicted_riders:
                if predicted_riders.index(rider['full_name']) + 1 == pos:
                    user_points += points[pos] * 2
                else:
                    user_points += points[pos]
        if user_id not in points_by_user:
            points_by_user[user_id] = {'user_name': user_name, 'points': 0}
        points_by_user[user_id]['points'] += user_points
    return points_by_user

# Obtener el circuito más próximo
next_circuit = get_next_circuit(circuits)
circuit_name = next_circuit['name'].replace(' ', '_').replace('/', '_')

# Leer predicciones y resultados
predictions_file = f"porras/porra_{circuit_name}.json"
results_file = f"results/results_{circuit_name}.json"
predictions = read_predictions(predictions_file)
results = read_results(results_file)

# Calcular puntos totales por usuario
total_points_by_user = {}
for session in next_circuit['sessions']:
    if session['type'] in ['SPR', 'RAC']:
        session_type = session['type']
        session_results = next((result['top_3_riders'] for result in results if result['session_type'] == session_type), [])
        points = points_sprint if session_type == 'SPR' else points_race
        session_points = calculate_points(predictions, session_results, points)
        for user_id, user_data in session_points.items():
            if user_id not in total_points_by_user:
                total_points_by_user[user_id] = {'user_name': user_data['user_name'], 'points': 0}
            total_points_by_user[user_id]['points'] += user_data['points']

# Guardar los resultados en un archivo JSON
output_file = "results_puntuaciones.json"
with open(output_file, 'w') as f:
    json.dump(total_points_by_user, f, indent=4)

print(f"Resultados guardados en {output_file}")
