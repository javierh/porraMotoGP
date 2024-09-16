import json
import os
from datetime import datetime, timedelta
import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import pandas as pd
import subprocess

# Cargar configuración
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    TIMEZONE = config['TIMEZONE']

# Token del bot
TOKEN = config['TOKEN']

# Load JSON data
with open('data.json', 'r') as f:
    data = json.load(f)
    pilots = [rider['full_name'] for rider in data['rider'] if rider['full_name']]
    circuits = data['circuits']

# DataFrame para almacenar las predicciones
predictions = pd.DataFrame(columns=['user_id', 'username', 'race', 'prediction'])

# List of admin user IDs
ADMIN_IDS = config['ADMIN_IDS']

# Estados de la conversación
SPRINT_FIRST, SPRINT_SECOND, SPRINT_THIRD, RACE_FIRST, RACE_SECOND, RACE_THIRD = range(6)

# Función de inicio /start
def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    update.message.reply_text(f"Hi, {user.first_name}! Welcome to the MotoGP betting bot.")
    update.message.reply_text("Use /porra to make a prediction.\n Use /help to see the available commands.")

# Función para iniciar la porra
def porra(update: Update, context: CallbackContext) -> int:
    # Seleccionar el circuito más próximo a la fecha actual
    today = datetime.now()
    next_race = min(
        (circuit for circuit in circuits if datetime.strptime(circuit['date_start'].split('T')[0], '%Y-%m-%d') >= today),
        key=lambda x: datetime.strptime(x['date_start'].split('T')[0], '%Y-%m-%d') - today
    )
    context.user_data['race'] = next_race['name']
    race_name = next_race['name']
    file_name = f"porra_{race_name.replace(' ', '_')}.json"
    grid_file_name = f"grid/grid_{race_name.replace(' ', '_')}.json"

    # Leer la hora del evento desde el archivo JSON
    with open(grid_file_name, 'r') as file:
        grid_data = json.load(file)
        event_time_str = grid_data['session']['date']  # Obtener la hora de inicio del primer evento
        event_time = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S%z")

    # Obtener la zona horaria del circuito, usar una predeterminada si no está presente
    circuit_timezone = next_race.get('timezone', TIMEZONE)

    # Convertir la hora del evento a la zona horaria del circuito
    event_time_circuit_tz = event_time.astimezone(pytz.timezone(circuit_timezone))

    # Añadir una hora a la hora del evento
    event_time_plus_one_hour = event_time_circuit_tz + timedelta(hours=1)

    # Obtener la hora actual en la zona horaria especificada en config.json
    current_time = datetime.now(pytz.timezone(TIMEZONE))

    # Comparar las horas
    if current_time > event_time_plus_one_hour:
        update.message.reply_text("You cannot submit the prediction for the current event because the deadline has passed.")
        return ConversationHandler.END

    # Verificar si el usuario ya ha realizado una predicción para este circuito
    try:
        with open(file_name, 'r') as f:
            predictions_data = json.load(f)
            if any(prediction['user_id'] == update.message.from_user.id for prediction in predictions_data):
                update.message.reply_text("You have already made a prediction for the next event.")
                return ConversationHandler.END
    except FileNotFoundError:
        predictions_data = []

    update.message.reply_text(f"The next Sprint Race and Race will take place at: {next_race['name']}")

    # Solicitar los 3 primeros pilotos para la Sprint Race
    keyboard = [[pilot] for pilot in pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Select the pilot who will finish in first position in the Sprint Race:', reply_markup=reply_markup)

    return SPRINT_FIRST

def sprint_first(update: Update, context: CallbackContext) -> int:
    first_pilot = update.message.text
    context.user_data['sprint_first_pilot'] = first_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot != first_pilot]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Select the pilot who will finish in second position in the Sprint Race:', reply_markup=reply_markup)

    return SPRINT_SECOND

def sprint_second(update: Update, context: CallbackContext) -> int:
    second_pilot = update.message.text
    context.user_data['sprint_second_pilot'] = second_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot not in [context.user_data['sprint_first_pilot'], second_pilot]]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Select the pilot who will finish in third position in the Sprint Race:', reply_markup=reply_markup)

    return SPRINT_THIRD

def sprint_third(update: Update, context: CallbackContext) -> int:
    third_pilot = update.message.text
    context.user_data['sprint_third_pilot'] = third_pilot

    # Solicitar los 3 primeros pilotos para la Carrera
    remaining_pilots = pilots[:]  # Resetear la lista de pilotos
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Select the pilot who will finish in first position in the Race', reply_markup=reply_markup)

    return RACE_FIRST

def race_first(update: Update, context: CallbackContext) -> int:
    first_pilot = update.message.text
    context.user_data['race_first_pilot'] = first_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot != first_pilot]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Select the pilot who will finish in second position in the Race:', reply_markup=reply_markup)

    return RACE_SECOND

def race_second(update: Update, context: CallbackContext) -> int:
    second_pilot = update.message.text
    context.user_data['race_second_pilot'] = second_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot not in [context.user_data['race_first_pilot'], second_pilot]]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Select the pilot who will finish in third position in the Race:', reply_markup=reply_markup)

    return RACE_THIRD

