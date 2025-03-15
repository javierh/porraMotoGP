import gspread
from google.oauth2.service_account import Credentials
import logging
import sys
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("PuntosCalculator")

# Configuración
GOOGLE_SHEET_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEET_CREDENTIALS_FILE', './google_credentials.json')
GOOGLE_SHEET_URL = os.getenv('GOOGLE_SHEET_URL')
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Europe/Madrid'))

# Parse scoring from comma-separated values
PUNTOS_SPRINT = [int(p) for p in os.getenv('PUNTOS_SPRINT', '12,9,7').split(',')]
PUNTOS_CARRERA = [int(p) for p in os.getenv('PUNTOS_CARRERA', '25,20,16').split(',')]

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
        logger.info(f"Obtenidos {len(data_resultados)} registros de la hoja Resultados")
        
        # Mostrar una muestra de datos para depuración
        logger.info(f"Muestra de datos de resultados: {data_resultados[:2] if data_resultados else 'No hay datos'}")
        
        # Organizar resultados por evento y tipo (SPR/RAC)
        resultados = {}
        for row in data_resultados:
            # Imprimir cada fila para depuración
            logger.debug(f"Procesando fila de resultados: {row}")
            
            # Obtener IDs y datos clave - convertir a string para evitar problemas de tipo
            circuit_id = str(row.get('circuit_id', '')).strip()
            
            # En algunas hojas, event_name podría ser event_id o estar en diferentes columnas
            event_name = None
            if 'event_name' in row:
                event_name = str(row.get('event_name', '')).strip().upper()
            elif 'event_id' in row and 'SPR' in str(row.get('event_id', '')).upper():
                event_name = 'SPR'
            elif 'event_id' in row and 'RAC' in str(row.get('event_id', '')).upper():
                event_name = 'RAC'
            
            # Si no encuentro event_name, buscar en cualquier columna que contenga SPR o RAC
            if not event_name:
                for key, value in row.items():
                    if isinstance(value, str) and ('SPR' in value.upper() or 'RAC' in value.upper()):
                        event_name = 'SPR' if 'SPR' in value.upper() else 'RAC'
                        logger.info(f"Evento encontrado en columna alternativa {key}: {event_name}")
                        break
            
            if not event_name and 'event_type' in row:
                event_name = str(row.get('event_type', '')).strip().upper()
            
            # Si todavía no hay nombre de evento, no podemos procesar esta fila
            if not event_name:
                logger.warning(f"No se pudo determinar el tipo de evento en la fila: {row}")
                continue
                
            # Verificar la posición
            try:
                position_str = str(row.get('finished', '')).strip()
                # Intentar diferentes formatos de posición
                if position_str.isdigit():
                    position = int(position_str)
                else:
                    # Podría ser algo como "1st", "2nd", etc.
                    position_str = ''.join(c for c in position_str if c.isdigit())
                    position = int(position_str) if position_str.isdigit() else None
            except (ValueError, TypeError):
                logger.debug(f"Posición no numérica para {row.get('rider_name')}: {row.get('finished')}")
                continue
            
            # Solo nos interesan los 3 primeros lugares
            if position is None or position > 3:
                continue
                
            rider_name = str(row.get('rider_name', '')).strip()
            if not rider_name and 'name' in row:
                rider_name = str(row.get('name', '')).strip()
                
            if not circuit_id or not event_name or not rider_name:
                logger.warning(f"Datos incompletos en fila: circuit_id={circuit_id}, event_name={event_name}, rider_name={rider_name}")
                continue
            
            logger.info(f"Resultado oficial encontrado: Circuito {circuit_id}, Evento {event_name}, Pos {position}: {rider_name}")
            
            # Inicializar estructuras si no existen
            if circuit_id not in resultados:
                resultados[circuit_id] = {}
            if event_name not in resultados[circuit_id]:
                resultados[circuit_id][event_name] = {}
            
            # Guardamos el nombre del piloto en su posición
            resultados[circuit_id][event_name][position] = rider_name
        
        # Convertir el diccionario a listas ordenadas de podio
        podios_oficiales = {}
        for circuit_id, events in resultados.items():
            podios_oficiales[circuit_id] = {}
            for event_name, positions in events.items():
                # Crear la lista de podio ordenada (posiciones 1, 2, 3)
                podio = [
                    positions.get(1, ""), 
                    positions.get(2, ""), 
                    positions.get(3, "")
                ]
                
                # Solo guardar podios completos
                if all(podio):
                    podios_oficiales[circuit_id][event_name] = podio
                    logger.info(f"Podio oficial para {circuit_id} en {event_name}: {podio}")
                else:
                    logger.warning(f"Podio incompleto para {circuit_id} en {event_name}: {podio}")
        
        # Informar del total de podios encontrados
        total_podios = sum(len(events) for events in podios_oficiales.values())
        logger.info(f"Total de podios oficiales encontrados: {total_podios}")
        
        return podios_oficiales
    except Exception as e:
        logger.error(f"Error al obtener resultados oficiales: {e}", exc_info=True)
        return {}

