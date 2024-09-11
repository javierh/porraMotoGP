import json
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import pandas as pd

# Cargar configuración
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Token del bot
TOKEN = config['TOKEN']

# Load JSON data
with open(config['DATA_FILE'], 'r') as f:
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
    update.message.reply_text(f"¡Hola, {user.first_name}! Bienvenido al bot de porras de MotoGP.")
    update.message.reply_text("Usa /porra para hacer una predicción.\n Usa /help para ver los comandos disponibles.")

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

    # Verificar si el usuario ya ha realizado una predicción para este circuito
    try:
        with open(file_name, 'r') as f:
            predictions_data = json.load(f)
            if any(prediction['user_id'] == update.message.from_user.id for prediction in predictions_data):
                update.message.reply_text("Ya has realizado una porra para el próximo evento.")
                return ConversationHandler.END
    except FileNotFoundError:
        predictions_data = []

    update.message.reply_text(f"La siguiente Sprint Race y Carrera se realizará en: {next_race['name']}")

    # Solicitar los 3 primeros pilotos para la Sprint Race
    keyboard = [[pilot] for pilot in pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Selecciona el piloto que quedará en primera posición en la Sprint Race:', reply_markup=reply_markup)

    return SPRINT_FIRST

def sprint_first(update: Update, context: CallbackContext) -> int:
    first_pilot = update.message.text
    context.user_data['sprint_first_pilot'] = first_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot != first_pilot]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Selecciona el piloto que quedará en segunda posición en la Sprint Race:', reply_markup=reply_markup)

    return SPRINT_SECOND

def sprint_second(update: Update, context: CallbackContext) -> int:
    second_pilot = update.message.text
    context.user_data['sprint_second_pilot'] = second_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot not in [context.user_data['sprint_first_pilot'], second_pilot]]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Selecciona el piloto que quedará en tercera posición en la Sprint Race:', reply_markup=reply_markup)

    return SPRINT_THIRD

def sprint_third(update: Update, context: CallbackContext) -> int:
    third_pilot = update.message.text
    context.user_data['sprint_third_pilot'] = third_pilot

    # Solicitar los 3 primeros pilotos para la Carrera
    remaining_pilots = pilots[:]  # Resetear la lista de pilotos
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Selecciona el piloto que quedará en primera posición en la Carrera:', reply_markup=reply_markup)

    return RACE_FIRST

def race_first(update: Update, context: CallbackContext) -> int:
    first_pilot = update.message.text
    context.user_data['race_first_pilot'] = first_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot != first_pilot]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Selecciona el piloto que quedará en segunda posición en la Carrera:', reply_markup=reply_markup)

    return RACE_SECOND

def race_second(update: Update, context: CallbackContext) -> int:
    second_pilot = update.message.text
    context.user_data['race_second_pilot'] = second_pilot
    remaining_pilots = [pilot for pilot in pilots if pilot not in [context.user_data['race_first_pilot'], second_pilot]]
    keyboard = [[pilot] for pilot in remaining_pilots]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Selecciona el piloto que quedará en tercera posición en la Carrera:', reply_markup=reply_markup)

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

    update.message.reply_text(f"Tu porra ha sido registrada para {race_name}: {prediction}")
    return ConversationHandler.END

def update_results(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    if user.id not in ADMIN_IDS:
        update.message.reply_text("No tienes permiso para actualizar los resultados.")
        return

    # Admin can update results
    update.message.reply_text("Envía los resultados de la carrera en el formato: Carrera, Piloto1, Piloto2, Piloto3")

def handle_results_input(update: Update, context: CallbackContext) -> None:
    # Handle results input
    pass

# Función para manejar el comando /help
def help_command(update: Update, context: CallbackContext) -> None:
    help_message = (
        "Bienvenido al sistema de porra de MotoGP!\n\n"
        "Aquí tienes los comandos disponibles para interactuar con el bot:\n"
        "/start - Inicia la interacción con el bot.\n"
        "/porra - Registra tu porra para la próxima carrera.\n"
        "/puntuaciones - Muestra un listado con los datos de nombre y puntuación de los participantes ordenado de mayor a menor por puntos.\n"
        "/mrgrid - Muestra los tiempos de vuelta de los pilotos en la última sesión de clasificación.\n"
        "/help - Muestra este mensaje de ayuda.\n\n"
        "Para registrar tu porra, usa el comando /porra y sigue las instrucciones para ingresar tus predicciones para la sprint race y la carrera principal.\n"
        "Te recordamos que no se admiten modificaciones en la predicción, elige sabiamente tus pilotos"
        "¡Buena suerte!"
    )
    update.message.reply_text(help_message)


def show_scores(update: Update, context: CallbackContext) -> None:
    try:
        with open('results_puntuaciones.json', 'r') as f:
            scores = json.load(f)
    except FileNotFoundError:
        update.message.reply_text("No hay puntuaciones disponibles.")
        return

    # Ordenar los participantes por puntos de mayor a menor
    sorted_scores = sorted(scores.items(), key=lambda x: x[1]['points'], reverse=True)

    # Crear el mensaje con el listado de participantes y sus puntos
    message = "Puntuaciones de los participantes:\n\n"
    for user_id, data in sorted_scores:
        message += f"{data['user_name']}: {data['points']} puntos\n"

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
        update.message.reply_text(f"No se encontró el archivo para el circuito: {circuit_name}")
        return

    with open(file_path, 'r') as file:
        data = json.load(file)

    if 'classifications' not in data:
        update.message.reply_text(f"No se encontraron clasificaciones en el archivo para el circuito: {circuit_name}")
        return

    message = "Listado de pilotos y sus tiempos:\n"
    for entry in data['classifications']:
        message += f"{entry['position']}: {entry['full_name']} - {entry['best_lap_time']}\n"

    update.message.reply_text(message)

def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    # Añadir el manejador para el comando /puntuaciones
    dispatcher.add_handler(CommandHandler("puntuaciones", show_scores))
    # Añadir el manejador para el comando /help
    dispatcher.add_handler(CommandHandler("help", help_command))
    # Registro del comando /mrgrid en el dispatcher
    dispatcher.add_handler(CommandHandler("mrgrid", mrgrid))

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
