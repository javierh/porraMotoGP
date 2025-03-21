import asyncio
import telegram
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, Application, PicklePersistence, CallbackQueryHandler
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone
import pytz  # Para manejo de Timezones
import math  # Para funciones matemáticas en la paginación
import logging  # Para debug logging

# Load environment variables
load_dotenv()

# Configure logging with more details
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. Configuración Inicial ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_SHEET_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEET_CREDENTIALS_FILE', './google_credentials.json')
GOOGLE_SHEET_URL = os.getenv('GOOGLE_SHEET_URL')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Circuitos')
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Europe/Madrid'))

# Estados para la conversación de apuestas (ConversationHandler)
(APOSTAR_SPRINT_PILOTO1, APOSTAR_SPRINT_PILOTO2, APOSTAR_SPRINT_PILOTO3,
 APOSTAR_CARRERA_PILOTO1, APOSTAR_CARRERA_PILOTO2, APOSTAR_CARRERA_PILOTO3,
 EJECUTAR_SPRINT_PILOTO1, EJECUTAR_SPRINT_PILOTO2, EJECUTAR_SPRINT_PILOTO3,
 EJECUTAR_CARRERA_PILOTO1, EJECUTAR_CARRERA_PILOTO2, EJECUTAR_CARRERA_PILOTO3) = range(12)

# Prefijos para los callbacks de botones
PILOTO_CALLBACK_PREFIX = "piloto_"
PAGE_CALLBACK_PREFIX = "page_"
SPRINT_PREFIX = "sprint_"
CARRERA_PREFIX = "carrera_"
BUTTONS_PER_ROW = 2  # Número de botones por fila
MAX_BUTTONS_PER_PAGE = 8  # Máximo de botones por página