def obtener_apuestas_usuarios(spreadsheet):
    """Obtiene las apuestas de los usuarios desde la hoja Apuestas."""
    try:
        apuestas_sheet = spreadsheet.worksheet('Apuestas')
        data_apuestas = apuestas_sheet.get_all_records()
        logger.info(f"Obtenidas {len(data_apuestas)} apuestas de usuarios")
        
        # Mostrar una muestra de datos para depuración
        logger.info(f"Muestra de datos de apuestas: {data_apuestas[:2] if data_apuestas else 'No hay datos'}")
        
        # Organizar apuestas por usuario, evento y tipo
        apuestas = {}
        for row in data_apuestas:
            logger.debug(f"Procesando fila de apuestas: {row}")
            
            try:
                # Convertir IDs a string para evitar problemas de comparación
                circuit_id = str(row.get('circuit_id', '')).strip()
                
                # Obtener user_id como entero
                user_id_str = str(row.get('user_id', '0')).strip()
                if not user_id_str.isdigit():
                    logger.warning(f"ID de usuario no numérico: {user_id_str}")
                    continue
                
                user_id = int(user_id_str)
                
                # Normalizar el tipo de evento (SPR o RAC)
                evento = str(row.get('evento', '')).strip().upper()
                if not evento:
                    # Intentar buscar en otras columnas
                    if 'tipo' in row:
                        evento = str(row.get('tipo', '')).strip().upper()
                    elif 'event_type' in row:
                        evento = str(row.get('event_type', '')).strip().upper()
                
                # Validar que sea SPR o RAC
                if evento not in ['SPR', 'RAC']:
                    logger.warning(f"Tipo de evento no válido: {evento}")
                    continue
                
                if not circuit_id or not evento:
                    logger.warning(f"Datos incompletos en apuesta: circuit_id={circuit_id}, evento={evento}")
                    continue
                
                # Crear la lista de podio apostado con normalización
                podio = [
                    str(row.get('posicion1', '')).strip(),
                    str(row.get('posicion2', '')).strip(),
                    str(row.get('posicion3', '')).strip()
                ]
                
                # Verificar que el podio esté completo
                if not all(podio):
                    logger.warning(f"Apuesta con podio incompleto: {podio}")
                    continue
                
                logger.info(f"Apuesta registrada: Usuario {user_id}, Circuito {circuit_id}, Evento {evento}, Podio: {podio}")
                
                # Organizar en la estructura de datos
                if user_id not in apuestas:
                    apuestas[user_id] = {}
                if circuit_id not in apuestas[user_id]:
                    apuestas[user_id][circuit_id] = {}
                    
                apuestas[user_id][circuit_id][evento] = podio
            except (ValueError, KeyError) as e:
                logger.error(f"Error al procesar apuesta: {e}, Fila: {row}")
        
        # Informar del total de apuestas procesadas
        total_apuestas = sum(sum(len(eventos) for eventos in circuitos.values()) for circuitos in apuestas.values())
        logger.info(f"Total de apuestas procesadas: {total_apuestas}")
        
        return apuestas
    except Exception as e:
        logger.error(f"Error al obtener apuestas de usuarios: {e}", exc_info=True)
        return {}

