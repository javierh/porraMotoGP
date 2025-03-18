import mysql.connector
from datetime import datetime, timedelta, timezone
import pytz
import math
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import os

TIMEZONE = pytz.timezone('Europe/Madrid')

def get_mysql_connection():
    """Establece conexión con la base de datos MySQL."""
    host = os.getenv('MYSQL_HOST')
    user = os.getenv('MYSQL_USER')
    password = os.getenv('MYSQL_PASSWORD')
    database = os.getenv('MYSQL_DATABASE')
    
    # Verificar que todas las variables de entorno necesarias estén definidas
    if not host or not user or not password or not database:
        missing = []
        if not host: missing.append('MYSQL_HOST')
        if not user: missing.append('MYSQL_USER')
        if not password: missing.append('MYSQL_PASSWORD')
        if not database: missing.append('MYSQL_DATABASE')
        error_msg = f"Faltan variables de entorno MySQL: {', '.join(missing)}"
        print(error_msg)
        raise ValueError(error_msg)
    
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        print(f"Conexión exitosa a MySQL: {host}")
        return connection
    except mysql.connector.Error as e:
        print(f"Error al conectar a MySQL: {e}")
        print(f"Parámetros de conexión: host={host}, user={user}, database={database}")
        raise e

def obtener_sesiones_desde_mysql():
    """Obtiene y procesa los datos de sesiones desde MySQL."""
    connection = None
    cursor = None
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Sesiones")
        data_sesiones = cursor.fetchall()
        sesiones = []
        for row in data_sesiones:
            try:
                # Handle ISO format dates with timezone information
                date_start = None
                date_end = None
                
                if row['date_start']:
                    try:
                        date_start = datetime.fromisoformat(row['date_start'].replace('Z', '+00:00')).astimezone(TIMEZONE)
                    except ValueError:
                        print(f"Error parsing date_start: {row['date_start']}")
                
                if row['date_end']:
                    try:
                        date_end = datetime.fromisoformat(row['date_end'].replace('Z', '+00:00')).astimezone(TIMEZONE)
                    except ValueError:
                        print(f"Error parsing date_end: {row['date_end']}")

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
                print(f"Error al procesar fila en MySQL (Sesiones): {row}. Error: {e}")
        return sesiones
    except Exception as e:
        print(f"Error al obtener sesiones desde MySQL: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def obtener_eventos_desde_mysql():
    """Obtiene y procesa los datos de eventos desde MySQL."""
    connection = None
    cursor = None
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Circuitos")
        data_eventos = cursor.fetchall()
        eventos = []
        for row in data_eventos:
            try:
                # Handle ISO format dates with timezone information
                date_start = None
                date_end = None
                
                if row['date_start']:
                    try:
                        date_start = datetime.fromisoformat(row['date_start'].replace('Z', '+00:00')).astimezone(TIMEZONE)
                    except ValueError:
                        print(f"Error parsing date_start: {row['date_start']}")
                
                if row['date_end']:
                    try:
                        date_end = datetime.fromisoformat(row['date_end'].replace('Z', '+00:00')).astimezone(TIMEZONE)
                    except ValueError:
                        print(f"Error parsing date_end: {row['date_end']}")

                evento = {
                    'event_id': row['event_id'],
                    'circuit_name': row['circuit_name'],
                    'date_start': date_start,
                    'date_end': date_end,
                    'hashtag': row['hashtag']
                }
                eventos.append(evento)
            except ValueError as e:
                print(f"Error al procesar fila en MySQL (Circuitos): {row}. Error: {e}")
        return eventos
    except Exception as e:
        print(f"Error al obtener eventos desde MySQL: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def obtener_pilotos_desde_mysql():
    """Obtiene la lista de nombres de pilotos desde MySQL."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT rider_name FROM Pilotos")
        data_pilotos = cursor.fetchall()
        pilotos_nombres = [row['rider_name'] for row in data_pilotos if row['rider_name']]
        return pilotos_nombres
    except Exception as e:
        print(f"Error al obtener pilotos desde MySQL: {e}")
        return []
    finally:
        cursor.close()
        connection.close()

def guardar_usuario_en_mysql(user):
    """Guarda o actualiza la información de un usuario en MySQL."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO Jugones (chat_id, username, first_name, last_name, join_date)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                username = VALUES(username),
                first_name = VALUES(first_name),
                last_name = VALUES(last_name),
                join_date = VALUES(join_date)
        """, (user.id, user.username or '', user.first_name or '', user.last_name or '', datetime.now(TIMEZONE).isoformat()))
        connection.commit()
        return True
    except Exception as e:
        print(f"Error al guardar usuario en MySQL: {e}")
        return False
    finally:
        cursor.close()
        connection.close()

def guardar_apuesta_en_mysql(chat_id, evento_id, tipo_evento, podio):
    """Guarda una apuesta en MySQL."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO Apuestas (circuit_id, user_id, hashtag, posicion1, posicion2, posicion3, evento, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                posicion1 = VALUES(posicion1),
                posicion2 = VALUES(posicion2),
                posicion3 = VALUES(posicion3),
                timestamp = VALUES(timestamp)
        """, (evento_id, chat_id, '', podio[0], podio[1], podio[2], tipo_evento, datetime.now(TIMEZONE).isoformat()))
        connection.commit()
        return True
    except Exception as e:
        print(f"Error al guardar apuesta en MySQL: {e}")
        return False
    finally:
        cursor.close()
        connection.close()

def cargar_apuestas_desde_mysql():
    """Carga todas las apuestas desde MySQL."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Apuestas")
        data = cursor.fetchall()
        apuestas_cargadas = {}
        for row in data:
            try:
                circuit_id = row.get('circuit_id')
                user_id = int(row.get('user_id', 0))
                tipo_evento = row.get('evento')
                podio = [row.get('posicion1', ''), row.get('posicion2', ''), row.get('posicion3', '')]
                if user_id not in apuestas_cargadas:
                    apuestas_cargadas[user_id] = {}
                if circuit_id not in apuestas_cargadas[user_id]:
                    apuestas_cargadas[user_id][circuit_id] = {}
                apuestas_cargadas[user_id][circuit_id][tipo_evento] = podio
            except (ValueError, KeyError) as e:
                print(f"Error al procesar fila de apuesta: {e}, fila: {row}")
        return apuestas_cargadas
    except Exception as e:
        print(f"Error al cargar apuestas desde MySQL: {e}")
        return {}
    finally:
        cursor.close()
        connection.close()

def obtener_deadline_sesion(evento_id, tipo_evento):
    """Obtiene la fecha y hora límite para apostar desde la tabla Sesiones."""
    try:
        sesiones = obtener_sesiones_desde_mysql()
        tipo_sesion = evento_interno_a_gsheet(tipo_evento)
        for sesion in sesiones:
            if str(sesion.get('circuit_id', '')) == str(evento_id) and sesion.get('shortname') == tipo_sesion:
                return sesion.get('date_start')
        print(f"No se encontró información de la sesión {tipo_sesion} para el evento {evento_id}")
        return None
    except Exception as e:
        print(f"Error al obtener deadline desde Sesiones: {e}")
        return None

def obtener_evento_mas_proximo(eventos):
    """Determina el evento actualmente en curso o el próximo a comenzar."""
    ahora = datetime.now(TIMEZONE)
    evento_en_curso = None
    for evento in eventos:
        if (evento['date_start'] and evento['date_end'] and 
            evento['date_start'] <= ahora <= evento['date_end']):
            return evento
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
    if not evento:
        return False
    ahora = datetime.now(TIMEZONE)
    deadline = obtener_deadline_sesion(evento['event_id'], tipo_evento)
    if not deadline:
        if not evento['date_start']:
            return False
        if tipo_evento == 'sprint' or tipo_evento == 'SPR':
            return ahora < evento['date_start'] - timedelta(minutes=45)
        else:
            return ahora < evento['date_start'] - timedelta(minutes=15)
    return ahora < deadline

def format_datetime_para_usuario(datetime_obj):
    """Formatea un objeto datetime para mostrar al usuario."""
    if not datetime_obj:
        return "No especificado"
    return datetime_obj.strftime('%d-%m-%Y %H:%M %Z')

def escape_markdown_v2(text):
    """Escapa caracteres especiales para Markdown V2 de Telegram."""
    if not text:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text

def crear_teclado_pilotos(pilotos, prefix, page=0):
    """Crea un teclado inline con botones para cada piloto."""
    total_pages = math.ceil(len(pilotos) / MAX_BUTTONS_PER_PAGE)
    start_idx = page * MAX_BUTTONS_PER_PAGE
    end_idx = min(start_idx + MAX_BUTTONS_PER_PAGE, len(pilotos))
    pilotos_page = pilotos[start_idx:end_idx]
    keyboard = []
    for i in range(0, len(pilotos_page), BUTTONS_PER_ROW):
        row = []
        for j in range(BUTTONS_PER_ROW):
            if i + j < len(pilotos_page):
                piloto = pilotos_page[i + j]
                callback_data = f"{prefix}{PILOTO_CALLBACK_PREFIX}{piloto}"
                row.append(InlineKeyboardButton(piloto, callback_data=callback_data))
        keyboard.append(row)
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"{prefix}{PAGE_CALLBACK_PREFIX}{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"{prefix}{PAGE_CALLBACK_PREFIX}{page+1}"))
        keyboard.append(nav_row)
    return InlineKeyboardMarkup(keyboard)

def calcular_puntos_apuesta(apuesta, resultado_oficial, tipo_evento):
    """Calcula los puntos obtenidos en una apuesta según el resultado oficial."""
    if not apuesta or not resultado_oficial:
        return 0
    tipo_evento_interno = evento_gsheet_a_interno(tipo_evento)
    if tipo_evento_interno == 'sprint':
        puntos_por_posicion = [12, 9, 7]
    else:
        puntos_por_posicion = [25, 20, 16]
    puntos_totales = 0
    for i in range(3):
        piloto_apostado = apuesta[i] if i < len(apuesta) else None
        piloto_oficial = resultado_oficial[i] if i < len(resultado_oficial) else None
        if piloto_apostado and piloto_oficial:
            if piloto_apostado == piloto_oficial:
                puntos_totales += puntos_por_posicion[i] * 2
            elif piloto_apostado in resultado_oficial:
                puntos_totales += puntos_por_posicion[resultado_oficial.index(piloto_apostado)]
    return puntos_totales

def actualizar_ranking_en_mysql(chat_id, puntos_circuito, evento_id):
    """Actualiza la puntuación del usuario en la tabla Ranking de MySQL."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO Ranking (user_id, score, points_last_circuit)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                score = score + VALUES(score),
                points_last_circuit = VALUES(points_last_circuit)
        """, (chat_id, puntos_circuito, puntos_circuito))
        connection.commit()
        return True
    except Exception as e:
        print(f"Error al actualizar ranking en MySQL: {e}")
        return False
    finally:
        cursor.close()
        connection.close()

