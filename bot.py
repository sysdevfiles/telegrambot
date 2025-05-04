import os
import logging
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import user_manager
import datetime
import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler # Importar scheduler
from apscheduler.triggers.cron import CronTrigger # Importar trigger

# Configuración del logging para la librería de Telegram
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger_telegram = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID')

# Validar variables de entorno
if not TELEGRAM_BOT_TOKEN:
    logger_telegram.error("Error: TELEGRAM_BOT_TOKEN no encontrado en .env")
    exit()
if not ADMIN_TELEGRAM_ID:
    logger_telegram.error("Error: ADMIN_TELEGRAM_ID no encontrado en .env")
    exit()
try:
    ADMIN_ID = int(ADMIN_TELEGRAM_ID)
except ValueError:
    logger_telegram.error("Error: ADMIN_TELEGRAM_ID en .env no es un número válido.")
    exit()

# --- Funciones Auxiliares ---
def is_admin(update: Update) -> bool:
    """Verifica si el usuario que envía el mensaje es el administrador ORIGINAL."""
    return update.effective_user.id == ADMIN_ID

def is_authorized(update: Update) -> bool:
    """Verifica si el usuario es el Admin principal o está en la lista de gestores."""
    user_id = update.effective_user.id
    return user_id == ADMIN_ID or user_manager.is_bot_manager(user_id)

async def send_management_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía el menú de ayuda de gestión."""
    # Texto base para usuarios autorizados (no admin)
    help_text = (
        "🤖 *Menú de Gestión de Usuarios (zivpn)*\n\n"
        "Gestiona los usuarios que *tú* has añadido a `/etc/zivpn/config.json`:\n\n"
        "➕ `/add <username>` - Añadir usuario (30 días).\n*Ejemplo:* `/add juanperez`\n\n"
        "➖ `/delete <username>` - Eliminar usuario (creado por ti) de `auth.config`.\n*Ejemplo:* `/delete juanperez`\n\n"
        "🔄 `/renew <username>` - Renovar usuario (creado por ti) por 30 días.\n*Ejemplo:* `/renew juanperez`\n\n" # Añadido
        "📋 `/list` - Listar usuarios creados por ti (con expiración).\n\n"
        "❓ `/help` - Mostrar este menú.\n\n"
        "*Nota: Necesitas autorización del Admin para usar estos comandos.*"
    )

    # Si es el admin principal, muestra un menú extendido
    if is_admin(update):
        help_text = (
            "👑 *Menú de Administrador Principal*\n\n"
            "**Gestión de Usuarios zivpn:**\n"
            "➕ `/add <username>` - Añadir usuario (30 días).\n"
            "➖ `/delete <username>` - Eliminar usuario de `auth.config` (cualquiera).\n"
            "🔄 `/renew <username>` - Renovar usuario (cualquiera) por 30 días.\n" # Añadido
            "📋 `/list` - Listar *todos* los usuarios registrados (con expiración).\n\n"
            "**Gestión de Acceso al Bot:**\n"
            "✅ `/grant <user_id>` - Autorizar a un usuario a usar este bot.\n*Ejemplo:* `/grant 123456789`\n"
            "❌ `/revoke <user_id>` - Revocar autorización a un usuario.\n*Ejemplo:* `/revoke 123456789`\n\n"
            "**Otras Funciones:**\n"
            "💾 `/backup` - Crear backup de archivos de configuración.\n"
            "❓ `/help` - Mostrar este menú.\n"
        )

    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Manejadores de Comandos ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para el comando /start."""
    # Comprobar autorización primero
    if not is_authorized(update):
        await update.message.reply_text("⛔ No tienes permiso para usar este bot. Contacta al administrador.")
        return

    user = update.effective_user
    logger_telegram.info(f"Usuario {user.id} ({user.username}) inició el bot.")
    greeting = f"¡Hola {user.first_name}!"
    if is_admin(update):
        greeting = f"¡Hola, Admin {user.first_name}!"

    await update.message.reply_text(greeting)
    await send_management_help(update, context) # Mostrar menú de gestión a todos

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para el comando /help."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return
    await send_management_help(update, context)

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agrega un username a la lista auth.config y lo registra."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return
    creator_id = update.effective_user.id # ID del usuario que ejecuta el comando

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /add <username>")
        return

    username_to_add = args[0]

    # Pasar creator_id a user_manager
    success, message = user_manager.add_user(username=username_to_add, creator_id=creator_id)

    if success:
        logger.log_action(creator_id, "add_username", target_username=username_to_add, details=message)
        await update.message.reply_text(f"✅ {message}")
    else:
        logger.log_action(creator_id, "add_username_fail", target_username=username_to_add, details=message)
        await update.message.reply_text(f"⚠️ {message}")

