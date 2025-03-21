import sys
import logging
import datetime
import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import json

# Cargar variables de entorno
load_dotenv()

# Configurar logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("apuestas_automaticas.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Variables de configuración
GOOGLE_SHEET_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEET_CREDENTIALS_FILE', './google_credentials.json')
GOOGLE_SHEET_URL = os.getenv('GOOGLE_SHEET_URL')

# Configuración de Google Sheets
def conectar_google_sheets():
    """Establece conexión con Google Sheets API"""
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

def obtener_jugadores_sin_apuesta(spreadsheet, carrera_id):
    """Obtiene los jugadores que no han realizado apuesta para la carrera actual"""
    try:
        # Abrir hoja de jugadores
        jugadores_sheet = spreadsheet.worksheet('Jugadores')
        jugadores_data = jugadores_sheet.get_all_records()
        
        # Filtrar jugadores activos
        jugadores_activos = [j for j in jugadores_data if j.get('activo', True)]
        
        # Abrir hoja de apuestas
        apuestas_sheet = spreadsheet.worksheet('Apuestas')
        apuestas_data = apuestas_sheet.get_all_records()
        
        # Filtrar apuestas de la carrera actual
        apuestas_carrera = [a for a in apuestas_data if str(a.get('carrera_id')) == str(carrera_id)]
        
        # Jugadores con apuestas en esta carrera
        jugadores_con_apuestas = set(str(a.get('jugador_id')) for a in apuestas_carrera)
        
        # Jugadores sin apuestas
        jugadores_sin_apuesta = [j for j in jugadores_activos if str(j.get('id')) not in jugadores_con_apuestas]
        
        logger.info(f"Jugadores activos: {len(jugadores_activos)}, Jugadores sin apuesta: {len(jugadores_sin_apuesta)}")
        return jugadores_sin_apuesta
        
    except Exception as e:
        logger.error(f"Error obteniendo jugadores sin apuesta: {e}")
        raise

def obtener_resultados_q2(spreadsheet, circuit_id):
    """Obtiene los resultados de la Q2 para el circuito especificado"""
    try:
        logger.info(f"Buscando resultados Q2 para el circuito {circuit_id}")
        
        # Obtener la sesión Q2 para este circuito desde la hoja Sesiones
        sesiones_sheet = spreadsheet.worksheet('Sesiones')
        sesiones_data = sesiones_sheet.get_all_records()
        
        # Filtrar para encontrar la sesión Q2 del circuito
        sesion_q2 = None
        for sesion in sesiones_data:
            if (str(sesion.get('circuit_id', '')) == str(circuit_id) and 
                'Q2' in str(sesion.get('shortname', '')).upper()):
                sesion_q2 = sesion
                break
        
        if not sesion_q2:
            logger.error(f"No se encontró sesión Q2 para el circuit_id {circuit_id}")
            return []
        
        session_id = sesion_q2.get('session_id', '')
        logger.info(f"Session ID de Q2 encontrado: {session_id}")
        
        # Obtener los resultados de Q2
        q2_sheet = spreadsheet.worksheet('Q2')
        q2_data = q2_sheet.get_all_records()
        logger.info(f"Total de registros en hoja Q2: {len(q2_data)}")
        
        # Verificar si tenemos las columnas esperadas
        if q2_data and len(q2_data) > 0:
            campos_esperados = ['circuit_id', 'circuit_name', 'event_id', 'rider_id', 'rider_name', 'time']
            campos_faltantes = [campo for campo in campos_esperados if campo not in q2_data[0]]
            if campos_faltantes:
                logger.warning(f"Faltan algunos campos esperados en Q2: {campos_faltantes}")
        
        # Filtrar por circuit_id y event_id (que debe coincidir con session_id de Q2)
        resultados_q2 = []
        for resultado in q2_data:
            try:
                circuit_id_resultado = str(resultado.get('circuit_id', '')).strip()
                event_id_resultado = str(resultado.get('event_id', '')).strip()
                
                if (circuit_id_resultado == str(circuit_id) and 
                    event_id_resultado == str(session_id)):
                    resultados_q2.append(resultado)
                    logger.debug(f"Resultado Q2 encontrado para {resultado.get('rider_name')}: {resultado.get('time')}")
            except Exception as e:
                logger.warning(f"Error procesando resultado Q2: {e}")
        
        if not resultados_q2:
            logger.error(f"No se encontraron resultados de Q2 para circuit_id {circuit_id}, session_id {session_id}")
            # Mostrar los primeros resultados para depuración
            if q2_data:
                muestra = q2_data[:3] if len(q2_data) >= 3 else q2_data
                logger.info(f"Muestra de datos Q2 disponibles: {muestra}")
            return []
        
        # Convertir tiempos para asegurar ordenamiento correcto
        def normalizar_tiempo(tiempo):
            if not tiempo:
                return '999999'  # Valor alto para tiempos vacíos
            # Quitar cualquier carácter no numérico excepto el punto decimal
            tiempo_str = ''.join(c for c in str(tiempo) if c.isdigit() or c == '.')
            return tiempo_str
        
        # Ordenar por tiempo (menor a mayor)
        resultados_q2.sort(key=lambda x: normalizar_tiempo(x.get('time', '')))
        
        logger.info(f"Encontrados {len(resultados_q2)} resultados para Q2 del circuito {circuit_id}")
        
        # Convertir al formato esperado por el resto del código
        pilotos_q2 = []
        for resultado in resultados_q2:
            rider_id = resultado.get('rider_id', '')
            rider_name = resultado.get('rider_name', '')
            time_value = resultado.get('time', '')
            
            if not rider_id or not rider_name:
                logger.warning(f"Datos de piloto incompletos: ID={rider_id}, Nombre={rider_name}")
                continue
                
            pilotos_q2.append({
                'id': rider_id,
                'nombre': rider_name,
                'numero': '',  # El número no está disponible en la hoja Q2
                'tiempo': time_value
            })
        
        # Tomar solo los 3 primeros
        top3_pilotos_q2 = pilotos_q2[:3]
        if top3_pilotos_q2:
            logger.info(f"Top 3 pilotos de Q2: {', '.join([f'{p['nombre']} ({p['tiempo']})' for p in top3_pilotos_q2])}")
        else:
            logger.error("No se pudieron obtener los 3 mejores pilotos de Q2")
        
        return top3_pilotos_q2
        
    except Exception as e:
        logger.error(f"Error obteniendo resultados Q2: {e}")
        raise