def calcular_y_actualizar_puntos_del_evento(evento_id, tipo_evento):
    """Calcula puntos para todos los usuarios y actualiza el ranking después de un evento oficial."""
    if evento_id not in resultados_oficiales or tipo_evento not in resultados_oficiales[evento_id]:
        print(f"No se encontró resultado oficial para {tipo_evento} en evento {evento_id}")
        return False
    resultado_oficial = resultados_oficiales[evento_id][tipo_evento]
    puntos_circuito_por_usuario = {}
    for user_id, eventos_usuario in apuestas.items():
        for ev_id in eventos_usuario:
            if str(ev_id) == str(evento_id) and tipo_evento in eventos_usuario[ev_id]:
                apuesta_usuario = eventos_usuario[ev_id][tipo_evento]
                puntos = calcular_puntos_apuesta(apuesta_usuario, resultado_oficial, tipo_evento)
                if user_id not in puntos_circuito_por_usuario:
                    puntos_circuito_por_usuario[user_id] = 0
                puntos_circuito_por_usuario[user_id] += puntos
                print(f"Usuario {user_id}: {puntos} puntos en {tipo_evento}")
    for user_id, puntos in puntos_circuito_por_usuario.items():
        actualizar_ranking_en_mysql(user_id, puntos, evento_id)
    return True

