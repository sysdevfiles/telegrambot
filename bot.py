import os
import logging
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import user_manager
import datetime
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

async def send_management_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía el menú de ayuda de gestión."""
    # Menú para todos los usuarios que pueden gestionar
    help_text = (
        "🤖 *Menú de Gestión de Usuarios (zivpn)*\n\n"
        "Gestiona los usuarios que *tú* has añadido a `/etc/zivpn/config.json`:\n\n"
        "➕ `/add <username>` - Añadir usuario a la lista `auth.config`.\n*Ejemplo:* `/add juanperez`\n\n"
        "➖ `/delete <username>` - Eliminar usuario (creado por ti) de `auth.config`.\n*Ejemplo:* `/delete juanperez`\n\n"
        "📋 `/list` - Listar usuarios creados por ti (o todos si eres Admin).\n\n"
        "💾 `/backup` - (Admin) Crear backup de `config.json` y `manager_tracking.json`.\n\n"
        "❓ `/help` - Mostrar este menú.\n\n"
        "*Nota: El Admin Principal puede eliminar usuarios creados por otros.*"
    )
    # El admin ve el mismo menú, pero /list y /delete tienen comportamiento extendido
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Manejadores de Comandos ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para el comando /start."""
    user = update.effective_user
    logger_telegram.info(f"Usuario {user.id} ({user.username}) inició el bot.")
    greeting = f"¡Hola {user.first_name}!"
    if is_admin(update):
        greeting = f"¡Hola, Admin {user.first_name}!"

    await update.message.reply_text(greeting)
    await send_management_help(update, context) # Mostrar menú de gestión a todos

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para el comando /help."""
    await send_management_help(update, context)

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agrega un username a la lista auth.config y lo registra."""
    # No más check is_admin aquí
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
    # No más check is_admin aquí
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

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista los usernames creados por el usuario (o todos si es admin)."""
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

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea un backup de config.json y tracking.json (solo admin original)."""
    if not is_admin(update):
        await update.message.reply_text("❌ No tienes permiso para usar este comando.")
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
    await update.message.reply_text("Comando desconocido. Usa /help para ver los comandos disponibles.")

async def post_init(application: Application):
    """Acciones a realizar después de inicializar el bot (ej. definir comandos)."""
    # Remover "(Admin)" de add/delete
    await application.bot.set_my_commands([
        BotCommand("start", "▶️ Iniciar el bot"),
        BotCommand("help", "❓ Mostrar menú de ayuda"),
        BotCommand("add", "➕ Añadir usuario a zivpn"),
        BotCommand("delete", "➖ Eliminar usuario de zivpn"),
        BotCommand("list", "📋 Listar usuarios de zivpn"),
        BotCommand("backup", "💾 (Admin) Crear backup config"),
    ])
    logger_telegram.info("Comandos del bot definidos.")

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
    application.add_handler(CommandHandler("list", list_users_command))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger_telegram.info("Bot listo y escuchando...")
    application.run_polling()

if __name__ == '__main__':
    main()