# --- 2. Autenticación Google Sheets ---
scopes = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
creds = Credentials.from_service_account_file(GOOGLE_SHEET_CREDENTIALS_FILE, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet(GOOGLE_SHEET_NAME)

def obtener_sesiones_desde_gsheet():
    """Obtiene y procesa los datos de sesiones desde Google Sheets (hoja 'Sesiones')."""
    try:
        sesiones_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Sesiones') # Abre la hoja 'Sesiones'
        data_sesiones = sesiones_sheet.get_all_records()
        sesiones = []
        for row in data_sesiones:
            try:
                # Intentar parsear las fechas, manejando posibles errores
                date_start = datetime.fromisoformat(row['date_start'].replace('Z', '+00:00')).astimezone(TIMEZONE) if row['date_start'] else None
                date_end = datetime.fromisoformat(row['date_end'].replace('Z', '+00:00')).astimezone(TIMEZONE) if row['date_end'] else None

                sesion = {
                    'circuit_id': row['circuit_id'],
                    'circuit_name': row['circuit_name'],
                    'session_id': row['session_id'],
                    'shortname': row['shortname'],
                    'date_start': date_start,
                    'date_end': date_end,
                    'category_id': row['category_id'],
                    'category_name': row['category_name']
                }
                sesiones.append(sesion)
            except ValueError as e:
                print(f"Error al procesar fila en Google Sheets (Sesiones): {row}. Error: {e}") # Loguear errores de parsing de fecha
        return sesiones
    except Exception as e:
        print(f"Error al obtener sesiones desde Google Sheets (hoja 'Sesiones'): {e}")
        return [] # En caso de error, retorna una lista vacía



# --- 3. Funciones de Google Sheets ---
def obtener_eventos_desde_gsheet():
    """Obtiene y procesa los datos de eventos desde Google Sheets (hoja 'Circuitos')."""
    try:
        eventos_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Circuitos') # Abre la hoja 'Circuitos'
        data_eventos = eventos_sheet.get_all_records()
        eventos = []
        for row in data_eventos:
            try:
                # Intentar parsear las fechas, manejando posibles errores
                date_start = datetime.fromisoformat(row['date_start'].replace('Z', '+00:00')).astimezone(TIMEZONE) if row['date_start'] else None
                date_end = datetime.fromisoformat(row['date_end'].replace('Z', '+00:00')).astimezone(TIMEZONE) if row['date_end'] else None

                evento = {
                    'event_id': row['event_id'],
                    'circuit_name': row['circuit_name'],
                    'date_start': date_start,
                    'date_end': date_end,
                    'hashtag': row['hashtag']
                }
                eventos.append(evento)
            except ValueError as e:
                print(f"Error al procesar fila en Google Sheets (Circuitos): {row}. Error: {e}") # Loguear errores de parsing de fecha
        return eventos
    except Exception as e:
        print(f"Error al obtener eventos desde Google Sheets (hoja 'Circuitos'): {e}")
        return [] # En caso de error, retorna una lista vacía

def obtener_pilotos_desde_gsheet():
    """Obtiene la lista de nombres de pilotos desde la hoja 'Pilotos' en Google Sheets."""
    try:
        pilotos_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Pilotos') # Abre la hoja 'Pilotos'
        data_pilotos = pilotos_sheet.get_all_records() # Obtiene todos los registros de la hoja 'Pilotos'
        pilotos_nombres = [row['rider_name'] for row in data_pilotos if row['rider_name']] # Extrae 'rider_name' y filtra filas vacías
        return pilotos_nombres
    except Exception as e:
        print(f"Error al obtener pilotos desde Google Sheets: {e}")
        return [] # En caso de error, retorna una lista vacía para evitar que el bot falle completamente

def guardar_usuario_en_gsheet(user):
    """Guarda o actualiza la información de un usuario en la hoja 'Jugones' de Google Sheets."""
    try:
        # Abrir la hoja Jugones (crearla si no existe)
        try:
            jugones_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Jugones')
        except gspread.exceptions.WorksheetNotFound:
            # Si no existe la hoja, crearla
            spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
            jugones_sheet = spreadsheet.add_worksheet(title='Jugones', rows=100, cols=5)
            # Añadir encabezados
            jugones_sheet.append_row(['chat_id', 'username', 'first_name', 'last_name', 'join_date'])
        
        # Verificar si el usuario ya existe
        cells = jugones_sheet.findall(str(user.id))
        if cells:  # Si encontró alguna celda
            # Si existe, actualizar la fila
            row_num = cells[0].row
            jugones_sheet.update(f'A{row_num}:E{row_num}', 
                               [[str(user.id), 
                                 user.username or '', 
                                 user.first_name or '', 
                                 user.last_name or '', 
                                 datetime.now(TIMEZONE).isoformat()]])
        else:  # No se encontró ninguna celda
            # Si no existe, añadir una nueva fila
            jugones_sheet.append_row([
                str(user.id),
                user.username or '',
                user.first_name or '',
                user.last_name or '',
                datetime.now(TIMEZONE).isoformat()
            ])
        
        return True
    except Exception as e:
        print(f"Error al guardar usuario en Google Sheets: {e}")
        return False

def evento_interno_a_gsheet(tipo_evento):
    """Convierte el tipo de evento del formato interno al usado en Google Sheets."""
    if tipo_evento == 'sprint':
        return 'SPR'
    elif tipo_evento == 'carrera':
        return 'RAC'
    return tipo_evento  # Si ya está en formato correcto o es desconocido, lo devuelve tal cual

def evento_gsheet_a_interno(tipo_evento):
    """Convierte el tipo de evento del formato de Google Sheets al formato interno."""
    if tipo_evento == 'SPR':
        return 'sprint'
    elif tipo_evento == 'RAC':
        return 'carrera'
    return tipo_evento  # Si ya está en formato correcto o es desconocido, lo devuelve tal cual

def guardar_apuesta_en_gsheet(chat_id, evento_id, tipo_evento, podio):
    """Guarda una apuesta en la hoja 'Apuestas' de Google Sheets."""
    try:
        # Obtener información adicional del evento
        eventos = obtener_eventos_desde_gsheet()
        # Buscar el evento comparando como strings para evitar problemas de tipo
        evento = next((ev for ev in eventos if str(ev['event_id']) == str(evento_id)), None)
        if not evento:
            print(f"No se encontró el evento con ID {evento_id} para guardar la apuesta")
            return False
        
        circuit_id = str(evento_id)  # Asegurar que siempre guardamos como string
        hashtag = evento.get('hashtag', '')
        
        # Convertir el tipo de evento al formato de Google Sheets
        tipo_evento_gsheet = evento_interno_a_gsheet(tipo_evento)
        
        # Abrir la hoja Apuestas (crearla si no existe)
        try:
            apuestas_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Apuestas')
        except gspread.exceptions.WorksheetNotFound:
            # Si no existe la hoja, crearla
            spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
            apuestas_sheet = spreadsheet.add_worksheet(title='Apuestas', rows=100, cols=8)
            # Añadir encabezados con el nuevo formato
            apuestas_sheet.append_row(['circuit_id', 'user_id', 'hashtag', 'posicion1', 'posicion2', 'posicion3', 'evento', 'timestamp'])
        
        # Verificar si ya existe una apuesta para este usuario, circuito y tipo de evento
        existing_rows = apuestas_sheet.findall(str(chat_id))
        for cell in existing_rows:
            row_num = cell.row
            row_data = apuestas_sheet.row_values(row_num)
            # Verificamos si es el mismo circuito y tipo de evento
            if len(row_data) >= 7 and str(row_data[0]) == str(circuit_id) and row_data[6] == tipo_evento_gsheet:
                # Actualizar apuesta existente
                apuestas_sheet.update(f'A{row_num}:H{row_num}',
                                   [[str(circuit_id), 
                                     str(chat_id),  # user_id
                                     hashtag, 
                                     podio[0], podio[1], podio[2],  # posiciones
                                     tipo_evento_gsheet,  # Nueva columna evento (SPR o RAC)
                                     datetime.now(TIMEZONE).isoformat()]])
                return True
        
        # Si no existe, añadir una nueva fila
        apuestas_sheet.append_row([
            str(circuit_id),
            str(chat_id),  # user_id
            hashtag,
            podio[0], podio[1], podio[2],  # posiciones
            tipo_evento_gsheet,  # Tipo de evento en formato Google Sheets
            datetime.now(TIMEZONE).isoformat()
        ])
        
        return True
    except Exception as e:
        print(f"Error al guardar apuesta en Google Sheets: {e}")
        return False

def cargar_apuestas_desde_gsheet():
    """Carga todas las apuestas desde la hoja 'Apuestas' de Google Sheets."""
    try:
        try:
            apuestas_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Apuestas')
        except gspread.exceptions.WorksheetNotFound:
            # Si no existe la hoja, no hay apuestas para cargar
            return {}
        
        data = apuestas_sheet.get_all_records()
        apuestas_cargadas = {}
        
        for row in data:
            try:
                # Adaptación a los nuevos nombres de columnas
                circuit_id = row.get('circuit_id')  # Aceptar circuit_id como string o int
                user_id = int(row.get('user_id', 0))
                
                # Usar la columna 'evento' (SPR o RAC) y convertirla al formato interno
                tipo_evento_gsheet = row.get('evento', '')
                tipo_evento = evento_gsheet_a_interno(tipo_evento_gsheet)
                
                podio = [
                    row.get('posicion1', ''),
                    row.get('posicion2', ''),
                    row.get('posicion3', '')
                ]
                
                if user_id not in apuestas_cargadas:
                    apuestas_cargadas[user_id] = {}
                if circuit_id not in apuestas_cargadas[user_id]:
                    apuestas_cargadas[user_id][circuit_id] = {}
                    
                apuestas_cargadas[user_id][circuit_id][tipo_evento] = podio
            except (ValueError, KeyError) as e:
                print(f"Error al procesar fila de apuesta: {e}, fila: {row}")
        
        return apuestas_cargadas
    except Exception as e:
        print(f"Error al cargar apuestas desde Google Sheets: {e}")
        return {}

def guardar_apuesta(chat_id, evento_id, tipo_evento, podio):
    """Guarda la apuesta de un usuario."""
    # Guardar en memoria - asegurarse de usar el mismo tipo de dato para el ID
    str_evento_id = str(evento_id)  # Convertir a string para consistencia
    
    if chat_id not in apuestas:
        apuestas[chat_id] = {}
    if str_evento_id not in apuestas[chat_id]:
        apuestas[chat_id][str_evento_id] = {}
    apuestas[chat_id][str_evento_id][tipo_evento] = podio
    
    # Guardar en Google Sheets con el nuevo formato
    guardar_apuesta_en_gsheet(chat_id, evento_id, tipo_evento, podio)

def obtener_apuesta_usuario(chat_id, evento_id, tipo_evento):
    """Obtiene la apuesta de un usuario para un evento y tipo de evento."""
    # Asegurar que estamos buscando con el tipo correcto de ID (string o int)
    # ya que los IDs pueden ser UUIDs en forma de string
    if chat_id in apuestas:
        for ev_id in apuestas[chat_id]:
            # Comparar como strings para ser compatible con ambos formatos
            if str(ev_id) == str(evento_id) and tipo_evento in apuestas[chat_id][ev_id]:
                return apuestas[chat_id][ev_id][tipo_evento]
    return None

def bloquear_apuestas_evento(evento_id, tipo_evento, podio_q2):
    """Bloquea las apuestas para un evento y tipo de evento, guardando el podio de Q2."""
    apuestas_q2_fallback[evento_id] = apuestas_q2_fallback.get(evento_id, {}) # Inicializa si no existe
    apuestas_q2_fallback[evento_id][tipo_evento] = podio_q2
    # TODO: Implementar lógica para notificar a los usuarios que las apuestas están cerradas y se usará Q2.


# --- 4. Funciones de Gestión de Fechas y Eventos ---
def obtener_deadline_sesion(evento_id, tipo_evento):
    """
    Obtiene la fecha y hora límite para apostar desde la hoja Sesiones.
    
    Args:
        evento_id: ID del evento/circuito
        tipo_evento: 'sprint'/'SPR' o 'carrera'/'RAC'
    
    Returns:
        datetime: Fecha y hora límite para apostar, o None si no se encontró
    """
    try:
        sesiones = obtener_sesiones_desde_gsheet()
        # Convertir al formato Google Sheets si es necesario
        tipo_sesion = evento_interno_a_gsheet(tipo_evento)
        
        # Buscar la sesión correspondiente al evento y tipo
        for sesion in sesiones:
            if str(sesion.get('circuit_id', '')) == str(evento_id) and sesion.get('shortname') == tipo_sesion:
                return sesion.get('date_start')  # Devuelve la fecha/hora de inicio de la sesión
        
        # Si no se encuentra, devolver None
        print(f"No se encontró información de la sesión {tipo_sesion} para el evento {evento_id}")
        return None
    except Exception as e:
        print(f"Error al obtener deadline desde Sesiones: {e}")
        return None

def obtener_evento_mas_proximo(eventos):
    """Determina el evento actualmente en curso o el próximo a comenzar."""
    ahora = datetime.now(TIMEZONE)
    
    # Primero buscar si hay algún evento en curso actualmente
    evento_en_curso = None
    for evento in eventos:
        if (evento['date_start'] and evento['date_end'] and 
            evento['date_start'] <= ahora <= evento['date_end']):
            return evento  # Si hay un evento en curso, lo devolvemos inmediatamente
    
    # Si no hay evento en curso, buscamos el próximo
    evento_proximo = None
    min_diferencia = timedelta.max
    
    for evento in eventos:
        if evento['date_start'] and evento['date_start'] > ahora:
            diferencia = evento['date_start'] - ahora
            if diferencia < min_diferencia:
                min_diferencia = diferencia
                evento_proximo = evento
    
    return evento_proximo

def es_tiempo_apuesta_abierto(evento, tipo_evento):
    """Verifica si el tiempo para apostar en un evento (Sprint o Carrera) está abierto."""
    if not evento: # Verificar si evento es válido
        return False

    ahora = datetime.now(TIMEZONE)
    
    # Obtener el deadline desde la hoja Sesiones
    deadline = obtener_deadline_sesion(evento['event_id'], tipo_evento)
    
    # Si no se encuentra el deadline en Sesiones, usar el método anterior como fallback
    if not deadline:
        # Fallback a la lógica anterior
        if not evento['date_start']:
            return False
            
        if tipo_evento == 'sprint' or tipo_evento == 'SPR':
            return ahora < evento['date_start'] - timedelta(minutes=45)
        else:  # carrera o RAC
            return ahora < evento['date_start'] - timedelta(minutes=15)
    
    # Si tenemos deadline, comparar con la hora actual
    return ahora < deadline

def format_datetime_para_usuario(datetime_obj):
    """Formatea un objeto datetime para mostrar al usuario."""
    if not datetime_obj:
        return "No especificado"
    return datetime_obj.strftime('%d-%m-%Y %H:%M %Z')


# --- 5. Gestión de Apuestas ---
apuestas = cargar_apuestas_desde_gsheet() # Inicializar cargando del Google Sheet
apuestas_q2_fallback = {} # Diccionario para guardar los podios de Q2 como fallback
resultados_oficiales = {}  # Diccionario para guardar resultados oficiales

def guardar_apuesta(chat_id, evento_id, tipo_evento, podio):
    """Guarda la apuesta de un usuario."""
    # Guardar en memoria
    if chat_id not in apuestas:
        apuestas[chat_id] = {}
    if evento_id not in apuestas[chat_id]:
        apuestas[chat_id][evento_id] = {}
    apuestas[chat_id][evento_id][tipo_evento] = podio
    
    # Guardar en Google Sheets
    guardar_apuesta_en_gsheet(chat_id, evento_id, tipo_evento, podio)

def obtener_apuesta_usuario(chat_id, evento_id, tipo_evento):
    """Obtiene la apuesta de un usuario para un evento y tipo de evento."""
    if chat_id in apuestas and evento_id in apuestas[chat_id] and tipo_evento in apuestas[chat_id][evento_id]:
        return apuestas[chat_id][evento_id][tipo_evento]
    return None

def bloquear_apuestas_evento(evento_id, tipo_evento, podio_q2):
    """Bloquea las apuestas para un evento y tipo de evento, guardando el podio de Q2."""
    apuestas_q2_fallback[evento_id] = apuestas_q2_fallback.get(evento_id, {}) # Inicializa si no existe
    apuestas_q2_fallback[evento_id][tipo_evento] = podio_q2
    # TODO: Implementar lógica para notificar a los usuarios que las apuestas están cerradas y se usará Q2.


# --- 6. Funciones de UI para Botones ---
def crear_teclado_pilotos(pilotos, prefix, page=0):
    """Crea un teclado inline con botones para cada piloto."""
    total_pages = math.ceil(len(pilotos) / MAX_BUTTONS_PER_PAGE)
    start_idx = page * MAX_BUTTONS_PER_PAGE
    end_idx = min(start_idx + MAX_BUTTONS_PER_PAGE, len(pilotos))
    
    pilotos_page = pilotos[start_idx:end_idx]
    keyboard = []
    
    # Crear filas con BUTTONS_PER_ROW botones cada una
    for i in range(0, len(pilotos_page), BUTTONS_PER_ROW):
        row = []
        for j in range(BUTTONS_PER_ROW):
            if i + j < len(pilotos_page):
                piloto = pilotos_page[i + j]
                callback_data = f"{prefix}{PILOTO_CALLBACK_PREFIX}{piloto}"
                row.append(InlineKeyboardButton(piloto, callback_data=callback_data))
        keyboard.append(row)
    
    # Añadir botones de navegación si hay más de una página
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"{prefix}{PAGE_CALLBACK_PREFIX}{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"{prefix}{PAGE_CALLBACK_PREFIX}{page+1}"))
        keyboard.append(nav_row)
    
    return InlineKeyboardMarkup(keyboard)

# --- 7. Manejadores de Comandos del Bot ---
async def start(update, context):
    """Comando /start: Mensaje de bienvenida e información básica."""
    user = update.message.from_user
    # Guardar información del usuario en Google Sheets
    guardar_usuario_en_gsheet(user)
    
    await update.message.reply_markdown_v2(
        fr'Hola {user.mention_markdown_v2()}\! 👋\n\n'
        'Bienvenido al bot de porras de MotoGP\! 🏍💨\n\n'
        'Utiliza /help para ver los comandos disponibles\.'
    )

async def help_command(update, context):
    """Comando /help: Muestra la lista de comandos disponibles."""
    help_text = """
Estos son los comandos disponibles:

/help - Muestra este mensaje de ayuda
/proximo_evento - Muestra información del próximo evento de MotoGP
/apostar_sprint - Permite apostar al podio de la Sprint Race
/apostar_carrera - Permite apostar al podio de la carrera principal
/ver_apuesta - Muestra tu apuesta actual para el próximo evento
/podio_q2 - Muestra el podio de Q2 que se usará si se cierran las apuestas (si aplica)
/ranking - Muestra la clasificación actual de todos los jugadores
/rules - Muestra las reglas del sistema de apuestas
"""
   
    help_text += """
----------------
Puedes consultar el código fuente en [GitHub](https://github.com/javierh/porraMotoGP)
    """
    await update.message.reply_text(help_text)

def escape_markdown_v2(text):
    """Escapa caracteres especiales para Markdown V2 de Telegram."""
    if not text:
        return ""
    
    # Caracteres especiales que necesitan escape en Markdown V2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Escapar cada caracter especial con una barra invertida
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    
    return text

async def proximo_evento_command(update, context):
    """Comando /proximo_evento: Muestra información del próximo evento."""
    eventos = obtener_eventos_desde_gsheet()
    evento_proximo = obtener_evento_mas_proximo(eventos)

    if evento_proximo:
        # Verificar y asignar apuestas por defecto si el tiempo se ha cerrado
        evento_id = evento_proximo['event_id']
        if not es_tiempo_apuesta_abierto(evento_proximo, 'SPR'):
            asignar_apuestas_q2_por_defecto(evento_id, 'sprint')
        if not es_tiempo_apuesta_abierto(evento_proximo, 'RAC'):
            asignar_apuestas_q2_por_defecto(evento_id, 'carrera')
            
        mensaje = f"Próximo Evento: *{escape_markdown_v2(evento_proximo['hashtag'])}*\n"
        mensaje += f"Comienza: {escape_markdown_v2(format_datetime_para_usuario(evento_proximo['date_start']))}\n"
        mensaje += f"Finaliza: {escape_markdown_v2(format_datetime_para_usuario(evento_proximo['date_end']))}\n"
        mensaje += f"Circuito: {escape_markdown_v2(evento_proximo['circuit_name'])}"
        await update.message.reply_markdown_v2(mensaje)
    else:
        await update.message.reply_text("No hay próximos eventos programados en este momento.")

async def apostar_sprint_command_inicio(update, context):
    """Inicia la conversación para apostar al Sprint Race."""
    logger.info(f"Usuario {update.effective_user.id} ha invocado /apostar_sprint")
    # Log more details about the update object
    logger.info(f"Update object type: {type(update)}")
    logger.info(f"Message text: {update.message.text if update.message else 'No message'}")
    
    eventos = obtener_eventos_desde_gsheet()
    evento_proximo = obtener_evento_mas_proximo(eventos)

    if not evento_proximo:
        await update.message.reply_text("No hay próximos eventos para apostar.")
        return ConversationHandler.END

    if not es_tiempo_apuesta_abierto(evento_proximo, 'sprint'):
        await update.message.reply_text(f"Lo siento, el tiempo para apostar en la Sprint Race de {evento_proximo['circuit_name']} ha terminado.")
        return ConversationHandler.END

    pilotos_disponibles = obtener_pilotos_desde_gsheet()
    context.user_data['evento_id'] = evento_proximo['event_id']
    context.user_data['tipo_evento'] = 'sprint'
    context.user_data['pilotos_disponibles_sprint'] = pilotos_disponibles # Guardar para validación
    context.user_data['podio_sprint_apuesta'] = [] # Inicializar la lista de podio

    # Obtener el deadline específico para la sprint desde la hoja Sesiones
    deadline = obtener_deadline_sesion(evento_proximo['event_id'], 'sprint')
    if not deadline:
        # Fallback a la fecha estimada
        deadline = evento_proximo['date_start'] - timedelta(minutes=45)

    mensaje = f"Vas a apostar al podio de la Sprint Race de *{escape_markdown_v2(evento_proximo['circuit_name'])}*\\.\n\n"
    mensaje += f"Tienes hasta: {escape_markdown_v2(format_datetime_para_usuario(deadline))} para apostar\\.\n\n"
    mensaje += "Elige el *Piloto 1* para tu podio:"
    
    # Crear teclado con botones para cada piloto
    keyboard = crear_teclado_pilotos(pilotos_disponibles, SPRINT_PREFIX + "p1_")
    
    await update.message.reply_markdown_v2(mensaje, reply_markup=keyboard)
    return APOSTAR_SPRINT_PILOTO1

async def apostar_sprint_piloto1_callback(update, context):
    """Procesa la selección del Piloto 1 para Sprint mediante botón."""
    query = update.callback_query
    await query.answer()
    
    # Extraer el nombre del piloto del callback_data
    callback_data = query.data
    prefix = SPRINT_PREFIX + "p1_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_sprint', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, SPRINT_PREFIX + "p1_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return APOSTAR_SPRINT_PILOTO1
    
    piloto1 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_sprint', [])
    
    if piloto1 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia una nueva apuesta con /apostar_sprint")
        return ConversationHandler.END
    
    context.user_data['podio_sprint_apuesta'].append(piloto1)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto1]
    context.user_data['pilotos_disponibles_sprint_piloto2'] = pilotos_restantes
    
    mensaje = f"Has elegido a *{escape_markdown_v2(piloto1)}* como Piloto 1 para el Sprint\\.\n\n"
    mensaje += "Ahora elige el *Piloto 2* para tu podio:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, SPRINT_PREFIX + "p2_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return APOSTAR_SPRINT_PILOTO2