def obtener_usuarios_registrados():
    """Obtiene la lista de usuarios registrados en la tabla 'Jugones'."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT chat_id FROM Jugones")
        data_usuarios = cursor.fetchall()
        usuarios = [int(row['chat_id']) for row in data_usuarios if 'chat_id' in row and row['chat_id']]
        print(f"Se encontraron {len(usuarios)} usuarios registrados")
        return usuarios
    except Exception as e:
        print(f"Error al obtener usuarios registrados: {e}")
        return []
    finally:
        cursor.close()
        connection.close()

def obtener_q2_resultados(evento_id):
    """Obtiene los resultados de Q2 para un evento específico desde la tabla 'Q2'."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Q2 WHERE circuit_id = %s", (evento_id,))
        fila = cursor.fetchone()
        if fila:
            result = [fila.get('posicion1', ''), fila.get('posicion2', ''), fila.get('posicion3', '')]
            print(f"Q2: Encontrados resultados para evento {evento_id}: {result}")
            return result
        print(f"Q2: No se encontraron resultados para el evento {evento_id}")
        return None
    except Exception as e:
        print(f"Error al obtener resultados Q2: {e}")
        return None
    finally:
        cursor.close()
        connection.close()

def asignar_apuestas_q2_por_defecto(evento_id, tipo_evento, forzar=False):
    """Asigna automáticamente las posiciones de Q2 como apuesta para los usuarios registrados que no hicieron una apuesta."""
    try:
        print(f"Iniciando asignación de Q2 para evento {evento_id}, tipo {tipo_evento}")
        eventos = obtener_eventos_desde_mysql()
        evento = next((e for e in eventos if str(e['event_id']) == str(evento_id)), None)
        if not evento:
            print(f"No se encontró el evento con ID {evento_id}")
            return False
        tipo_evento_gsheet = evento_interno_a_gsheet(tipo_evento)
        apuestas_abiertas = es_tiempo_apuesta_abierto(evento, tipo_evento)
        print(f"Las apuestas están {'abiertas' if apuestas_abiertas else 'cerradas'} para {evento['hashtag']} - {tipo_evento}")
        if apuestas_abiertas and not forzar:
            print(f"El tiempo para apostar en {tipo_evento} aún está abierto. No se asignan apuestas Q2.")
            return False
        q2_resultados = obtener_q2_resultados(evento_id)
        print(f"Resultados Q2 obtenidos para evento {evento_id}: {q2_resultados}")
        if not q2_resultados or '' in q2_resultados or None in q2_resultados:
            print(f"No hay resultados Q2 completos para el evento {evento_id}")
            return False
        usuarios = obtener_usuarios_registrados()
        print(f"Usuarios registrados: {len(usuarios)}")
        if not usuarios:
            print("No hay usuarios registrados")
            return False
        contador = 0
        usuarios_sin_apuesta = []
        for user_id in usuarios:
            tiene_apuesta = False
            if user_id in apuestas:
                for ev_id in apuestas[user_id]:
                    if str(ev_id) == str(evento_id) and tipo_evento in apuestas[user_id][ev_id]:
                        tiene_apuesta = True
                        break
            if not tiene_apuesta:
                usuarios_sin_apuesta.append(user_id)
                guardar_apuesta(user_id, evento_id, tipo_evento, q2_resultados)
                contador += 1
        print(f"Se han asignado apuestas Q2 por defecto a {contador} usuarios")
        if contador > 0:
            print(f"Usuarios sin apuesta: {usuarios_sin_apuesta}")
        if evento_id not in apuestas_q2_fallback:
            apuestas_q2_fallback[evento_id] = {}
        apuestas_q2_fallback[evento_id][tipo_evento] = q2_resultados
        return contador > 0
    except Exception as e:
        print(f"Error al asignar apuestas Q2 por defecto: {e}")
        return False

def evento_interno_a_gsheet(tipo_evento):
    """Convierte el tipo de evento del formato interno al usado en MySQL."""
    if tipo_evento == 'sprint':
        return 'SPR'
    elif tipo_evento == 'carrera':
        return 'RAC'
    return tipo_evento  # Si ya está en formato correcto o es desconocido, lo devuelve tal cual

def evento_gsheet_a_interno(tipo_evento):
    """Convierte el tipo de evento del formato de MySQL al formato interno."""
    if tipo_evento == 'SPR':
        return 'sprint'
    elif tipo_evento == 'RAC':
        return 'carrera'
    return tipo_evento  # Si ya está en formato correcto o es desconocido, lo devuelve tal cual

# Declarar las variables globales para que sean accesibles en todas las funciones
PILOTO_CALLBACK_PREFIX = "piloto_"
PAGE_CALLBACK_PREFIX = "page_"
BUTTONS_PER_ROW = 2  # Número de botones por fila
MAX_BUTTONS_PER_PAGE = 8  # Máximo de botones por página