def crear_apuesta_automatica(spreadsheet, jugador_id, carrera_id, pilotos):
    """Crea una nueva apuesta automática con los 3 primeros pilotos de Q2"""
    try:
        # Obtener siguiente ID para la apuesta
        apuestas_sheet = spreadsheet.worksheet('Apuestas')
        apuestas_data = apuestas_sheet.get_all_records()
        
        # Calcular el siguiente ID de apuesta
        next_id = 1
        if apuestas_data:
            ids = [int(a.get('id', 0)) for a in apuestas_data if a.get('id', '').isdigit()]
            if ids:
                next_id = max(ids) + 1
        
        # Registrar la apuesta principal
        nueva_apuesta = {
            'id': next_id,
            'jugador_id': jugador_id,
            'carrera_id': carrera_id,
            'fecha_creacion': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'automatica': True
        }
        
        # Añadir la apuesta a la hoja
        apuestas_sheet.append_row([
            nueva_apuesta['id'],
            nueva_apuesta['jugador_id'], 
            nueva_apuesta['carrera_id'],
            nueva_apuesta['fecha_creacion'],
            nueva_apuesta['automatica']
        ])
        
        # Registrar los detalles de la apuesta
        detalles_sheet = spreadsheet.worksheet('ApuestasDetalle')
        
        for i, piloto in enumerate(pilotos[:3], 1):
            detalle = {
                'apuesta_id': next_id,
                'posicion': i,
                'piloto_id': piloto['id']
            }
            
            detalles_sheet.append_row([
                detalle['apuesta_id'],
                detalle['posicion'],
                detalle['piloto_id']
            ])
        
        logger.info(f"Apuesta automática #{next_id} creada para jugador {jugador_id}")
        return next_id
        
    except Exception as e:
        logger.error(f"Error al crear la apuesta automática: {e}")
        raise

def obtener_carrera_actual(spreadsheet):
    """Obtiene la última carrera cerrada"""
    try:
        # Abrir hoja de carreras
        carreras_sheet = spreadsheet.worksheet('Sesiones')
        carreras_data = carreras_sheet.get_all_records()
        
        # Obtener fecha actual
        fecha_actual = datetime.datetime.now()
        
        # Filtrar carreras cerradas
        carreras_cerradas = []
        for carrera in carreras_data:
            fecha_cierre = carrera.get('fecha_cierre_apuestas')
            if fecha_cierre:
                # Convertir la fecha de string a datetime
                try:
                    fecha_cierre_dt = datetime.datetime.strptime(fecha_cierre, '%Y-%m-%d %H:%M:%S')
                    if fecha_cierre_dt < fecha_actual:
                        carreras_cerradas.append(carrera)
                except ValueError:
                    logger.warning(f"Formato de fecha inválido: {fecha_cierre}")
        
        # Ordenar por fecha de cierre descendente
        carreras_cerradas.sort(key=lambda x: x.get('fecha_cierre_apuestas', ''), reverse=True)
        
        if carreras_cerradas:
            logger.info(f"Carrera actual encontrada: {carreras_cerradas[0].get('nombre', '')} (ID: {carreras_cerradas[0].get('id', '')})")
        else:
            logger.warning("No se encontraron carreras cerradas")
            
        return carreras_cerradas[0] if carreras_cerradas else None
        
    except Exception as e:
        logger.error(f"Error obteniendo carrera actual: {e}")
        raise