def calcular_puntos_apuesta(apuesta, resultado_oficial, tipo_evento):
    """
    Calcula los puntos obtenidos en una apuesta según el resultado oficial.
    
    Reglas de puntuación:
    - Sprint: 1º=12pts, 2º=9pts, 3º=7pts
    - Carrera: 1º=25pts, 2º=20pts, 3º=16pts
    - Si acierta piloto y posición, puntos dobles
    """
    if not apuesta or not resultado_oficial:
        logger.warning(f"No se puede calcular puntos: apuesta={apuesta}, resultado={resultado_oficial}")
        return 0
    
    # Definir puntos por posición según tipo de evento
    if tipo_evento == 'SPR':
        puntos_por_posicion = PUNTOS_SPRINT
    else:  # 'RAC'
        puntos_por_posicion = PUNTOS_CARRERA
    
    # Log detallado para depuración
    logger.info(f"Calculando puntos: Apuesta={apuesta}, Resultado={resultado_oficial}, Evento={tipo_evento}")
    
    puntos_totales = 0
    
    # Normalizar todos los nombres de pilotos (quitar espacios extra, mayúsculas, etc.)
    apuesta_normalizada = [p.strip().upper() for p in apuesta]
    resultado_normalizado = [p.strip().upper() for p in resultado_oficial]
    
    # Revisar cada posición del podio
    for i in range(3):
        piloto_apostado = apuesta_normalizada[i] if i < len(apuesta_normalizada) else None
        piloto_oficial = resultado_normalizado[i] if i < len(resultado_normalizado) else None
        
        if piloto_apostado and piloto_oficial:
            # Si acierta piloto y posición exacta → puntos dobles
            if piloto_apostado == piloto_oficial:
                puntos_ganados = puntos_por_posicion[i] * 2
                puntos_totales += puntos_ganados
                logger.info(f"Acierto exacto en posición {i+1}: {apuesta[i]} = {puntos_ganados} puntos")
            # Si el piloto apostado está en el podio pero en otra posición → puntos normales
            elif piloto_apostado in resultado_normalizado:
                pos_real = resultado_normalizado.index(piloto_apostado)
                puntos_ganados = puntos_por_posicion[pos_real]
                puntos_totales += puntos_ganados
                logger.info(f"Acierto de piloto {apuesta[i]} en otra posición ({pos_real+1}): {puntos_ganados} puntos")
    
    logger.info(f"Total puntos calculados: {puntos_totales}")
    return puntos_totales

def actualizar_ranking_en_gsheet(spreadsheet, puntuacion_por_usuario):
    """Actualiza o crea la hoja de Ranking con los puntos calculados."""
    try:
        # Intentar obtener la hoja de Ranking o crearla si no existe
        try:
            ranking_sheet = spreadsheet.worksheet('Ranking')
            logger.info("Hoja de Ranking encontrada, obteniendo datos actuales")
        except gspread.exceptions.WorksheetNotFound:
            logger.info("Creando nueva hoja de Ranking")
            ranking_sheet = spreadsheet.add_worksheet(title='Ranking', rows=100, cols=3)
            ranking_sheet.append_row(['user_id', 'score', 'points_last_circuit'])
            logger.info("Hoja de Ranking creada")
        
        # Obtener los datos actuales de la hoja
        datos_actuales = ranking_sheet.get_all_records()
        logger.info(f"Obtenidos {len(datos_actuales)} registros de ranking actuales")
        
        # Convertir a diccionario para fácil acceso
        ranking_actual = {}
        for row in datos_actuales:
            try:
                user_id_str = str(row.get('user_id', '0'))
                if user_id_str.isdigit():
                    user_id = int(user_id_str)
                    ranking_actual[user_id] = {
                        'score': int(str(row.get('score', '0')).replace(',', '')),
                        'points_last_circuit': int(str(row.get('points_last_circuit', '0')).replace(',', ''))
                    }
            except (ValueError, TypeError) as e:
                logger.error(f"Error al procesar fila de ranking: {e}, fila: {row}")
        
        # Actualizar con la nueva puntuación
        usuarios_actualizados = set()
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
            usuarios_actualizados.add(user_id)
            logger.info(f"Ranking actualizado para usuario {user_id}: +{puntos} puntos")
        
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
        
        logger.info(f"Ranking actualizado correctamente para {len(usuarios_actualizados)} usuarios")
        return True
    except Exception as e:
        logger.error(f"Error al actualizar la hoja de Ranking: {e}", exc_info=True)
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

