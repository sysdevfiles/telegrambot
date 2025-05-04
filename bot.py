import os
import logging
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import user_manager
import datetime # Asegúrate que datetime está importado
import logger

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

# Modificado para ser llamado por cualquier usuario
async def send_management_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía el menú de ayuda de gestión."""
    # Texto base para cualquier usuario que pueda gestionar (incluido admin)
    help_text = (
        "🤖 *Menú de Gestión de Usuarios*\n\n"
        "Estos comandos modifican directamente el archivo `/etc/zivpn/config.json` para gestionar los usuarios que *tú* has creado:\n\n"
        "➕ `/add <user_id>` - Añadir entrada de usuario al JSON (30 días).\n"
        "➖ `/delete <user_id>` - Eliminar entrada de usuario del JSON.\n"
        "🔄 `/update <user_id>` - Renovar fecha en la entrada JSON del usuario (30 días).\n"
        "📋 `/list` - Listar tus entradas de usuario desde el JSON.\n"
        "❓ `/help` - Mostrar este menú.\n\n"
    )
    # Solo el admin original ve el comando backup en la ayuda principal
    if is_admin(update):
         # El admin también gestiona el mismo archivo, pero tiene override y backup
         help_text = (
            "👑 *Menú de Gestión de Administrador*\n\n"
            "Gestionas `/etc/zivpn/config.json` con permisos elevados:\n\n"
            "➕ `/add <user_id>` - Añadir/reactivar cualquier usuario (30 días).\n"
            "➖ `/delete <user_id>` - Eliminar cualquier usuario.\n"
            "🔄 `/update <user_id>` - Renovar cualquier usuario (30 días).\n"
            "📋 `/list` - Listar *todos* los usuarios.\n"
            "💾 `/backup` - Crear backup de `config.json`.\n"
            "❓ `/help` - Mostrar este menú.\n\n"
         )

    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Manejadores de Comandos ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para el comando /start."""
    user = update.effective_user
    logger_telegram.info(f"Usuario {user.id} ({user.username}) inició el bot.")
    # Saludo especial para el admin original
    if is_admin(update):
        await update.message.reply_text(f"¡Hola, Admin Original {user.first_name}!")
        await send_management_help(update, context) # Mostrar menú de gestión
    else:
        # Verificar si el usuario está registrado (sin importar quién lo creó)
        user_data = user_manager.get_user(user.id)
        if user_data:
            expiry_date_str = user_data.get('expiration_date')
            creator_id = user_data.get('creator_id', 'N/A')
            try:
                expiry_date = datetime.datetime.strptime(expiry_date_str, "%Y-%m-%d %H:%M:%S")
                if expiry_date > datetime.datetime.now():
                     await update.message.reply_text(f"¡Hola {user.first_name}! Tu acceso está activo hasta {expiry_date_str} (Creado por ID: {creator_id}).")
                else:
                     await update.message.reply_text(f"¡Hola {user.first_name}! Tu acceso ha expirado ({expiry_date_str}). Contacta a tu gestor (ID: {creator_id}).")
            except (ValueError, TypeError):
                 await update.message.reply_text(f"¡Hola {user.first_name}! Tu acceso está registrado (Creado por ID: {creator_id}) pero la fecha de expiración es inválida.")
        else:
            # Si no está registrado, ofrecerle la ayuda de gestión por si es un manager
            await update.message.reply_text(f"¡Hola {user.first_name}! No tienes acceso autorizado.")
            await send_management_help(update, context) # Mostrar menú por si puede gestionar a otros

# Modificado para mostrar ayuda a todos
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para el comando /help."""
    await send_management_help(update, context)

# Modificado: Sin chequeo is_admin, pasa creator_id
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agrega un nuevo usuario, registrando al usuario actual como creador."""
    creator_id = update.effective_user.id # ID del usuario que ejecuta el comando

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /add <user_id>")
        return

    try:
        user_id_to_add = int(args[0])
    except ValueError:
        await update.message.reply_text("El ID de usuario debe ser un número.")
        return

    # Usar user_manager, pasando el creator_id
    if user_manager.add_user(telegram_id=user_id_to_add, creator_id=creator_id):
        logger.log_action(creator_id, "add", user_id_to_add, f"Usuario agregado/actualizado exitosamente por {creator_id}.")
        await update.message.reply_text(f"Usuario {user_id_to_add} agregado/actualizado. Tú eres el creador. Acceso válido por 30 días.")
    else:
        logger.log_action(creator_id, "add", user_id_to_add, f"Error al agregar/actualizar usuario por {creator_id}.")
        await update.message.reply_text(f"Error al guardar el usuario {user_id_to_add}. Revisa los logs del bot y los permisos del archivo.")