async def apostar_sprint_piloto2_callback(update, context):
    """Procesa la selección del Piloto 2 para Sprint mediante botón."""
    query = update.callback_query
    await query.answer()
    
    # Extraer el nombre del piloto del callback_data
    callback_data = query.data
    prefix = SPRINT_PREFIX + "p2_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_sprint_piloto2', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, SPRINT_PREFIX + "p2_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return APOSTAR_SPRINT_PILOTO2
    
    piloto2 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_sprint_piloto2', [])
    
    if piloto2 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia una nueva apuesta con /apostar_sprint")
        return ConversationHandler.END
    
    context.user_data['podio_sprint_apuesta'].append(piloto2)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto2]
    context.user_data['pilotos_disponibles_sprint_piloto3'] = pilotos_restantes
    
    mensaje = f"Has elegido a *{escape_markdown_v2(piloto2)}* como Piloto 2 para el Sprint\\.\n\n"
    mensaje += "Por último, elige el *Piloto 3* para tu podio:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, SPRINT_PREFIX + "p3_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return APOSTAR_SPRINT_PILOTO3

async def apostar_sprint_piloto3_callback(update, context):
    """Procesa la selección del Piloto 3 para Sprint mediante botón y finaliza la apuesta."""
    query = update.callback_query
    await query.answer()
    
    # Extraer el nombre del piloto del callback_data
    callback_data = query.data
    prefix = SPRINT_PREFIX + "p3_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_sprint_piloto3', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, SPRINT_PREFIX + "p3_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return APOSTAR_SPRINT_PILOTO3
    
    piloto3 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_sprint_piloto3', [])
    
    if piloto3 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia una nueva apuesta con /apostar_sprint")
        return ConversationHandler.END
    
    context.user_data['podio_sprint_apuesta'].append(piloto3)
    podio_apuesta = context.user_data['podio_sprint_apuesta']
    evento_id = context.user_data['evento_id']
    tipo_evento = context.user_data['tipo_evento']
    chat_id = update.callback_query.message.chat_id
    
    # Guardar apuesta y usuario
    guardar_apuesta(chat_id, evento_id, tipo_evento, podio_apuesta)
    guardar_usuario_en_gsheet(update.callback_query.from_user)
    
    mensaje = f"Has elegido a *{escape_markdown_v2(piloto3)}* como Piloto 3 para el Sprint\\.\n\n"
    mensaje += "¡Apuesta de *Sprint Race* registrada con éxito\\! Tu podio es:\n"
    mensaje += f"🥇 1º: *{escape_markdown_v2(podio_apuesta[0])}*\n🥈 2º: *{escape_markdown_v2(podio_apuesta[1])}*\n🥉 3º: *{escape_markdown_v2(podio_apuesta[2])}*\n\n"
    mensaje += "Puedes ver tu apuesta con /ver\\_apuesta"
    
    await query.edit_message_text(mensaje, parse_mode="MarkdownV2")
    return ConversationHandler.END