def race_third(update: Update, context: CallbackContext) -> int:
    third_pilot = update.message.text
    user = update.message.from_user
    race_name = context.user_data['race']
    prediction = {
        'user_id': user.id,
        'username': user.username,
        'sprint_race': [context.user_data['sprint_first_pilot'], context.user_data['sprint_second_pilot'], context.user_data['sprint_third_pilot']],
        'race': [context.user_data['race_first_pilot'], context.user_data['race_second_pilot'], third_pilot]
    }

    # Guardar la predicción en un archivo JSON
    file_name = f"porras/porra_{race_name.replace(' ', '_')}.json"
    try:
        with open(file_name, 'r') as f:
            predictions_data = json.load(f)
    except FileNotFoundError:
        predictions_data = []

    predictions_data.append(prediction)

    with open(file_name, 'w') as f:
        json.dump(predictions_data, f, indent=4)

    update.message.reply_text(f"Your prediction has been recorded for {race_name}: {prediction}")
    return ConversationHandler.END

def update_results(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    if user.id not in ADMIN_IDS:
        update.message.reply_text("You do not have permission to update the results.")
        return

    # Admin can update results
    update.message.reply_text("Send the race results in the format: Race, Pilot1, Pilot2, Pilot3")

def handle_results_input(update: Update, context: CallbackContext) -> None:
    # Handle results input
    pass

# Función para manejar el comando /help
def help_command(update: Update, context: CallbackContext) -> None:
    help_message = (
        "Welcome to the MotoGP betting system!\n\n"
        "Here are the available commands to interact with the bot:\n"
        "/start - Start interacting with the bot.\n"
        "/porra - Register your bet for the next race.\n"
        "/puntuaciones - Show a list with the name and score data of the participants sorted from highest to lowest by points.\n"
        "/mrgrid - Show the lap times of the riders in the last qualifying session.\n"
        "/help - Show this help message.\n\n"
        "To register your bet, use the /porra command and follow the instructions to enter your predictions for the sprint race and the main race.\n"
        "Remember that modifications to the prediction are not allowed, choose your riders wisely."
        "Good luck!"
    )
    update.message.reply_text(help_message)


def show_scores(update: Update, context: CallbackContext) -> None:
    try:
        with open('results_puntuaciones.json', 'r') as f:
            scores = json.load(f)
    except FileNotFoundError:
        update.message.reply_text("No scores available.")
        return

    # Ordenar los participantes por puntos de mayor a menor
    sorted_scores = sorted(scores.items(), key=lambda x: x[1]['points'], reverse=True)

    # Crear el mensaje con el listado de participantes y sus puntos
    message = "Participants' scores:\n\n"
    for user_id, data in sorted_scores:
        message += f"{data['user_name']}: {data['points']} points\n"

    update.message.reply_text(message)

# Función para manejar el comando /mrgrid
def mrgrid(update: Update, context: CallbackContext) -> None:
    today = datetime.now()
    next_race = min(
        (circuit for circuit in circuits if datetime.strptime(circuit['date_start'].split('T')[0], '%Y-%m-%d') >= today),
        key=lambda x: datetime.strptime(x['date_start'].split('T')[0], '%Y-%m-%d') - today
    )
    circuit_name = next_race['name']  # Obtener el nombre del circuito de los argumentos
    file_path = f"grid/grid_{circuit_name.replace(' ', '_')}.json"

    if not os.path.exists(file_path):
        update.message.reply_text(f"The file for the circuit: {circuit_name} was not found")
        return

    with open(file_path, 'r') as file:
        data = json.load(file)

    if 'classifications' not in data:
        update.message.reply_text(f"No classifications found in the file for the circuit: {circuit_name}")
        return

    message = "Listado de pilotos y sus tiempos:\n"
    for entry in data['classifications']:
        message += f"{entry['position']}: {entry['full_name']} - {entry['best_lap_time']}\n"

    update.message.reply_text(message)

def update_data(update: Update, context: CallbackContext) -> None:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    user_id = config['ADMIN_IDS']
    if user_id not in ADMIN_IDS:
        update.message.reply_text("You do not have permission to execute this command.")
        return
    # Ruta al script bash
    script_path = 'import_data.sh'

    # Ejecutar el script bash
    result = subprocess.run(['bash', script_path], capture_output=True, text=True)

    # Imprimir la salida del script
    print(result.stdout)

    # Imprimir cualquier error del script
    if result.stderr:
        print(result.stderr)

def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    # Añadir el manejador para el comando /puntuaciones
    dispatcher.add_handler(CommandHandler("puntuaciones", show_scores))
    # Añadir el manejador para el comando /help
    dispatcher.add_handler(CommandHandler("help", help_command))
    # Registro del comando /mrgrid en el dispatcher
    dispatcher.add_handler(CommandHandler("mrgrid", mrgrid))
    # Registro del comando /mrgrid en el dispatcher
    dispatcher.add_handler(CommandHandler("update_data", update_data))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('porra', porra)],
        states={
            SPRINT_FIRST: [MessageHandler(Filters.text & ~Filters.command, sprint_first)],
            SPRINT_SECOND: [MessageHandler(Filters.text & ~Filters.command, sprint_second)],
            SPRINT_THIRD: [MessageHandler(Filters.text & ~Filters.command, sprint_third)],
            RACE_FIRST: [MessageHandler(Filters.text & ~Filters.command, race_first)],
            RACE_SECOND: [MessageHandler(Filters.text & ~Filters.command, race_second)],
            RACE_THIRD: [MessageHandler(Filters.text & ~Filters.command, race_third)],
        },
        fallbacks=[]
    )

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler("update_results", update_results))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_results_input))


    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
