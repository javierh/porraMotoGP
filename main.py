import asyncio
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, Application, PicklePersistence, CallbackQueryHandler
from datetime import datetime, timedelta, timezone
import pytz  # Para manejo de Timezones
import math  # Para funciones matemáticas en la paginación
import logging  # Para debug logging
import sys  # Para salir del programa con un código de error
from database import fetch_data, insert_data

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
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Europe/Madrid'))

# Verificar configuración de MySQL
if not all([MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE]):
    missing = []
    if not MYSQL_HOST: missing.append('MYSQL_HOST')
    if not MYSQL_USER: missing.append('MYSQL_USER')
    if not MYSQL_PASSWORD: missing.append('MYSQL_PASSWORD')
    if not MYSQL_DATABASE: missing.append('MYSQL_DATABASE')
    logger.error(f"Faltan variables de entorno MySQL: {', '.join(missing)}")
    logger.error("Por favor configura las variables de entorno en el archivo .env")
    sys.exit(1)

# Verificar token de Telegram
if not TELEGRAM_BOT_TOKEN:
    logger.error("Falta la variable de entorno TELEGRAM_BOT_TOKEN")
    logger.error("Por favor configura TELEGRAM_BOT_TOKEN en el archivo .env")
    sys.exit(1)

# Ahora importamos las funciones, después de verificar variables de entorno
try:
    from functions import (get_mysql_connection, obtener_sesiones_desde_mysql, obtener_eventos_desde_mysql, 
                          obtener_pilotos_desde_mysql, guardar_usuario_en_mysql, guardar_apuesta_en_mysql, 
                          cargar_apuestas_desde_mysql, obtener_deadline_sesion, obtener_evento_mas_proximo, 
                          es_tiempo_apuesta_abierto, format_datetime_para_usuario, escape_markdown_v2, 
                          crear_teclado_pilotos)
    
    # Intentar verificar la conexión MySQL
    try:
        conn = get_mysql_connection()
        conn.close()
        logger.info("Conexión a MySQL verificada correctamente")
    except Exception as e:
        logger.error(f"Error al conectar a MySQL: {e}")
        logger.error("Por favor verifica que el servidor MySQL esté en ejecución y las credenciales sean correctas")
        sys.exit(1)
        
except ImportError as e:
    logger.error(f"Error al importar funciones: {e}")
    sys.exit(1)

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

# --- 2. Conexión a MySQL ---
# ...existing code...

# --- 3. Funciones de MySQL ---
# ...existing code...

# --- 4. Funciones de Gestión de Fechas y Eventos ---
# ...existing code...

# --- 5. Gestión de Apuestas ---
# Inicializar apuestas con manejo de errores
try:
    apuestas = cargar_apuestas_desde_mysql()
    logger.info(f"Se cargaron {sum(len(eventos) for chat in apuestas.values() for eventos in chat.values())} apuestas desde MySQL")
except Exception as e:
    logger.error(f"Error al cargar apuestas: {e}")
    logger.warning("Se utilizará un diccionario vacío para apuestas")
    apuestas = {}

apuestas_q2_fallback = {}
resultados_oficiales = {}

def guardar_apuesta(chat_id, evento_id, tipo_evento, podio):
    """Guarda la apuesta de un usuario."""
    if chat_id not in apuestas:
        apuestas[chat_id] = {}
    if evento_id not in apuestas[chat_id]:
        apuestas[chat_id][evento_id] = {}
    apuestas[chat_id][evento_id][tipo_evento] = podio
    guardar_apuesta_en_mysql(chat_id, evento_id, tipo_evento, podio)

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
# ...existing code...

# --- 7. Manejadores de Comandos del Bot ---
async def start(update, context):
    """Comando /start: Mensaje de bienvenida e información básica."""
    user = update.message.from_user
    guardar_usuario_en_mysql(user)
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

async def proximo_evento_command(update, context):
    """Comando /proximo_evento: Muestra información del próximo evento."""
    eventos = obtener_eventos_desde_mysql()
    evento_proximo = obtener_evento_mas_proximo(eventos)
    if evento_proximo:
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

async def rules_command(update, context):
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

async def ver_apuesta_command(update, context):
    """Comando /ver_apuesta: Muestra la apuesta actual del usuario para el próximo evento."""
    evento_proximo = obtener_evento_mas_proximo(obtener_eventos_desde_mysql())
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
    evento_proximo = obtener_evento_mas_proximo(obtener_eventos_desde_mysql())
    if not evento_proximo:
        await update.message.reply_text("No hay próximos eventos para mostrar podio de Q2.")
        return

    evento_id = evento_proximo['event_id']
    # Obtener resultados de Q2 directamente de la base de datos
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