# Modificado: Sin chequeo is_admin, pasa admin_id para verificación de propiedad
async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina un usuario si el usuario actual es el creador."""
    admin_id = update.effective_user.id # ID del usuario que ejecuta el comando

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /delete <user_id>")
        return

    try:
        user_id_to_delete = int(args[0])
    except ValueError:
        await update.message.reply_text("El ID de usuario debe ser un número.")
        return

    # No permitir auto-eliminación (aunque no debería estar en la lista de creados por sí mismo)
    if user_id_to_delete == admin_id:
         await update.message.reply_text("No puedes eliminarte a ti mismo usando este comando.")
         return

    # Usar user_manager, pasando admin_id para verificación
    success, message = user_manager.delete_user(telegram_id=user_id_to_delete, admin_id=admin_id)

    if success:
        logger.log_action(admin_id, "delete", user_id_to_delete, f"Usuario eliminado exitosamente por su creador {admin_id}.")
        await update.message.reply_text(message) # Mensaje de éxito desde user_manager
    else:
        logger.log_action(admin_id, "delete", user_id_to_delete, f"Error al eliminar usuario por {admin_id}: {message}")
        await update.message.reply_text(message) # Mensaje de error desde user_manager (ej. permiso denegado, no encontrado)

# Modificado: Sin chequeo is_admin, pasa admin_id para verificación de propiedad
async def update_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renueva la fecha de expiración de un usuario si el usuario actual es el creador."""
    admin_id = update.effective_user.id # ID del usuario que ejecuta el comando

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Uso: /update <user_id>")
        return

    try:
        user_id_to_update = int(args[0])
    except ValueError:
        await update.message.reply_text("El ID de usuario debe ser un número.")
        return

    # Usar user_manager.renew_user, pasando admin_id para verificación
    success, message = user_manager.renew_user(telegram_id=user_id_to_update, admin_id=admin_id)

    if success:
        logger.log_action(admin_id, "renew", user_id_to_update, f"Expiración de usuario actualizada por su creador {admin_id}.")
        await update.message.reply_text(message) # Mensaje de éxito desde user_manager
    else:
        logger.log_action(admin_id, "renew", user_id_to_update, f"Error al renovar usuario por {admin_id}: {message}")
        await update.message.reply_text(message) # Mensaje de error desde user_manager

# Modificado: Sin chequeo is_admin, pasa admin_id para filtrar la lista
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todos los usuarios registrados creados por el usuario actual."""
    admin_id = update.effective_user.id # ID del usuario que ejecuta el comando

    # Usar user_manager, pasando admin_id para filtrar
    users = user_manager.get_all_users(admin_id=admin_id)

    # Comprobar si el que lista es el admin original para cambiar el título
    is_original_admin_check = is_admin(update)

    if not users:
        if is_original_admin_check:
             await update.message.reply_text("No hay usuarios registrados en `config.json`.")
        else:
             await update.message.reply_text("No has creado ningún usuario todavía.")
        return

    if is_original_admin_check:
        message = "👥 *Todos los Usuarios Registrados (Admin View)*\n\n"
    else:
        message = f"👥 *Usuarios Creados por Ti ({admin_id})*\n\n"

    for user in users:
        uid = user.get('telegram_id', 'N/A')
        cdate = user.get('creation_date', 'N/A')
        edate = user.get('expiration_date', 'N/A')
        creator = user.get('creator_id', 'N/A') # Mostrar creador
        message += f"🆔 `{uid}`\n"
        message += f"   👤 Creador: `{creator}`\n" # Mostrar creador
        message += f"   📅 Creación: {cdate}\n"
        message += f"   ⏳ Vencimiento: {edate}\n\n"

    # ... (envío del mensaje en partes si es largo existente) ...
    max_length = 4096
    for i in range(0, len(message), max_length):
        await update.message.reply_text(message[i:i+max_length], parse_mode='Markdown')


# Mantenido: Solo para el admin original
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea un backup del archivo config.json (solo admin original)."""
    if not is_admin(update):
        await update.message.reply_text("No tienes permiso para usar este comando global.")
        return

    # Usar user_manager
    backup_path = user_manager.create_backup()
    if backup_path:
        logger.log_action(update.effective_user.id, "backup", details=f"Backup de config.json creado en {backup_path}")
        await update.message.reply_text(f"Backup de `config.json` creado exitosamente: `{os.path.basename(backup_path)}`")
        try:
            # Intentar enviar el archivo de backup
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(backup_path, 'rb'))
        except Exception as e:
            logger_telegram.error(f"Error al enviar el archivo de backup: {e}")
            await update.message.reply_text("No se pudo enviar el archivo de backup directamente. Se guardó en el servidor local (`backups/`).")
    else:
        logger.log_action(update.effective_user.id, "backup", details="Error al crear backup de config.json.")
        await update.message.reply_text("Error al crear el backup de `config.json`. Revisa los logs.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para comandos desconocidos."""
    # Ya que todos pueden ver la ayuda, dirigir a /help
    await update.message.reply_text("Comando desconocido. Usa /help para ver los comandos disponibles.")

async def post_init(application: Application):
    """Acciones a realizar después de inicializar el bot (ej. definir comandos)."""
    # Las descripciones aquí son más cortas, mantenemos las anteriores
    await application.bot.set_my_commands([
        BotCommand("start", "▶️ Iniciar el bot y verificar acceso"),
        BotCommand("help", "❓ Mostrar menú de gestión de usuarios"),
        BotCommand("add", "➕ Añadir un usuario nuevo (creado por ti)"),
        BotCommand("delete", "➖ Eliminar un usuario creado por ti"),
        BotCommand("update", "🔄 Renovar un usuario creado por ti"),
        BotCommand("list", "📋 Listar usuarios creados por ti"),
        BotCommand("backup", "💾 Crear backup (Admin)"),
    ])
    logger_telegram.info("Comandos del bot definidos.")

def main():
    """Función principal para iniciar el bot."""
    logger_telegram.info("Iniciando bot con gestión JSON...")

    # Inicializar el almacenamiento JSON y directorio de backups
    user_manager.init_storage()
    logger_telegram.info("Almacenamiento JSON inicializado.")

    # Crear la aplicación del bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Registrar manejadores (sin cambios en los nombres de comando aquí)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_user_command))
    application.add_handler(CommandHandler("delete", delete_user_command))
    application.add_handler(CommandHandler("update", update_user_command)) # El handler sigue siendo /update
    application.add_handler(CommandHandler("list", list_users_command))
    application.add_handler(CommandHandler("backup", backup_command))

    # Manejador para comandos desconocidos
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Iniciar el bot
    logger_telegram.info("Bot listo y escuchando...")
    application.run_polling()

if __name__ == '__main__':
    main()