def obtener_circuitos_desde_resultados(spreadsheet):
    """Obtiene información de circuitos desde la hoja 'Resultados' para reemplazar la hoja 'Circuitos'."""
    try:
        resultados_sheet = spreadsheet.worksheet('Resultados')
        data_resultados = resultados_sheet.get_all_records()
        
        # Agrupar por circuit_id y obtener información única de circuitos
        circuitos = {}
        for row in data_resultados:
            circuit_id = str(row.get('circuit_id', '')).strip()
            if circuit_id and circuit_id not in circuitos:
                circuit_name = row.get('circuit_name', '')
                if not circuit_name:
                    # Intentar encontrar el nombre en otras columnas
                    for key, value in row.items():
                        if 'name' in key.lower() and isinstance(value, str) and value:
                            circuit_name = value
                            break
                
                circuitos[circuit_id] = {
                    'circuit_id': circuit_id,
                    'circuit_name': circuit_name or circuit_id
                }
        
        logger.info(f"Información de {len(circuitos)} circuitos extraída de la hoja Resultados")
        return list(circuitos.values())
    except Exception as e:
        logger.error(f"Error al obtener información de circuitos: {e}", exc_info=True)
        return []

def obtener_mapeo_circuitos(spreadsheet):
    """
    Crea un mapeo entre diferentes IDs de circuito basado en nombres de circuito o eventos.
    Esto soluciona problemas de IDs inconsistentes entre las hojas de apuestas y resultados.
    """
    try:
        # Intentar obtener datos de todas las hojas relevantes para crear un mapeo completo
        mapeo_circuitos = {}
        mapeo_por_nombre = {}
        mapeo_por_hashtag = {}
        
        # Primero desde la hoja de Resultados
        try:
            resultados_sheet = spreadsheet.worksheet('Resultados')
            data_resultados = resultados_sheet.get_all_records()
            
            # Mapear circuit_id -> circuit_name
            for row in data_resultados:
                circuit_id = str(row.get('circuit_id', '')).strip()
                circuit_name = str(row.get('circuit_name', '')).strip()
                
                if circuit_id and circuit_name:
                    if circuit_name not in mapeo_por_nombre:
                        mapeo_por_nombre[circuit_name] = []
                    if circuit_id not in mapeo_por_nombre[circuit_name]:
                        mapeo_por_nombre[circuit_name].append(circuit_id)
            
            logger.info(f"Mapeo por nombre de circuito creado con {len(mapeo_por_nombre)} circuitos")
        except Exception as e:
            logger.error(f"Error al obtener datos de Resultados para mapeo: {e}")
        
        # Luego desde la hoja de Apuestas
        try:
            apuestas_sheet = spreadsheet.worksheet('Apuestas')
            data_apuestas = apuestas_sheet.get_all_records()
            
            # Mapear circuit_id -> hashtag
            for row in data_apuestas:
                circuit_id = str(row.get('circuit_id', '')).strip()
                hashtag = str(row.get('hashtag', '')).strip()
                
                if circuit_id and hashtag:
                    if hashtag not in mapeo_por_hashtag:
                        mapeo_por_hashtag[hashtag] = []
                    if circuit_id not in mapeo_por_hashtag[hashtag]:
                        mapeo_por_hashtag[hashtag].append(circuit_id)
            
            logger.info(f"Mapeo por hashtag creado con {len(mapeo_por_hashtag)} hashtags")
        except Exception as e:
            logger.error(f"Error al obtener datos de Apuestas para mapeo: {e}")
        
        # Intentar mapear apuestas con resultados
        for nombre, ids_resultado in mapeo_por_nombre.items():
            for hashtag, ids_apuesta in mapeo_por_hashtag.items():
                # Intentar relacionar a través de similitudes en nombres/hashtags
                if nombre.lower() in hashtag.lower() or hashtag.lower() in nombre.lower():
                    logger.info(f"Posible coincidencia: {nombre} <-> {hashtag}")
                    
                    for id_apuesta in ids_apuesta:
                        for id_resultado in ids_resultado:
                            # Agregar mapeos en ambas direcciones
                            mapeo_circuitos[id_apuesta] = id_resultado
                            mapeo_circuitos[id_resultado] = id_apuesta
        
        # Mapeo directo para IDs idénticos
        for nombre, ids in mapeo_por_nombre.items():
            for id_circuito in ids:
                mapeo_circuitos[id_circuito] = id_circuito
                
        for hashtag, ids in mapeo_por_hashtag.items():
            for id_circuito in ids:
                mapeo_circuitos[id_circuito] = id_circuito
        
        # Si después de los intentos automáticos seguimos sin mapeos completos,
        # agregar algunos mapeos manuales conocidos
        mapeos_manuales = {
            '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b': 'a8bd93f8-8e7e-4669-ae1c-1f3f5156b4e7',
            'a8bd93f8-8e7e-4669-ae1c-1f3f5156b4e7': '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b',
            '536d88a0-b7b9-4312-a5f1-f196e8228991': '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b',
            '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b': '536d88a0-b7b9-4312-a5f1-f196e8228991'
        }
        
        for origen, destino in mapeos_manuales.items():
            if origen not in mapeo_circuitos:
                mapeo_circuitos[origen] = destino
                logger.info(f"Añadido mapeo manual: {origen} -> {destino}")
        
        # Información para debug
        logger.info(f"Mapeo de circuitos creado con {len(mapeo_circuitos)} entradas")
        for origen, destino in mapeo_circuitos.items():
            logger.debug(f"Mapeo: {origen} -> {destino}")
            
        return mapeo_circuitos
    except Exception as e:
        logger.error(f"Error al crear mapeo de circuitos: {e}", exc_info=True)
        # Devolver al menos los mapeos manuales como fallback
        return {
            '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b': 'a8bd93f8-8e7e-4669-ae1c-1f3f5156b4e7',
            'a8bd93f8-8e7e-4669-ae1c-1f3f5156b4e7': '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b',
            '536d88a0-b7b9-4312-a5f1-f196e8228991': '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b',
            '0ecbb0a9-a732-4c4f-9a3c-9e5628defa3b': '536d88a0-b7b9-4312-a5f1-f196e8228991'
        }

