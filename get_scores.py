import gspread
from google.oauth2.service_account import Credentials
import logging
import sys
import os
import json
from datetime import datetime
import pytz

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("PuntosCalculator")

# Configuración
GOOGLE_SHEET_CREDENTIALS_FILE = './google_credentials.json'
GOOGLE_SHEET_URL = 'https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXXXXXXXXX'
TIMEZONE = pytz.timezone('Europe/Madrid')

# Puntuación por posición
PUNTOS_SPRINT = [12, 9, 7]  # Puntos para 1º, 2º, 3º en Sprint
PUNTOS_CARRERA = [25, 20, 16]  # Puntos para 1º, 2º, 3º en Carrera

def conectar_google_sheets():
    """Establece conexión con Google Sheets."""
    try:
        # Verificar si el archivo de credenciales existe
        if not os.path.exists(GOOGLE_SHEET_CREDENTIALS_FILE):
            logger.error(f"El archivo de credenciales no existe en la ruta: {os.path.abspath(GOOGLE_SHEET_CREDENTIALS_FILE)}")
            logger.error(f"Directorio actual: {os.getcwd()}")
            sys.exit(1)
            
        # Verificar que el archivo no esté vacío
        if os.path.getsize(GOOGLE_SHEET_CREDENTIALS_FILE) == 0:
            logger.error(f"El archivo de credenciales está vacío: {GOOGLE_SHEET_CREDENTIALS_FILE}")
            sys.exit(1)
            
        # Intentar leer el JSON para verificar su formato
        try:
            with open(GOOGLE_SHEET_CREDENTIALS_FILE, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as json_err:
            logger.error(f"El archivo de credenciales no contiene JSON válido: {json_err}")
            sys.exit(1)
            
        # Configurar la autenticación
        scopes = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            creds = Credentials.from_service_account_file(GOOGLE_SHEET_CREDENTIALS_FILE, scopes=scopes)
        except Exception as cred_err:
            logger.error(f"Error al cargar las credenciales: {cred_err}")
            sys.exit(1)
            
        try:
            gc = gspread.authorize(creds)
            spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
            logger.info("Conexión a Google Sheets establecida correctamente")
            return spreadsheet
        except gspread.exceptions.APIError as api_err:
            logger.error(f"Error de API de Google: {api_err}")
            sys.exit(1)
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"No se encontró la hoja de cálculo con la URL: {GOOGLE_SHEET_URL}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error inesperado al conectar a Google Sheets: {e}")
        sys.exit(1)

def obtener_resultados_oficiales(spreadsheet):
    """Obtiene los resultados oficiales de la hoja Resultados."""
    try:
        resultados_sheet = spreadsheet.worksheet('Resultados')
        data_resultados = resultados_sheet.get_all_records()
        
        # Organizar resultados por evento y tipo (SPR/RAC)
        resultados = {}
        for row in data_resultados:
            circuit_id = row.get('circuit_id')
            event_type = row.get('event_type')  # SPR o RAC
            finished = row.get('finished', 0)
            
            # Convertir finished a número si es posible (posición final)
            try:
                position = int(finished)
            except (ValueError, TypeError):
                # Si no es un número, podría ser 'DNF', 'DNS', etc.
                continue
                
            # Solo nos interesan los 3 primeros lugares
            if position <= 3:
                if circuit_id not in resultados:
                    resultados[circuit_id] = {}
                if event_type not in resultados[circuit_id]:
                    resultados[circuit_id][event_type] = {}
                
                # Guardamos el nombre del piloto en su posición
                resultados[circuit_id][event_type][position] = row.get('rider_name')
        
        # Convertir el diccionario a listas ordenadas de podio
        podios_oficiales = {}
        for circuit_id, events in resultados.items():
            podios_oficiales[circuit_id] = {}
            for event_type, positions in events.items():
                # Crear la lista de podio ordenada (posiciones 1, 2, 3)
                podio = [positions.get(1, ""), positions.get(2, ""), positions.get(3, "")]
                podios_oficiales[circuit_id][event_type] = podio
        
        return podios_oficiales
    except Exception as e:
        logger.error(f"Error al obtener resultados oficiales: {e}")
        return {}