def obtener_circuito_actual(spreadsheet):
    """Obtiene el circuito actual basado en las fechas de la hoja Circuitos"""
    try:
        # Abrir hoja de circuitos
        circuitos_sheet = spreadsheet.worksheet('Circuitos')
        circuitos_data = circuitos_sheet.get_all_records()
        
        # Obtener fecha actual
        fecha_actual = datetime.datetime.now()
        
        # Buscar el circuito actual (donde fecha_actual está entre date_start y date_end)
        circuito_actual = None
        for circuito in circuitos_data:
            date_start = circuito.get('date_start', '')
            date_end = circuito.get('date_end', '')
            
            if date_start and date_end:
                try:
                    # Convertir fechas a datetime
                    date_start_dt = datetime.datetime.strptime(date_start, '%Y-%m-%d')
                    date_end_dt = datetime.datetime.strptime(date_end, '%Y-%m-%d')
                    
                    # Verificar si la fecha actual está dentro del rango
                    if date_start_dt <= fecha_actual <= date_end_dt:
                        circuito_actual = circuito
                        break
                except ValueError:
                    logger.warning(f"Formato de fecha inválido: {date_start} o {date_end}")
        
        if circuito_actual:
            logger.info(f"Circuito actual encontrado: {circuito_actual.get('circuit_name')} (ID: {circuito_actual.get('id')})")
            return circuito_actual
        else:
            # Si no encontramos un circuito actual, buscar el más reciente que haya terminado
            circuitos_pasados = []
            for circuito in circuitos_data:
                date_end = circuito.get('date_end', '')
                if date_end:
                    try:
                        date_end_dt = datetime.datetime.strptime(date_end, '%Y-%m-%d')
                        if date_end_dt < fecha_actual:
                            circuitos_pasados.append((date_end_dt, circuito))
                    except ValueError:
                        continue
            
            if circuitos_pasados:
                # Ordenar por fecha descendente y tomar el más reciente
                circuitos_pasados.sort(reverse=True)
                circuito_reciente = circuitos_pasados[0][1]
                logger.info(f"Circuito más reciente encontrado: {circuito_reciente.get('circuit_name')} (ID: {circuito_reciente.get('id')})")
                return circuito_reciente
        
        logger.warning("No se encontró un circuito actual o reciente")
        return None
        
    except Exception as e:
        logger.error(f"Error obteniendo circuito actual: {e}")
        raise

def asignar_apuestas_automaticas(circuit_id=None):
    """Función principal para asignar apuestas automáticas"""
    try:
        # Conectar a Google Sheets
        spreadsheet = conectar_google_sheets()
        
        # Si no se proporciona circuit_id, obtener el circuito actual o más reciente
        if circuit_id is None:
            circuito = obtener_circuito_actual(spreadsheet)
            if not circuito:
                logger.error("No se encontró un circuito actual o reciente para asignar apuestas automáticas")
                return
            circuit_id = circuito.get('id')
        
        logger.info(f"Iniciando asignación de apuestas automáticas para circuito {circuit_id}")
        
        # 1. Obtener los 3 primeros pilotos de la Q2
        pilotos_q2 = obtener_resultados_q2(spreadsheet, circuit_id)
        
        if not pilotos_q2 or len(pilotos_q2) < 3:
            logger.error("No se pudieron obtener los resultados de la Q2 o hay menos de 3 pilotos.")
            return
        
        # 2. Obtener jugadores sin apuesta para este circuito
        jugadores_sin_apuesta = obtener_jugadores_sin_apuesta(spreadsheet, circuit_id)
        logger.info(f"Encontrados {len(jugadores_sin_apuesta)} jugadores sin apuesta")
        
        if not jugadores_sin_apuesta:
            logger.info("No hay jugadores sin apuesta. Finalizando proceso.")
            return
        
        # 3. Crear y guardar apuestas automáticas para cada jugador
        for jugador in jugadores_sin_apuesta:
            apuesta_id = crear_apuesta_automatica(spreadsheet, jugador['id'], circuit_id, pilotos_q2)
            logger.info(f"Creada apuesta automática #{apuesta_id} para jugador {jugador.get('nombre', jugador['id'])}")
        
        logger.info(f"Proceso finalizado. Se han creado {len(jugadores_sin_apuesta)} apuestas automáticas.")
    
    except Exception as e:
        logger.error(f"Error en asignar_apuestas_automaticas: {e}")
        raise

if __name__ == "__main__":
    # Si se proporciona un argumento, usarlo como ID de circuito
    circuit_id = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        asignar_apuestas_automaticas(circuit_id)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    sys.exit(0)