async def apostar_carrera_command_inicio(update, context):
    """Inicia la conversación para apostar a la Carrera."""
    logger.info(f"Usuario {update.effective_user.id} ha invocado /apostar_carrera")
    # Log more details about the update object
    logger.info(f"Update object type: {type(update)}")
    logger.info(f"Message text: {update.message.text if update.message else 'No message'}")
    
    eventos = obtener_eventos_desde_gsheet()
    evento_proximo = obtener_evento_mas_proximo(eventos)

    if not evento_proximo:
        await update.message.reply_text("No hay próximos eventos para apostar.")
        return ConversationHandler.END

    if not es_tiempo_apuesta_abierto(evento_proximo, 'carrera'):
        await update.message.reply_text(f"Lo siento, el tiempo para apostar en la Carrera de {evento_proximo['hashtag']} ha terminado.")
        return ConversationHandler.END

    pilotos_disponibles = obtener_pilotos_desde_gsheet()
    context.user_data['evento_id'] = evento_proximo['event_id']
    context.user_data['tipo_evento'] = 'carrera'
    context.user_data['pilotos_disponibles_carrera'] = pilotos_disponibles # Guardar para validación
    context.user_data['podio_carrera_apuesta'] = [] # Inicializar la lista de podio

    # Obtener el deadline específico para la carrera desde la hoja Sesiones
    deadline = obtener_deadline_sesion(evento_proximo['event_id'], 'carrera')
    if not deadline:
        # Fallback a la fecha estimada
        deadline = evento_proximo['date_start'] - timedelta(minutes=15)

    mensaje = f"Vas a apostar al podio de la *Carrera* de *{escape_markdown_v2(evento_proximo['hashtag'])}*\\.\n\n"
    mensaje += f"Tienes hasta: {escape_markdown_v2(format_datetime_para_usuario(deadline))} para apostar\\.\n\n"
    mensaje += "Elige el *Piloto 1* para tu podio:"
    
    # Crear teclado con botones para cada piloto
    keyboard = crear_teclado_pilotos(pilotos_disponibles, CARRERA_PREFIX + "p1_")
    
    await update.message.reply_markdown_v2(mensaje, reply_markup=keyboard)
    return APOSTAR_CARRERA_PILOTO1

async def apostar_carrera_piloto1_callback(update, context):
    """Procesa la selección del Piloto 1 para Carrera mediante botón."""
    query = update.callback_query
    await query.answer()
    
    # Extraer el nombre del piloto del callback_data
    callback_data = query.data
    prefix = CARRERA_PREFIX + "p1_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_carrera', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, CARRERA_PREFIX + "p1_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return APOSTAR_CARRERA_PILOTO1
    
    piloto1 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_carrera', [])
    
    if piloto1 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia una nueva apuesta con /apostar_carrera")
        return ConversationHandler.END
    
    context.user_data['podio_carrera_apuesta'].append(piloto1)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto1]
    context.user_data['pilotos_disponibles_carrera_piloto2'] = pilotos_restantes
    
    mensaje = f"Has elegido a *{escape_markdown_v2(piloto1)}* como Piloto 1 para la Carrera\\.\n\n"
    mensaje += "Ahora elige el *Piloto 2* para tu podio:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, CARRERA_PREFIX + "p2_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return APOSTAR_CARRERA_PILOTO2

async def apostar_carrera_piloto2_callback(update, context):
    """Procesa la selección del Piloto 2 para Carrera mediante botón."""
    query = update.callback_query
    await query.answer()
    
    # Extraer el nombre del piloto del callback_data
    callback_data = query.data
    prefix = CARRERA_PREFIX + "p2_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_carrera_piloto2', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, CARRERA_PREFIX + "p2_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return APOSTAR_CARRERA_PILOTO2
    
    piloto2 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_carrera_piloto2', [])
    
    if piloto2 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia una nueva apuesta con /apostar_carrera")
        return ConversationHandler.END
    
    context.user_data['podio_carrera_apuesta'].append(piloto2)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto2]
    context.user_data['pilotos_disponibles_carrera_piloto3'] = pilotos_restantes
    
    mensaje = f"Has elegido a *{escape_markdown_v2(piloto2)}* como Piloto 2 para la Carrera\\.\n\n"
    mensaje += "Por último, elige el *Piloto 3* para tu podio:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, CARRERA_PREFIX + "p3_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return APOSTAR_CARRERA_PILOTO3

async def apostar_carrera_piloto3_callback(update, context):
    """Procesa la selección del Piloto 3 para Carrera mediante botón y finaliza la apuesta."""
    query = update.callback_query
    await query.answer()
    
    # Extraer el nombre del piloto del callback_data
    callback_data = query.data
    prefix = CARRERA_PREFIX + "p3_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_carrera_piloto3', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, CARRERA_PREFIX + "p3_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return APOSTAR_CARRERA_PILOTO3
    
    piloto3 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_carrera_piloto3', [])
    
    if piloto3 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia una nueva apuesta con /apostar_carrera")
        return ConversationHandler.END
    
    context.user_data['podio_carrera_apuesta'].append(piloto3)
    podio_apuesta = context.user_data['podio_carrera_apuesta']
    evento_id = context.user_data['evento_id']
    tipo_evento = context.user_data['tipo_evento']
    chat_id = update.callback_query.message.chat_id
    
    # Guardar apuesta y usuario
    guardar_apuesta(chat_id, evento_id, tipo_evento, podio_apuesta)
    guardar_usuario_en_gsheet(update.callback_query.from_user)
    
    mensaje = f"Has elegido a *{escape_markdown_v2(piloto3)}* como Piloto 3 para la Carrera\\.\n\n"
    mensaje += "¡Apuesta de *Carrera* registrada con éxito\\! Tu podio es:\n"
    mensaje += f"🥇 1º: *{escape_markdown_v2(podio_apuesta[0])}*\n🥈 2º: *{escape_markdown_v2(podio_apuesta[1])}*\n🥉 3º: *{escape_markdown_v2(podio_apuesta[2])}*\n\n"
    mensaje += "Puedes ver tu apuesta con /ver\\_apuesta"
    
    await query.edit_message_text(mensaje, parse_mode="MarkdownV2")
    return ConversationHandler.END

async def cancelar_apuesta(update, context):
    """Cancela la conversación de apuesta."""
    await update.message.reply_text('Apuesta cancelada.')
    return ConversationHandler.END

async def ver_apuesta_command(update, context):
    """Comando /ver_apuesta: Muestra la apuesta actual del usuario para el próximo evento."""
    evento_proximo = obtener_evento_mas_proximo(obtener_eventos_desde_gsheet())
    if not evento_proximo:
        await update.message.reply_text("No hay próximos eventos para mostrar apuestas.")
        return

    chat_id = update.message.chat_id
    evento_id = evento_proximo['event_id']
    
    # Verificar y asignar apuestas por defecto si el tiempo se ha cerrado
    if not es_tiempo_apuesta_abierto(evento_proximo, 'SPR'):
        asignar_apuestas_q2_por_defecto(evento_id, 'sprint')
    if not es_tiempo_apuesta_abierto(evento_proximo, 'RAC'):
        asignar_apuestas_q2_por_defecto(evento_id, 'carrera')

    apuesta_sprint = obtener_apuesta_usuario(chat_id, evento_id, 'sprint')
    apuesta_carrera = obtener_apuesta_usuario(chat_id, evento_id, 'carrera')

    mensaje = f"Tu apuesta para *{escape_markdown_v2(evento_proximo['hashtag'])}*:\n\n"

    if apuesta_sprint:
        es_por_defecto = (apuesta_sprint == obtener_q2_resultados(evento_id))
        mensaje += "*Sprint Race:* " + ("_(Q2 por defecto)_\n" if es_por_defecto else "\n")
        mensaje += f"🥇 1º: *{escape_markdown_v2(apuesta_sprint[0])}*\n🥈 2º: *{escape_markdown_v2(apuesta_sprint[1])}*\n🥉 3º: *{escape_markdown_v2(apuesta_sprint[2])}*\n\n"
    else:
        mensaje += "*Sprint Race:* _Sin apuesta realizada_\n\n"

    if apuesta_carrera:
        es_por_defecto = (apuesta_carrera == obtener_q2_resultados(evento_id))
        mensaje += "*Carrera:* " + ("_(Q2 por defecto)_\n" if es_por_defecto else "\n")
        mensaje += f"🥇 1º: *{escape_markdown_v2(apuesta_carrera[0])}*\n🥈 2º: *{escape_markdown_v2(apuesta_carrera[1])}*\n🥉 3º: *{escape_markdown_v2(apuesta_carrera[2])}*\n"
    else:
        mensaje += "*Carrera:* _Sin apuesta realizada_\n"

    await update.message.reply_markdown_v2(mensaje)