async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina un username de la lista auth.config (si tiene permiso)."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return
    admin_id = update.effective_user.id # ID del usuario que ejecuta el comando

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /delete <username>")
        return

    username_to_delete = args[0]

    # Pasar admin_id para verificación de permisos en user_manager
    success, message = user_manager.delete_user(username=username_to_delete, admin_id=admin_id)

    if success:
        logger.log_action(admin_id, "delete_username", target_username=username_to_delete, details=message)
        await update.message.reply_text(f"✅ {message}")
    else:
        logger.log_action(admin_id, "delete_username_fail", target_username=username_to_delete, details=message)
        await update.message.reply_text(f"⚠️ {message}")

async def renew_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renueva la fecha de expiración de un usuario (si tiene permiso)."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return

    admin_id = update.effective_user.id # ID del usuario que ejecuta el comando

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /renew <username>")
        return

    username_to_renew = args[0]

    # Pasar admin_id para verificación de permisos en user_manager
    success, message = user_manager.renew_user(username=username_to_renew, admin_id=admin_id)

    if success:
        logger.log_action(admin_id, "renew_username", target_username=username_to_renew, details=message)
        await update.message.reply_text(f"✅ {message}")
    else:
        logger.log_action(admin_id, "renew_username_fail", target_username=username_to_renew, details=message)
        await update.message.reply_text(f"⚠️ {message}")

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista los usernames creados por el usuario (o todos si es admin), con fecha de expiración."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return
    admin_id = update.effective_user.id # ID del usuario que ejecuta el comando

    # Pasar admin_id para filtrar en user_manager
    usernames = user_manager.get_all_users(admin_id=admin_id)

    is_main_admin_check = is_admin(update) # Para el título del mensaje

    if not usernames:
         if is_main_admin_check:
              await update.message.reply_text("No hay usuarios registrados en `manager_tracking.json`.")
         else:
              await update.message.reply_text("No has añadido ningún usuario todavía.")
         return

    if is_main_admin_check:
        message = "👥 *Todos los Usuarios Registrados (Admin View)*\n\n"
    else:
        message = f"👥 *Usuarios Añadidos por Ti ({admin_id})*\n\n"

    message += "\n".join([f"- `{name}`" for name in usernames])

    # Enviar el mensaje (considerar paginación si la lista puede ser muy larga)
    max_length = 4096
    if len(message) <= max_length:
        await update.message.reply_text(message, parse_mode='Markdown')
    else:
        # Simple paginación (puede mejorarse)
        parts = []
        current_part = message.split('\n\n')[0] + '\n\n' # Mantener título
        lines = message.split('\n')[2:] # Obtener solo las líneas de usuario
        for line in lines:
            if len(current_part) + len(line) + 1 > max_length:
                parts.append(current_part)
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        parts.append(current_part)
        for part in parts:
             await update.message.reply_text(part, parse_mode='Markdown')

# --- Nuevos Comandos de Gestión de Acceso ---

async def grant_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Admin Only) Autoriza a un usuario a usar el bot."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Comando reservado para el Administrador Principal.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /grant <user_id>")
        return

    try:
        user_id_to_grant = int(args[0])
    except ValueError:
        await update.message.reply_text("El ID de usuario debe ser un número.")
        return

    success, message = user_manager.add_bot_manager(user_id=user_id_to_grant)

    if success:
        logger.log_action(update.effective_user.id, "grant_access", target_username=str(user_id_to_grant), details=message)
        await update.message.reply_text(f"✅ {message}")
        # Opcional: Notificar al usuario que ha recibido acceso
        # try:
        #     await context.bot.send_message(chat_id=user_id_to_grant, text="✅ ¡Has sido autorizado para usar el bot de gestión!")
        # except Exception as e:
        #     logger_telegram.warning(f"No se pudo notificar al usuario {user_id_to_grant} sobre el acceso concedido: {e}")
    else:
        logger.log_action(update.effective_user.id, "grant_access_fail", target_username=str(user_id_to_grant), details=message)
        await update.message.reply_text(f"⚠️ {message}")