def obtener_apuestas_usuarios(spreadsheet):
    """Obtiene las apuestas de los usuarios desde la hoja Apuestas."""
    try:
        apuestas_sheet = spreadsheet.worksheet('Apuestas')
        data_apuestas = apuestas_sheet.get_all_records()
        
        # Organizar apuestas por usuario, evento y tipo
        apuestas = {}
        for row in data_apuestas:
            circuit_id = row.get('circuit_id')
            user_id = row.get('user_id')
            evento = row.get('evento')  # SPR o RAC
            
            # Crear la lista de podio apostado
            podio = [
                row.get('posicion1', ''),
                row.get('posicion2', ''),
                row.get('posicion3', '')
            ]
            
            # Organizar en la estructura de datos
            if user_id not in apuestas:
                apuestas[user_id] = {}
            if circuit_id not in apuestas[user_id]:
                apuestas[user_id][circuit_id] = {}
                
            apuestas[user_id][circuit_id][evento] = podio
        
        return apuestas
    except Exception as e:
        logger.error(f"Error al obtener apuestas de usuarios: {e}")
        return {}

def calcular_puntos(apuesta, resultado_oficial, tipo_evento):
    """
    Calcula los puntos obtenidos en una apuesta según el resultado oficial.
    
    Reglas de puntuación:
    - Sprint: 1º=12pts, 2º=9pts, 3º=7pts
    - Carrera: 1º=25pts, 2º=20pts, 3º=16pts
    - Si acierta piloto y posición, puntos dobles
    """
    if not apuesta or not resultado_oficial:
        return 0
    
    # Definir puntos por posición según tipo de evento
    if tipo_evento == 'SPR':
        puntos_por_posicion = PUNTOS_SPRINT
    else:  # 'RAC'
        puntos_por_posicion = PUNTOS_CARRERA
    
    puntos_totales = 0
    
    # Revisar cada posición del podio
    for i in range(3):
        piloto_apostado = apuesta[i] if i < len(apuesta) else None
        piloto_oficial = resultado_oficial[i] if i < len(resultado_oficial) else None
        
        if piloto_apostado and piloto_oficial:
            # Si acierta piloto y posición exacta → puntos dobles
            if piloto_apostado == piloto_oficial:
                puntos_totales += puntos_por_posicion[i] * 2
                logger.debug(f"Acierto exacto en posición {i+1}: {piloto_apostado} = {puntos_por_posicion[i]*2} puntos")
            # Si el piloto apostado está en el podio pero en otra posición → puntos normales
            elif piloto_apostado in resultado_oficial:
                pos_real = resultado_oficial.index(piloto_apostado)
                puntos_totales += puntos_por_posicion[pos_real]
                logger.debug(f"Acierto de piloto {piloto_apostado} en otra posición ({pos_real+1}): {puntos_por_posicion[pos_real]} puntos")
    
    return puntos_totales

def actualizar_ranking_sheet(spreadsheet, puntuacion_por_usuario):
    """Actualiza o crea la hoja de Ranking con los puntos calculados."""
    try:
        # Intentar obtener la hoja de Ranking o crearla si no existe
        try:
            ranking_sheet = spreadsheet.worksheet('Ranking')
        except gspread.exceptions.WorksheetNotFound:
            ranking_sheet = spreadsheet.add_worksheet(title='Ranking', rows=100, cols=3)
            ranking_sheet.append_row(['user_id', 'score', 'points_last_circuit'])
            logger.info("Hoja de Ranking creada")
        
        # Obtener los datos actuales de la hoja
        datos_actuales = ranking_sheet.get_all_records()
        
        # Convertir a diccionario para fácil acceso
        ranking_actual = {int(row.get('user_id', 0)): {
            'score': int(row.get('score', 0)),
            'points_last_circuit': int(row.get('points_last_circuit', 0))
        } for row in datos_actuales}
        
        # Actualizar con la nueva puntuación
        for user_id, puntos in puntuacion_por_usuario.items():
            if user_id in ranking_actual:
                # Actualizar usuario existente
                score_previo = ranking_actual[user_id]['score']
                ranking_actual[user_id]['score'] = score_previo + puntos
                ranking_actual[user_id]['points_last_circuit'] = puntos
            else:
                # Añadir nuevo usuario
                ranking_actual[user_id] = {
                    'score': puntos,
                    'points_last_circuit': puntos
                }
        
        # Preparar los datos para actualizar la hoja
        datos_actualizados = [['user_id', 'score', 'points_last_circuit']]
        for user_id, datos in ranking_actual.items():
            datos_actualizados.append([
                str(user_id),
                str(datos['score']),
                str(datos['points_last_circuit'])
            ])
        
        # Limpiar la hoja y actualizarla con los nuevos datos
        ranking_sheet.clear()
        ranking_sheet.update('A1', datos_actualizados)
        
        logger.info(f"Ranking actualizado correctamente para {len(puntuacion_por_usuario)} usuarios")
        return True
    except Exception as e:
        logger.error(f"Error al actualizar la hoja de Ranking: {e}")
        return False