async def podio_q2_command(update, context):
    """Comando /podio_q2: Muestra el podio de Q2 que se usará si las apuestas se cierran."""
    evento_proximo = obtener_evento_mas_proximo(obtener_eventos_desde_gsheet())
    if not evento_proximo:
        await update.message.reply_text("No hay próximos eventos para mostrar podio de Q2.")
        return

    evento_id = evento_proximo['event_id']
    # Obtener resultados de Q2 directamente de la hoja
    resultados_q2 = obtener_q2_resultados(evento_id)
    
    mensaje = f"Podio de Q2 para *{escape_markdown_v2(evento_proximo['circuit_name'])}*:\n\n"

    if resultados_q2 and all(resultados_q2):  # Verificar que los resultados existen y no están vacíos
        mensaje += "*Resultados Q2 oficiales:* \n"
        mensaje += f"🥇 1º: *{escape_markdown_v2(resultados_q2[0])}*\n"
        mensaje += f"🥈 2º: *{escape_markdown_v2(resultados_q2[1])}*\n"
        mensaje += f"🥉 3º: *{escape_markdown_v2(resultados_q2[2])}*\n\n"
        
        # Información sobre las apuestas cerradas
        if not es_tiempo_apuesta_abierto(evento_proximo, 'sprint'):
            mensaje += "_Estos resultados se utilizarán como apuesta para usuarios que no hayan apostado al Sprint Race_\n\n"
        if not es_tiempo_apuesta_abierto(evento_proximo, 'carrera'):
            mensaje += "_Estos resultados se utilizarán como apuesta para usuarios que no hayan apostado a la Carrera_\n"
    else:
        mensaje += "*Resultados Q2:* _No disponibles todavía en la base de datos_\n\n"
        
        # Mostrar información del estado de las apuestas
        if es_tiempo_apuesta_abierto(evento_proximo, 'sprint'):
            mensaje += "Las apuestas para Sprint Race están *abiertas*\\.\n"
        else:
            mensaje += "Las apuestas para Sprint Race están *cerradas*\\.\n"
            
        if es_tiempo_apuesta_abierto(evento_proximo, 'carrera'):
            mensaje += "Las apuestas para Carrera están *abiertas*\\.\n"
        else:
            mensaje += "Las apuestas para Carrera están *cerradas*\\.\n"

    await update.message.reply_markdown_v2(mensaje)


async def rules_command(update: Update, context: CallbackContext) -> None:
    """Comando /rules: Muestra las reglas del sistema de apuestas."""
    rules_text = (
        "*Reglas del Sistema de Apuestas de MotoGP*\n\n"
        "1\\. Solo puedes hacer una predicción por evento\\.\n"
        "2\\. Debes seleccionar los 3 primeros pilotos tanto en Sprint como en Carrera\\.\n"
        "3\\. Se permiten cambios en la predicción una vez enviada, vuelve a realizarla como si fuera la primera vez\\.\n"
        "4\\. Las predicciones deben enviarse antes del inicio del evento\\.\n"
        "5\\. Sistema de puntos:\n"
        "   \\- Si un piloto que elegiste queda en el podio, ganas los puntos que gana el piloto\\.\n"
        "   \\- Si aciertas piloto y posición, ganas el doble de puntos\\.\n"
    )
    await update.message.reply_markdown_v2(rules_text)

async def error(update, context):
    """Log errors caused by updates."""
    print(f'Update {update} caused error {context.error}')


# --- Nuevos comandos para ejecutar resultados ---

async def ejecutar_sprint_command(update, context):
    """Comando /ejecutar_sprint: Registra los resultados oficiales de la Sprint Race."""
    logger.info(f"Usuario {update.message.from_user.id} ha invocado /ejecutar_sprint")
    
    
    eventos = obtener_eventos_desde_gsheet()
    evento_proximo = obtener_evento_mas_proximo(eventos)
    
    if not evento_proximo:
        await update.message.reply_text("No hay eventos próximos para ejecutar resultados.")
        return ConversationHandler.END
    
    # Asignar apuestas Q2 por defecto si el tiempo de apuestas ha cerrado
    evento_id = evento_proximo['event_id']
    asignar_apuestas_q2_por_defecto(evento_id, 'sprint')
    
    context.user_data['evento_id'] = evento_id
    context.user_data['resultado_sprint'] = []
    
    pilotos_disponibles = obtener_pilotos_desde_gsheet()
    context.user_data['pilotos_disponibles_ejecutar_sprint'] = pilotos_disponibles
    
    mensaje = f"Vas a registrar el resultado oficial de la Sprint Race de *{escape_markdown_v2(evento_proximo['hashtag'])}*\\.\n\n"
    mensaje += "Selecciona el *Piloto que quedó en 1ª posición*:"
    
    keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_sprint_p1_")
    
    await update.message.reply_markdown_v2(mensaje, reply_markup=keyboard)
    return EJECUTAR_SPRINT_PILOTO1

async def ejecutar_sprint_piloto1_callback(update, context):
    """Procesa la selección del Piloto 1 para resultado oficial de Sprint."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    prefix = "ejecutar_sprint_p1_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_sprint', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_sprint_p1_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return EJECUTAR_SPRINT_PILOTO1
    
    piloto1 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_sprint', [])
    
    if piloto1 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia de nuevo con /ejecutar_sprint")
        return ConversationHandler.END
    
    context.user_data['resultado_sprint'].append(piloto1)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto1]
    context.user_data['pilotos_disponibles_ejecutar_sprint_p2'] = pilotos_restantes
    
    mensaje = f"Has seleccionado a *{escape_markdown_v2(piloto1)}* como 1º puesto en Sprint\\.\n\n"
    mensaje += "Ahora selecciona el *Piloto que quedó en 2ª posición*:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, "ejecutar_sprint_p2_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return EJECUTAR_SPRINT_PILOTO2

async def ejecutar_sprint_piloto2_callback(update, context):
    """Procesa la selección del Piloto 2 para resultado oficial de Sprint."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    prefix = "ejecutar_sprint_p2_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_sprint_p2', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_sprint_p2_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return EJECUTAR_SPRINT_PILOTO2
    
    piloto2 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_sprint_p2', [])
    
    if piloto2 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia de nuevo con /ejecutar_sprint")
        return ConversationHandler.END
    
    context.user_data['resultado_sprint'].append(piloto2)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto2]
    context.user_data['pilotos_disponibles_ejecutar_sprint_p3'] = pilotos_restantes
    
    mensaje = f"Has seleccionado a *{escape_markdown_v2(piloto2)}* como 2º puesto en Sprint\\.\n\n"
    mensaje += "Por último, selecciona el *Piloto que quedó en 3ª posición*:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, "ejecutar_sprint_p3_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return EJECUTAR_SPRINT_PILOTO3

async def ejecutar_sprint_piloto3_callback(update, context):
    """Procesa la selección del Piloto 3 para resultado oficial de Sprint y guarda el resultado."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    prefix = "ejecutar_sprint_p3_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_sprint_p3', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_sprint_p3_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return EJECUTAR_SPRINT_PILOTO3
    
    piloto3 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_sprint_p3', [])
    
    if piloto3 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia de nuevo con /ejecutar_sprint")
        return ConversationHandler.END
    
    context.user_data['resultado_sprint'].append(piloto3)
    resultado = context.user_data['resultado_sprint']
    evento_id = context.user_data['evento_id']
    
    # Guardar el resultado oficial
    if evento_id not in resultados_oficiales:
        resultados_oficiales[evento_id] = {}
    resultados_oficiales[evento_id]['sprint'] = resultado
    
    # Calcular puntos y actualizar ranking
    calcular_y_actualizar_puntos_del_evento(evento_id, 'sprint')
    
    mensaje = "✅ *Resultado oficial de Sprint Race registrado correctamente*\n\n"
    mensaje += f"🥇 1º: *{escape_markdown_v2(resultado[0])}*\n"
    mensaje += f"🥈 2º: *{escape_markdown_v2(resultado[1])}*\n"
    mensaje += f"🥉 3º: *{escape_markdown_v2(resultado[2])}*\n\n"
    mensaje += "Los puntos se han calculado y el ranking ha sido actualizado\\."
    
    await query.edit_message_text(mensaje, parse_mode="MarkdownV2")
    return ConversationHandler.END

async def ejecutar_carrera_command(update, context):
    """Comando /ejecutar_carrera: Registra los resultados oficiales de la Carrera."""
    logger.info(f"Usuario {update.message.from_user.id} ha invocado /ejecutar_carrera")
    
    # Verificar si el usuario tiene permisos (puedes implementar una lista de admins)
    user_id = update.effective_user.id
   
    
    eventos = obtener_eventos_desde_gsheet()
    evento_proximo = obtener_evento_mas_proximo(eventos)
    
    if not evento_proximo:
        await update.message.reply_text("No hay eventos próximos para ejecutar resultados.")
        return ConversationHandler.END
    
    # Asignar apuestas Q2 por defecto si el tiempo de apuestas ha cerrado
    evento_id = evento_proximo['event_id']
    asignar_apuestas_q2_por_defecto(evento_id, 'carrera')
    
    context.user_data['evento_id'] = evento_id
    context.user_data['resultado_carrera'] = []
    
    pilotos_disponibles = obtener_pilotos_desde_gsheet()
    context.user_data['pilotos_disponibles_ejecutar_carrera'] = pilotos_disponibles
    
    mensaje = f"Vas a registrar el resultado oficial de la Carrera de *{escape_markdown_v2(evento_proximo['hashtag'])}*\\.\n\n"
    mensaje += "Selecciona el *Piloto que quedó en 1ª posición*:"
    
    keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_carrera_p1_")
    
    await update.message.reply_markdown_v2(mensaje, reply_markup=keyboard)
    return EJECUTAR_CARRERA_PILOTO1

async def ejecutar_carrera_piloto1_callback(update, context):
    """Procesa la selección del Piloto 1 para resultado oficial de Carrera."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    prefix = "ejecutar_carrera_p1_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_carrera', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_carrera_p1_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return EJECUTAR_CARRERA_PILOTO1
    
    piloto1 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_carrera', [])
    
    if piloto1 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia de nuevo con /ejecutar_carrera")
        return ConversationHandler.END
    
    context.user_data['resultado_carrera'].append(piloto1)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto1]
    context.user_data['pilotos_disponibles_ejecutar_carrera_p2'] = pilotos_restantes
    
    mensaje = f"Has seleccionado a *{escape_markdown_v2(piloto1)}* como 1º puesto en Carrera\\.\n\n"
    mensaje += "Ahora selecciona el *Piloto que quedó en 2ª posición*:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, "ejecutar_carrera_p2_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return EJECUTAR_CARRERA_PILOTO2