async def revoke_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Admin Only) Revoca la autorización de un usuario para usar el bot."""
    if not is_admin(update):
        await update.message.reply_text("⛔ Comando reservado para el Administrador Principal.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /revoke <user_id>")
        return

    try:
        user_id_to_revoke = int(args[0])
    except ValueError:
        await update.message.reply_text("El ID de usuario debe ser un número.")
        return

    success, message = user_manager.remove_bot_manager(user_id=user_id_to_revoke)

    if success:
        logger.log_action(update.effective_user.id, "revoke_access", target_username=str(user_id_to_revoke), details=message)
        await update.message.reply_text(f"✅ {message}")
        # Opcional: Notificar al usuario que se le ha revocado el acceso
        # try:
        #     await context.bot.send_message(chat_id=user_id_to_revoke, text="❌ Tu autorización para usar el bot de gestión ha sido revocada.")
        # except Exception as e:
        #     logger_telegram.warning(f"No se pudo notificar al usuario {user_id_to_revoke} sobre el acceso revocado: {e}")
    else:
        logger.log_action(update.effective_user.id, "revoke_access_fail", target_username=str(user_id_to_revoke), details=message)
        await update.message.reply_text(f"⚠️ {message}")

# --- Fin Nuevos Comandos ---

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea un backup de los archivos de config (solo admin original)."""
    if not is_admin(update):
        # Ya no usamos is_authorized aquí, backup es solo para el admin principal
        await update.message.reply_text("⛔ Comando reservado para el Administrador Principal.")
        return

    # user_manager.create_backup ahora intenta hacer backup de ambos
    # pero solo devuelve la ruta del config.json si todo va bien
    config_backup_path = user_manager.create_backup()

    if config_backup_path:
        # Asumimos que si config_backup_path no es None, ambos backups (si existían los originales) se crearon
        logger.log_action(update.effective_user.id, "backup", details=f"Backups creados en {user_manager.BACKUP_DIR}")
        await update.message.reply_text(f"💾 Backups de `config.json` y `manager_tracking.json` creados exitosamente en el servidor.")
        try:
            # Enviar solo el backup de config.json por ahora
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(config_backup_path, 'rb'))
        except Exception as e:
            logger_telegram.error(f"Error al enviar el archivo de backup {config_backup_path}: {e}")
            await update.message.reply_text("⚠️ No se pudo enviar el archivo `config.json` directamente. Se guardó en el servidor local (`backups/`).")
    else:
        logger.log_action(update.effective_user.id, "backup_fail", details="Error al crear uno o ambos backups.")
        await update.message.reply_text("⚠️ Error al crear los backups. Revisa los logs.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para comandos desconocidos."""
    # Informar solo si está autorizado, para no dar pistas a usuarios no autorizados
    if is_authorized(update):
        await update.message.reply_text("Comando desconocido. Usa /help para ver los comandos disponibles.")
    # Si no está autorizado, no respondemos nada a comandos desconocidos

async def post_init(application: Application):
    """Acciones a realizar después de inicializar el bot y el scheduler."""
    # Añadir renew
    await application.bot.set_my_commands([
        BotCommand("start", "▶️ Iniciar el bot"),
        BotCommand("help", "❓ Mostrar menú de ayuda"),
        BotCommand("add", "➕ Añadir usuario a zivpn (30d)"),
        BotCommand("delete", "➖ Eliminar usuario de zivpn"),
        BotCommand("renew", "🔄 Renovar usuario zivpn (30d)"), # Añadido
        BotCommand("list", "📋 Listar usuarios de zivpn"),
        BotCommand("grant", "✅ (Admin) Autorizar usuario bot"),
        BotCommand("revoke", "❌ (Admin) Revocar usuario bot"),
        BotCommand("backup", "💾 (Admin) Crear backup config"),
    ])
    logger_telegram.info("Comandos del bot definidos.")

    # --- Configuración del Scheduler ---
    scheduler = AsyncIOScheduler(timezone="UTC") # O la timezone relevante
    # Ejecutar check_and_expire_users todos los días a las 03:00 UTC
    scheduler.add_job(user_manager.check_and_expire_users, CronTrigger(hour=3, minute=0))
    scheduler.start()
    logger_telegram.info("Scheduler iniciado. Chequeo de expiración programado diariamente a las 03:00 UTC.")
    # Guardar scheduler en context para poder apagarlo limpiamente si fuera necesario
    application.bot_data['scheduler'] = scheduler

def main():
    """Función principal para iniciar el bot."""
    logger_telegram.info("Iniciando bot para gestión de config.json...")

    user_manager.init_storage()
    logger_telegram.info("Almacenamiento JSON inicializado.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_user_command))
    application.add_handler(CommandHandler("delete", delete_user_command))
    application.add_handler(CommandHandler("renew", renew_user_command)) # Añadido
    application.add_handler(CommandHandler("list", list_users_command))
    application.add_handler(CommandHandler("grant", grant_access_command)) # Añadido
    application.add_handler(CommandHandler("revoke", revoke_access_command)) # Añadido
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger_telegram.info("Bot listo y escuchando...")
    application.run_polling()

    # Apagar scheduler al detener el bot (si se detiene limpiamente)
    scheduler = application.bot_data.get('scheduler')
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger_telegram.info("Scheduler detenido.")

if __name__ == '__main__':
    main()