def obtener_usuarios_y_nombres(spreadsheet):
    """Obtiene la información de usuarios desde la hoja Jugones."""
    try:
        jugones_sheet = spreadsheet.worksheet('Jugones')
        datos_jugones = jugones_sheet.get_all_records()
        
        jugones_dict = {}
        for row in datos_jugones:
            user_id = int(row.get('chat_id', 0))
            username = row.get('username', '')
            first_name = row.get('first_name', '')
            nombre = username if username else first_name
            
            if nombre:
                jugones_dict[user_id] = nombre
            else:
                jugones_dict[user_id] = f"Usuario {user_id}"
        
        return jugones_dict
    except Exception as e:
        logger.error(f"Error al obtener información de usuarios: {e}")
        return {}

def main():
    """Función principal que ejecuta el cálculo de puntos."""
    logger.info("Iniciando cálculo de puntos...")
    
    # Conectar a Google Sheets
    spreadsheet = conectar_google_sheets()
    
    # Obtener resultados oficiales
    resultados_oficiales = obtener_resultados_oficiales(spreadsheet)
    if not resultados_oficiales:
        logger.error("No se encontraron resultados oficiales para calcular puntos.")
        return
    
    # Obtener apuestas de usuarios
    apuestas_usuarios = obtener_apuestas_usuarios(spreadsheet)
    if not apuestas_usuarios:
        logger.error("No se encontraron apuestas de usuarios para calcular puntos.")
        return
    
    # Obtener información de los usuarios
    info_usuarios = obtener_usuarios_y_nombres(spreadsheet)
    
    # Calcular puntos para cada usuario y evento
    puntos_por_usuario = {}
    detalles_por_usuario = {}
    
    for user_id, eventos in apuestas_usuarios.items():
        puntos_usuario = 0
        detalles_usuario = []
        
        for circuit_id, tipos_evento in eventos.items():
            if circuit_id in resultados_oficiales:
                for tipo_evento, apuesta in tipos_evento.items():
                    if tipo_evento in resultados_oficiales[circuit_id]:
                        resultado = resultados_oficiales[circuit_id][tipo_evento]
                        puntos = calcular_puntos(apuesta, resultado, tipo_evento)
                        
                        if puntos > 0:
                            puntos_usuario += puntos
                            nombre_evento = f"Circuit {circuit_id} - {tipo_evento}"
                            detalles_usuario.append(f"{nombre_evento}: {puntos} pts")
            
        if puntos_usuario > 0:
            puntos_por_usuario[user_id] = puntos_usuario
            detalles_por_usuario[user_id] = detalles_usuario
    
    # Actualizar la hoja de Ranking
    if puntos_por_usuario:
        actualizar_ranking_sheet(spreadsheet, puntos_por_usuario)
    
    # Mostrar un resumen por consola
    logger.info(f"Puntos calculados para {len(puntos_por_usuario)} usuarios")
    
    for user_id, puntos in sorted(puntos_por_usuario.items(), key=lambda x: x[1], reverse=True):
        nombre = info_usuarios.get(user_id, f"Usuario {user_id}")
        logger.info(f"{nombre} ({user_id}): {puntos} puntos")
        for detalle in detalles_por_usuario.get(user_id, []):
            logger.info(f"  - {detalle}")
    
    logger.info("Proceso de cálculo de puntos completado.")

if __name__ == "__main__":
    main()