async def ejecutar_carrera_piloto2_callback(update, context):
    """Procesa la selección del Piloto 2 para resultado oficial de Carrera."""
    query = update.callback_query
    await query.answer()
    
    callback_data = y.data
    prefix = "ejecutar_carrera_p2_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_carrera_p2', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_carrera_p2_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return EJECUTAR_CARRERA_PILOTO2
    
    piloto2 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_carrera_p2', [])
    
    if piloto2 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia de nuevo con /ejecutar_carrera")
        return ConversationHandler.END
    
    context.user_data['resultado_carrera'].append(piloto2)
    pilotos_restantes = [p for p in pilotos_disponibles if p != piloto2]
    context.user_data['pilotos_disponibles_ejecutar_carrera_p3'] = pilotos_restantes
    
    mensaje = f"Has seleccionado a *{escape_markdown_v2(piloto2)}* como 2º puesto en Carrera\\.\n\n"
    mensaje += "Por último, selecciona el *Piloto que quedó en 3ª posición*:"
    
    keyboard = crear_teclado_pilotos(pilotos_restantes, "ejecutar_carrera_p3_")
    
    await query.edit_message_text(mensaje, reply_markup=keyboard, parse_mode="MarkdownV2")
    return EJECUTAR_CARRERA_PILOTO3