async def ranking_command(update, context):
    """Comando /ranking: Muestra la clasificación actual de todos los jugadores."""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT r.user_id, r.score, r.points_last_circuit, j.username, j.first_name, j.last_name 
            FROM Ranking r
            LEFT JOIN Jugones j ON r.user_id = j.chat_id
            ORDER BY r.score DESC
        """)
        datos_ranking = cursor.fetchall()
        
        if not datos_ranking:
            await update.message.reply_text("No hay datos de ranking disponibles todavía.")
            return
            
        # Preparar mensaje con el ranking
        mensaje = "*🏆 Ranking actual 🏆*\n\n"
        
        # Construir la tabla de clasificación
        posicion = 1
        for jugador in datos_ranking:
            try:
                user_id = int(jugador['user_id'])
                score = jugador['score']
                points_last = jugador['points_last_circuit']
                
                # Obtener nombre de usuario para mostrar
                if jugador['username']:
                    nombre_mostrar = jugador['username']
                elif jugador['first_name'] or jugador['last_name']:
                    nombre_mostrar = f"{jugador['first_name']} {jugador['last_name']}".strip()
                else:
                    nombre_mostrar = f"Usuario {user_id}"
                    
                nombre_escapado = escape_markdown_v2(str(nombre_mostrar))
                
                # Formatear línea del ranking
                if posicion <= 3:  # Destacar top 3
                    emoji = ['🥇', '🥈', '🥉'][posicion-1]
                    mensaje += f"{emoji} *{posicion}\\. {nombre_escapado}*: {score} pts \\(\\+{points_last} último\\)\n"
                else:
                    mensaje += f"{posicion}\\. {nombre_escapado}: {score} pts \\(\\+{points_last} último\\)\n"
                
                posicion += 1
            except Exception as e:
                logger.error(f"Error al procesar jugador del ranking: {e}")
        
        await update.message.reply_markdown_v2(mensaje)
    except Exception as e:
        logger.error(f"Error al mostrar ranking: {e}", exc_info=True)
        await update.message.reply_text("Hubo un error al obtener el ranking. Inténtalo más tarde.")
    finally:
        cursor.close()
        connection.close()

async def forzar_apuestas_q2_command(update, context):
    """Comando /forzar_apuestas_q2: Asigna manualmente las apuestas Q2 por defecto."""
    eventos = obtener_eventos_desde_mysql()
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

# Placeholder functions for conversation handlers
async def apostar_sprint_command_inicio(update, context):
    # Placeholder
    await update.message.reply_text("Función en desarrollo")
    return ConversationHandler.END

async def apostar_carrera_command_inicio(update, context):
    # Placeholder
    await update.message.reply_text("Función en desarrollo")
    return ConversationHandler.END

async def direct_apostar_sprint(update, context):
    # Placeholder
    logger.info("Direct apostar_sprint handler called")
    return await apostar_sprint_command_inicio(update, context)

async def direct_apostar_carrera(update, context):
    # Placeholder
    logger.info("Direct apostar_carrera handler called")
    return await apostar_carrera_command_inicio(update, context)

async def error(update, context):
    """Log errors caused by updates."""
    logger.error(f'Update {update} caused error {context.error}', exc_info=context.error)

async def debug_message_handler(update, context):
    """Handler para debug - captura todos los mensajes que no coinciden con otros handlers"""
    logger.info(f"Mensaje recibido no manejado: '{update.message.text}' de usuario {update.message.from_user.id}")
    return None

async def cancelar_apuesta(update, context):
    """Cancela la conversación de apuesta."""
    await update.message.reply_text('Apuesta cancelada.')
    return ConversationHandler.END

# --- Define conversation handlers ---
conv_handler_sprint = ConversationHandler(
    entry_points=[CommandHandler('apostar_sprint', apostar_sprint_command_inicio)],
    states={
        APOSTAR_SPRINT_PILOTO1: [], 
        APOSTAR_SPRINT_PILOTO2: [],
        APOSTAR_SPRINT_PILOTO3: []
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    name="sprint_conversation"
)

conv_handler_carrera = ConversationHandler(
    entry_points=[CommandHandler('apostar_carrera', apostar_carrera_command_inicio)],
    states={
        APOSTAR_CARRERA_PILOTO1: [],
        APOSTAR_CARRERA_PILOTO2: [],
        APOSTAR_CARRERA_PILOTO3: []
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    name="carrera_conversation"
)

conv_handler_ejecutar_sprint = ConversationHandler(
    entry_points=[CommandHandler('ejecutar_sprint', lambda u, c: ConversationHandler.END)],
    states={
        EJECUTAR_SPRINT_PILOTO1: [],
        EJECUTAR_SPRINT_PILOTO2: [],
        EJECUTAR_SPRINT_PILOTO3: []
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    name="ejecutar_sprint_conversation"
)

conv_handler_ejecutar_carrera = ConversationHandler(
    entry_points=[CommandHandler('ejecutar_carrera', lambda u, c: ConversationHandler.END)],
    states={
        EJECUTAR_CARRERA_PILOTO1: [],
        EJECUTAR_CARRERA_PILOTO2: [],
        EJECUTAR_CARRERA_PILOTO3: []
    },
    fallbacks=[CommandHandler('cancelar', cancelar_apuesta)],
    name="ejecutar_carrera_conversation"
)

# ...existing code...

async def main():
    """Inicia el bot y sus manejadores de comandos."""
    # Configurar persistencia
    persistence = PicklePersistence(filepath="bot_data.pickle")
    
    try:
        # Cargar apuestas desde MySQL al iniciar
        global apuestas
        apuestas_cargadas = cargar_apuestas_desde_mysql()
        if apuestas_cargadas:
            apuestas = apuestas_cargadas
            print(f"Se cargaron {sum(len(eventos) for chat in apuestas.values() for eventos in chat.values())} apuestas desde MySQL")
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