def main():
    """Función principal que ejecuta el cálculo de puntos."""
    logger.info("Iniciando cálculo de puntos...")
    
    # Aumentar el nivel de logging para ver más detalles
    logger.setLevel(logging.INFO)
    
    # Conectar a Google Sheets
    spreadsheet = conectar_google_sheets()
    
    # Obtener el mapeo de circuitos primero
    logger.info("Creando mapeo de IDs de circuito...")
    mapeo_circuitos = obtener_mapeo_circuitos(spreadsheet)
    
    # Obtener resultados oficiales
    logger.info("Obteniendo resultados oficiales...")
    resultados_oficiales = obtener_resultados_oficiales(spreadsheet)
    if not resultados_oficiales:
        logger.error("No se encontraron resultados oficiales para calcular puntos.")
        return
    
    # Obtener circuitos desde resultados para tener información completa
    circuitos = obtener_circuitos_desde_resultados(spreadsheet)
    logger.info(f"Circuitos encontrados: {len(circuitos)}")
    
    # Obtener apuestas de usuarios
    logger.info("Obteniendo apuestas de usuarios...")
    apuestas_usuarios = obtener_apuestas_usuarios(spreadsheet)
    if not apuestas_usuarios:
        logger.error("No se encontraron apuestas de usuarios para calcular puntos.")
        return
    
    # Obtener información de los usuarios
    info_usuarios = obtener_usuarios_y_nombres(spreadsheet)
    
    # Detallar la estructura de resultados para depuración
    for circuit_id, eventos in resultados_oficiales.items():
        for tipo_evento, resultado in eventos.items():
            logger.info(f"Resultado oficial para circuito {circuit_id}, evento {tipo_evento}: {resultado}")
    
    # Calcular puntos para cada usuario y evento
    logger.info("Calculando puntos...")
    puntos_por_usuario = {}
    detalles_por_usuario = {}
    
    for user_id, eventos_usuario in apuestas_usuarios.items():
        logger.info(f"Procesando apuestas del usuario {user_id}")
        puntos_usuario = 0
        detalles_usuario = []
        
        for circuit_id, tipos_evento in eventos_usuario.items():
            logger.info(f"Procesando circuito {circuit_id} para usuario {user_id}")
            
            # Buscar el circuit_id en los resultados, usando el mapeo si es necesario
            circuit_ids_a_verificar = [circuit_id]
            
            # Si hay un mapeo para este ID, añadirlo a la lista de IDs a verificar
            if circuit_id in mapeo_circuitos:
                circuit_ids_a_verificar.append(mapeo_circuitos[circuit_id])
                logger.info(f"Usando mapeo de circuito: {circuit_id} -> {mapeo_circuitos[circuit_id]}")
            
            # Ver si alguno de los IDs mapeados tiene resultados
            for circuit_id_verificar in circuit_ids_a_verificar:
                if circuit_id_verificar in resultados_oficiales:
                    logger.info(f"Encontrados resultados para el circuito mapeado {circuit_id_verificar}")
                    
                    for tipo_evento, apuesta in tipos_evento.items():
                        logger.info(f"Procesando evento {tipo_evento} para usuario {user_id}, circuito {circuit_id}")
                        
                        # Verificar si el tipo de evento existe en los resultados de este circuito
                        if tipo_evento in resultados_oficiales[circuit_id_verificar]:
                            resultado = resultados_oficiales[circuit_id_verificar][tipo_evento]
                            puntos = calcular_puntos_apuesta(apuesta, resultado, tipo_evento)
                            
                            if puntos > 0:
                                puntos_usuario += puntos
                                nombre_evento = f"{circuit_id} - {tipo_evento}"
                                detalles_usuario.append(f"{nombre_evento}: {puntos} pts")
                                logger.info(f"Usuario {user_id} suma {puntos} puntos por {tipo_evento} en circuito {circuit_id}")
                        else:
                            logger.warning(f"No hay resultados para el evento {tipo_evento} en el circuito {circuit_id_verificar}")
                    
                    # Si encontramos resultados para este ID, no seguimos verificando otros IDs
                    break
            else:
                # Este else corresponde al for, se ejecuta si no hizo break (no encontró resultados)
                logger.warning(f"No hay resultados para ninguno de los IDs mapeados del circuito {circuit_id}")
        
        if puntos_usuario > 0:
            puntos_por_usuario[user_id] = puntos_usuario
            detalles_por_usuario[user_id] = detalles_usuario
    
    # Actualizar la hoja de Ranking
    if puntos_por_usuario:
        logger.info(f"Actualizando ranking para {len(puntos_por_usuario)} usuarios")
        actualizar_ranking_en_gsheet(spreadsheet, puntos_por_usuario)
    else:
        logger.warning("No se calcularon puntos para ningún usuario")
    
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