async def ejecutar_carrera_piloto3_callback(update, context):
    """Procesa la selección del Piloto 3 para resultado oficial de Carrera y guarda el resultado."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    prefix = "ejecutar_carrera_p3_" + PILOTO_CALLBACK_PREFIX
    
    # Manejar navegación de páginas
    if PAGE_CALLBACK_PREFIX in callback_data:
        page = int(callback_data.split(PAGE_CALLBACK_PREFIX)[1])
        pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_carrera_p3', [])
        keyboard = crear_teclado_pilotos(pilotos_disponibles, "ejecutar_carrera_p3_", page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return EJECUTAR_CARRERA_PILOTO3
    
    piloto3 = callback_data[len(prefix):]
    pilotos_disponibles = context.user_data.get('pilotos_disponibles_ejecutar_carrera_p3', [])
    
    if piloto3 not in pilotos_disponibles:
        await query.edit_message_text("Error: Piloto no válido. Inicia de nuevo con /ejecutar_carrera")
        return ConversationHandler.END
    
    context.user_data['resultado_carrera'].append(piloto3)
    resultado = context.user_data['resultado_carrera']
    evento_id = context.user_data['evento_id']
    
    # Guardar el resultado oficial
    if evento_id not in resultados_oficiales:
        resultados_oficiales[evento_id] = {}
    resultados_oficiales[evento_id]['carrera'] = resultado
    
    # Calcular puntos y actualizar ranking
    calcular_y_actualizar_puntos_del_evento(evento_id, 'carrera')
    
    mensaje = "✅ *Resultado oficial de Carrera registrado correctamente*\n\n"
    mensaje += f"🥇 1º: *{escape_markdown_v2(resultado[0])}*\n"
    mensaje += f"🥈 2º: *{escape_markdown_v2(resultado[1])}*\n"
    mensaje += f"🥉 3º: *{escape_markdown_v2(resultado[2])}*\n\n"
    mensaje += "Los puntos se han calculado y el ranking ha sido actualizado\\."
    
    await query.edit_message_text(mensaje, parse_mode="MarkdownV2")
    return ConversationHandler.END

# Handler de mensajes para debug
async def debug_message_handler(update, context):
    """Handler para debug - captura todos los mensajes que no coinciden con otros handlers"""
    logger.info(f"Mensaje recibido no manejado: '{update.message.text}' de usuario {update.message.from_user.id}")
    return None

# --- 7. Lógica Principal y Manejadores ---
conv_handler_sprint = ConversationHandler(
    entry_points=[CommandHandler('apostar_sprint', apostar_sprint_command_inicio)],
    states={
        APOSTAR_SPRINT_PILOTO1: [
            CallbackQueryHandler(apostar_sprint_piloto1_callback, pattern=f"^{SPRINT_PREFIX}p1_")
        ],
        APOSTAR_SPRINT_PILOTO2: [
            CallbackQueryHandler(apostar_sprint_piloto2_callback, pattern=f"^{SPRINT_PREFIX}p2_")
        ],
        APOSTAR_SPRINT_PILOTO3: [
            CallbackQueryHandler(apostar_sprint_piloto3_callback, pattern=f"^{SPRINT_PREFIX}p3_")
        ]
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    allow_reentry=True,
    persistent=True,
    per_message=False,  # Changed from True to False
    name='sprint_conversation'
)

conv_handler_carrera = ConversationHandler(
    entry_points=[CommandHandler('apostar_carrera', apostar_carrera_command_inicio)],
    states={
        APOSTAR_CARRERA_PILOTO1: [
            CallbackQueryHandler(apostar_carrera_piloto1_callback, pattern=f"^{CARRERA_PREFIX}p1_")
        ],
        APOSTAR_CARRERA_PILOTO2: [
            CallbackQueryHandler(apostar_carrera_piloto2_callback, pattern=f"^{CARRERA_PREFIX}p2_")
        ],
        APOSTAR_CARRERA_PILOTO3: [
            CallbackQueryHandler(apostar_carrera_piloto3_callback, pattern=f"^{CARRERA_PREFIX}p3_")
        ]
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    allow_reentry=True,
    persistent=True,
    per_message=False,  # Changed from True to False
    name='carrera_conversation'
)

# Agregar los nuevo conversation handlers para ejecutar resultados
conv_handler_ejecutar_sprint = ConversationHandler(
    entry_points=[CommandHandler('ejecutar_sprint', ejecutar_sprint_command)],
    states={
        EJECUTAR_SPRINT_PILOTO1: [
            CallbackQueryHandler(ejecutar_sprint_piloto1_callback, pattern="^ejecutar_sprint_p1_")
        ],
        EJECUTAR_SPRINT_PILOTO2: [
            CallbackQueryHandler(ejecutar_sprint_piloto2_callback, pattern="^ejecutar_sprint_p2_")
        ],
        EJECUTAR_SPRINT_PILOTO3: [
            CallbackQueryHandler(ejecutar_sprint_piloto3_callback, pattern="^ejecutar_sprint_p3_")
        ]
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    allow_reentry=True,
    persistent=True,
    per_message=False,  # Changed from True to False
    name='ejecutar_sprint_conversation'
)

conv_handler_ejecutar_carrera = ConversationHandler(
    entry_points=[CommandHandler('ejecutar_carrera', ejecutar_carrera_command)],
    states={
        EJECUTAR_CARRERA_PILOTO1: [
            CallbackQueryHandler(ejecutar_carrera_piloto1_callback, pattern="^ejecutar_carrera_p1_")
        ],
        EJECUTAR_CARRERA_PILOTO2: [
            CallbackQueryHandler(ejecutar_carrera_piloto2_callback, pattern="^ejecutar_carrera_p2_")
        ],
        EJECUTAR_CARRERA_PILOTO3: [
            CallbackQueryHandler(ejecutar_carrera_piloto3_callback, pattern="^ejecutar_carrera_p3_")
        ]
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    allow_reentry=True,
    persistent=True,
    per_message=False,  # Changed from True to False
    name='ejecutar_carrera_conversation'
)

# Añadir un manejador directo para los comandos para debug
async def direct_apostar_sprint(update, context):
    logger.info("Direct apostar_sprint handler called")
    return await apostar_sprint_command_inicio(update, context)

async def direct_apostar_carrera(update, context):
    logger.info("Direct apostar_carrera handler called")
    return await apostar_carrera_command_inicio(update, context)

async def ranking_command(update, context):
    """Comando /ranking: Muestra la clasificación actual de todos los jugadores."""
    try:
        # Obtener datos de la hoja Ranking
        try:
            ranking_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Ranking')
            datos_ranking = ranking_sheet.get_all_records()
            logger.info(f"Datos de ranking obtenidos: {len(datos_ranking)} registros")
        except gspread.exceptions.WorksheetNotFound:
            await update.message.reply_text("No hay datos de ranking disponibles todavía.")
            return
        
        if not datos_ranking:
            await update.message.reply_text("No hay datos de ranking disponibles todavía.")
            return
        
        # Ordenar por puntuación (score) de mayor a menor con manejo seguro de tipos
        for jugador in datos_ranking:
            try:
                jugador['score'] = int(str(jugador.get('score', '0')))
            except (ValueError, TypeError):
                logger.error(f"Error al convertir score para jugador: {jugador}")
                jugador['score'] = 0
                
            try:
                jugador['points_last_circuit'] = int(str(jugador.get('points_last_circuit', '0')))
            except (ValueError, TypeError):
                logger.error(f"Error al convertir points_last_circuit para jugador: {jugador}")
                jugador['points_last_circuit'] = 0
        
        datos_ordenados = sorted(datos_ranking, key=lambda x: x.get('score', 0), reverse=True)
        
        # Preparar mensaje con el ranking
        mensaje = "*🏆 Ranking actual 🏆*\n\n"
        
        # Intentar obtener nombres de usuario desde la hoja Jugones para ser más amigable
        jugones_dict = {}
        try:
            jugones_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Jugones')
            datos_jugones = jugones_sheet.get_all_records()
            for j in datos_jugones:
                try:
                    # Usar user_id en lugar de chat_id según la estructura actualizada
                    user_id = int(str(j.get('user_id', '0')))
                    
                    # Primero intentar con nickname, luego combinar first_name + last_name
                    nickname = j.get('nickname', '')
                    first_name = j.get('first_name', '')
                    last_name = j.get('last_name', '')
                    
                    if nickname:
                        nombre_mostrar = nickname
                    elif first_name or last_name:
                        nombre_mostrar = f"{first_name} {last_name}".strip()
                    else:
                        nombre_mostrar = f"Usuario {user_id}"
                        
                    jugones_dict[user_id] = nombre_mostrar
                except (ValueError, TypeError) as e:
                    logger.error(f"Error procesando datos del jugador: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error al obtener datos de jugones: {e}")
        
        # Construir la tabla de clasificación
        posicion = 1
        for jugador in datos_ordenados:
            try:
                user_id = int(str(jugador.get('user_id', '0')))
                score = jugador.get('score', 0)
                points_last = jugador.get('points_last_circuit', 0)
                
                # Intentar obtener nombre de usuario
                nombre_usuario = jugones_dict.get(user_id, f"Usuario {user_id}")
                nombre_escapado = escape_markdown_v2(str(nombre_usuario))
                
                # Formatear línea del ranking
                if posicion <= 3:  # Destacar top 3
                    emoji = ['🥇', '🥈', '🥉'][posicion-1]
                    mensaje += f"{emoji} *{posicion}\\. {nombre_escapado}*: {score} pts \\(\\+{points_last} último evento\\)\n"
                else:
                    mensaje += f"{posicion}\\. {nombre_escapado}: {score} pts \\(\\+{points_last} último evento\\)\n"
                
                posicion += 1
            except Exception as e:
                logger.error(f"Error al procesar jugador del ranking: {e}")
        
        await update.message.reply_markdown_v2(mensaje)
    except Exception as e:
        logger.error(f"Error al mostrar ranking: {e}", exc_info=True)
        await update.message.reply_text("Hubo un error al obtener el ranking. Inténtalo más tarde.")

def calcular_puntos_apuesta(apuesta, resultado_oficial, tipo_evento):
    """
    Calcula los puntos obtenidos en una apuesta según el resultado oficial.
    
    Reglas de puntuación:
    - Sprint: 1º=12pts, 2º=9pts, 3º=7pts
    - Carrera: 1º=25pts, 2º=20pts, 3º=16pts
    - Si acierta piloto y posición, puntos dobles
    """
    if not apuesta or not resultado_oficial:
        return 0
    
    # Convertir tipo_evento a formato interno si es necesario
    tipo_evento_interno = evento_gsheet_a_interno(tipo_evento)
    
    # Definir puntos por posición según tipo de evento
    if tipo_evento_interno == 'sprint':
        puntos_por_posicion = [12, 9, 7]
    else:  # carrera
        puntos_por_posicion = [25, 20, 16]
    
    puntos_totales = 0
    
    # Revisar cada posición del podio
    for i in range(3):
        piloto_apostado = apuesta[i] if i < len(apuesta) else None
        piloto_oficial = resultado_oficial[i] if i < len(resultado_oficial) else None
        
        if piloto_apostado and piloto_oficial:
            # Si acierta piloto y posición exacta → puntos dobles
            if piloto_apostado == piloto_oficial:
                puntos_totales += puntos_por_posicion[i] * 2
            # Si el piloto apostado está en el podio pero en otra posición → puntos normales
            elif piloto_apostado in resultado_oficial:
                puntos_totales += puntos_por_posicion[resultado_oficial.index(piloto_apostado)]
    
    return puntos_totales

def actualizar_ranking_en_gsheet(chat_id, puntos_circuito, evento_id):
    """
    Actualiza la puntuación del usuario en la hoja Ranking de Google Sheets.
    
    Args:
        chat_id (int): ID del chat del usuario
        puntos_circuito (int): Puntos obtenidos en este circuito
        evento_id (str): ID del evento (circuito)
    """
    try:
        # Abrir la hoja Ranking (crearla si no existe)
        try:
            ranking_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Ranking')
        except gspread.exceptions.WorksheetNotFound:
            # Si no existe la hoja, crearla
            spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
            ranking_sheet = spreadsheet.add_worksheet(title='Ranking', rows=100, cols=3)
            # Añadir encabezados
            ranking_sheet.append_row(['user_id', 'score', 'points_last_circuit'])
        
        # Buscar al usuario en la hoja de ranking
        usuario_existente = False
        cells = ranking_sheet.findall(str(chat_id))
        
        if cells:  # Si encontró alguna celda con el user_id
            row_num = cells[0].row
            row_data = ranking_sheet.row_values(row_num)
            
            # Si hay datos de score previos
            score_previo = int(row_data[1]) if len(row_data) > 1 and row_data[1].isdigit() else 0
            nuevo_score = score_previo + puntos_circuito
            
            # Actualizar fila existente
            ranking_sheet.update(f'A{row_num}:C{row_num}', 
                               [[str(chat_id), 
                                 str(nuevo_score), 
                                 str(puntos_circuito)]])
        else:
            # Si no existe, añadir una nueva fila
            ranking_sheet.append_row([
                str(chat_id),
                str(puntos_circuito),  # Score inicial = puntos del circuito actual
                str(puntos_circuito)
            ])
        
        return True
    except Exception as e:
        print(f"Error al actualizar ranking en Google Sheets: {e}")
        return False

def calcular_y_actualizar_puntos_del_evento(evento_id, tipo_evento):
    """
    Calcula puntos para todos los usuarios y actualiza el ranking después de un evento oficial.
    
    Args:
        evento_id (str): ID del evento (circuito)
        tipo_evento (str): 'sprint' o 'carrera'
    """
    # Obtener resultado oficial
    if evento_id not in resultados_oficiales or tipo_evento not in resultados_oficiales[evento_id]:
        print(f"No se encontró resultado oficial para {tipo_evento} en evento {evento_id}")
        return False
    
    resultado_oficial = resultados_oficiales[evento_id][tipo_evento]
    puntos_circuito_por_usuario = {}  # Para almacenar puntos por usuario
    
    # Calcular puntos para cada usuario que hizo apuestas
    for user_id, eventos_usuario in apuestas.items():
        for ev_id in eventos_usuario:
            if str(ev_id) == str(evento_id) and tipo_evento in eventos_usuario[ev_id]:
                apuesta_usuario = eventos_usuario[ev_id][tipo_evento]
                puntos = calcular_puntos_apuesta(apuesta_usuario, resultado_oficial, tipo_evento)
                
                if user_id not in puntos_circuito_por_usuario:
                    puntos_circuito_por_usuario[user_id] = 0
                puntos_circuito_por_usuario[user_id] += puntos
                
                print(f"Usuario {user_id}: {puntos} puntos en {tipo_evento}")
    
    # Actualizar ranking en Google Sheets
    for user_id, puntos in puntos_circuito_por_usuario.items():
        actualizar_ranking_en_gsheet(user_id, puntos, evento_id)
    
    return True

def obtener_usuarios_registrados():
    """Obtiene la lista de usuarios registrados en la hoja 'Jugones'."""
    try:
        try:
            jugones_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Jugones')
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("La hoja 'Jugones' no existe todavía")
            return []
        
        data_usuarios = jugones_sheet.get_all_records()
        usuarios = [int(row['chat_id']) for row in data_usuarios if 'chat_id' in row and row['chat_id']]
        logger.info(f"Se encontraron {len(usuarios)} usuarios registrados")
        return usuarios
    except Exception as e:
        logger.error(f"Error al obtener usuarios registrados: {e}", exc_info=True)
        return []

def obtener_q2_resultados(evento_id):
    """Obtiene los resultados de Q2 para un evento específico desde la hoja 'Q2'."""
    try:
        try:
            q2_sheet = gc.open_by_url(GOOGLE_SHEET_URL).worksheet('Q2')
            logger.info(f"Hoja Q2 abierta correctamente")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("La hoja 'Q2' no existe todavía")
            return None
        
        # Buscar los datos de Q2 para el evento específico
        todas_filas = q2_sheet.get_all_records()
        logger.info(f"Q2: Se encontraron {len(todas_filas)} filas en total")
        
        # Imprimir algunas filas para depuración (máximo 5)
        for idx, fila in enumerate(todas_filas[:5]):
            logger.debug(f"Q2 muestra fila {idx}: {fila}")
        
        # Buscar la fila correspondiente al evento
        for fila in todas_filas:
            # Convertir ambos valores a string para comparación consistente
            circuit_id_sheet = str(fila.get('circuit_id', ''))
            evento_id_str = str(evento_id)
            
            if circuit_id_sheet == evento_id_str:
                result = [
                    fila.get('posicion1', ''),
                    fila.get('posicion2', ''),
                    fila.get('posicion3', '')
                ]
                logger.info(f"Q2: Encontrados resultados para evento {evento_id}: {result}")
                return result
        
        logger.warning(f"Q2: No se encontraron resultados para el evento {evento_id}")
        return None  # No se encontraron resultados para este evento
    except Exception as e:
        logger.error(f"Error al obtener resultados Q2: {e}", exc_info=True)
        return None

def asignar_apuestas_q2_por_defecto(evento_id, tipo_evento, forzar=False):
    """
    Asigna automáticamente las posiciones de Q2 como apuesta para los usuarios
    registrados que no hicieron una apuesta para el evento y tipo específico.
    
    Args:
        evento_id: ID del evento/circuito
        tipo_evento: 'sprint' o 'carrera'
        forzar: Si True, ignora las comprobaciones de tiempo y asigna igualmente
    """
    try:
        logger.info(f"Iniciando asignación de Q2 para evento {evento_id}, tipo {tipo_evento}")
        
        # Verificar si el tiempo para apostar se ha cerrado
        eventos = obtener_eventos_desde_gsheet()
        evento = next((e for e in eventos if str(e['event_id']) == str(evento_id)), None)
        
        if not evento:
            logger.error(f"No se encontró el evento con ID {evento_id}")
            return False
        
        # Convertir tipo_evento a formato Google Sheets para comparar
        tipo_evento_gsheet = evento_interno_a_gsheet(tipo_evento)
        apuestas_abiertas = es_tiempo_apuesta_abierto(evento, tipo_evento)
        logger.info(f"Las apuestas están {'abiertas' if apuestas_abiertas else 'cerradas'} para {evento['hashtag']} - {tipo_evento}")
        
        if apuestas_abiertas and not forzar:
            logger.info(f"El tiempo para apostar en {tipo_evento} aún está abierto. No se asignan apuestas Q2.")
            return False
        
        # Obtener resultados de Q2
        q2_resultados = obtener_q2_resultados(evento_id)
        logger.info(f"Resultados Q2 obtenidos para evento {evento_id}: {q2_resultados}")
        
        if not q2_resultados or '' in q2_resultados or None in q2_resultados:
            logger.warning(f"No hay resultados Q2 completos para el evento {evento_id}")
            return False
        
        # Obtener usuarios registrados
        usuarios = obtener_usuarios_registrados()
        logger.info(f"Usuarios registrados: {len(usuarios)}")
        
        if not usuarios:
            logger.warning("No hay usuarios registrados")
            return False
        
        # Asignar apuestas por defecto a usuarios sin apuesta
        contador = 0
        usuarios_sin_apuesta = []
        
        for user_id in usuarios:
            # Verificar si el usuario ya tiene una apuesta
            tiene_apuesta = False
            if user_id in apuestas:
                for ev_id in apuestas[user_id]:
                    if str(ev_id) == str(evento_id) and tipo_evento in apuestas[user_id][ev_id]:
                        tiene_apuesta = True
                        break
            
            # Si no tiene apuesta, asignar Q2 como apuesta por defecto
            if not tiene_apuesta:
                usuarios_sin_apuesta.append(user_id)
                guardar_apuesta(user_id, evento_id, tipo_evento, q2_resultados)
                contador += 1
        
        logger.info(f"Se han asignado apuestas Q2 por defecto a {contador} usuarios")
        if contador > 0:
            logger.debug(f"Usuarios sin apuesta: {usuarios_sin_apuesta}")
        
        # Guardar en diccionario de fallbacks para referencia
        if evento_id not in apuestas_q2_fallback:
            apuestas_q2_fallback[evento_id] = {}
        apuestas_q2_fallback[evento_id][tipo_evento] = q2_resultados
        
        return contador > 0
    except Exception as e:
        logger.error(f"Error al asignar apuestas Q2 por defecto: {e}", exc_info=True)
        return False

async def forzar_apuestas_q2_command(update, context):
    """Comando /forzar_apuestas_q2: Asigna manualmente las apuestas Q2 por defecto."""
    # Verificar si el usuario tiene permisos de administrador
   
    eventos = obtener_eventos_desde_gsheet()
    evento_proximo = obtener_evento_mas_proximo(eventos)
    
    if not evento_proximo:
        await update.message.reply_text("No hay eventos próximos para asignar apuestas Q2.")
        return
    
    evento_id = evento_proximo['event_id']
    q2_resultados = obtener_q2_resultados(evento_id)
    
    if not q2_resultados or '' in q2_resultados or None in q2_resultados:
        await update.message.reply_text(f"No hay resultados Q2 completos para el evento {evento_proximo['hashtag']}.")
        return
    
    await update.message.reply_text("Procesando asignación de apuestas Q2... Por favor espera.")
    
    # Forzar asignación para Sprint
    sprint_count = asignar_apuestas_q2_por_defecto(evento_id, 'sprint', forzar=True)
    # Forzar asignación para Carrera
    carrera_count = asignar_apuestas_q2_por_defecto(evento_id, 'carrera', forzar=True)
    
    mensaje = f"✅ *Asignación de apuestas Q2 por defecto*\n\n"
    mensaje += f"Evento: *{escape_markdown_v2(evento_proximo['hashtag'])}*\n\n"
    mensaje += f"• Sprint Race: {sprint_count} apuestas asignadas\n"
    mensaje += f"• Carrera: {carrera_count} apuestas asignadas\n\n"
    mensaje += f"Podio Q2 usado:\n"
    mensaje += f"🥇 1º: *{escape_markdown_v2(q2_resultados[0])}*\n"
    mensaje += f"🥈 2º: *{escape_markdown_v2(q2_resultados[1])}*\n"
    mensaje += f"🥉 3º: *{escape_markdown_v2(q2_resultados[2])}*"
    
    await update.message.reply_markdown_v2(mensaje)

async def main():
    """Inicia el bot y sus manejadores de comandos."""
    # Configurar persistencia
    persistence = PicklePersistence(filepath="bot_data.pickle")
    
    try:
        # Cargar apuestas desde Google Sheets al iniciar
        global apuestas
        apuestas_cargadas = cargar_apuestas_desde_gsheet()
        if apuestas_cargadas:
            apuestas = apuestas_cargadas
            print(f"Se cargaron {sum(len(eventos) for chat in apuestas.values() for eventos in chat.values())} apuestas desde Google Sheets")
    except Exception as e:
        print(f"Error al cargar apuestas iniciales: {e}")
    
    # Inicializar la aplicación con persistencia
    application = Application.builder()\
        .token(TELEGRAM_BOT_TOKEN)\
        .persistence(persistence)\
        .build()
    
    # Comandos básicos - estos se manejan directamente
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("proximo_evento", proximo_evento_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("ver_apuesta", ver_apuesta_command))
    application.add_handler(CommandHandler("podio_q2", podio_q2_command))
    application.add_handler(CommandHandler("ranking", ranking_command))
    application.add_handler(CommandHandler("forzar_apuestas_q2", forzar_apuestas_q2_command))  # Nuevo comando

    # Registrar conversation handlers con prioridad más alta
    application.add_handler(conv_handler_sprint)
    application.add_handler(conv_handler_carrera)
    application.add_handler(conv_handler_ejecutar_sprint)
    application.add_handler(conv_handler_ejecutar_carrera)
    
    # Añadir manejadores directos como fallback para debugging
    application.add_handler(CommandHandler("apostar_sprint", direct_apostar_sprint))
    application.add_handler(CommandHandler("apostar_carrera", direct_apostar_carrera))
    
    # Agregar debug handler para capturar mensajes no manejados
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, debug_message_handler))
    application.add_handler(MessageHandler(filters.COMMAND, lambda u, c: logger.info(f"Unhandled command: {u.message.text}")))

    # Manejador de errores
    application.add_error_handler(error)

    print("Bot iniciado. Presiona Ctrl+C para detener.")
    
    # Iniciar la aplicación y cerrar la aplicación correctamente cuando se termine
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Mantener el proceso en ejecución hasta que se reciba una señal de terminación
    try:
        await asyncio.Event().wait()  # Espera indefinidamente
    except (KeyboardInterrupt, SystemExit):
        # Si se recibe Ctrl+C o una excepción de salida del sistema
        pass
    finally:
        # Asegurar la limpieza adecuada cuando el programa termina
        await application.stop()
        await application.updater.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Manejar Ctrl+C aquí también para asegurar salida limpia
        print("\nDeteniendo el bot...")
