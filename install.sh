#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuración ---
# Directorio base donde se clonará el repositorio (cambiado a /opt)
PROJECT_BASE_DIR=/opt/telegram_bot_manager
# Nombre del repositorio (coincide con el último componente de la URL)
REPO_NAME="telegrambot"
# Directorio final del proyecto (donde está el código)
PROJECT_DIR="$PROJECT_BASE_DIR/$REPO_NAME"
# URL del repositorio Git
REPO_URL="https://github.com/sysdevfiles/telegrambot.git"
# Directorio para archivos de configuración y logs persistentes
CONFIG_DIR="/etc/zivpn"
# Usuario y Grupo explícitamente root
BOT_USER="root"
BOT_GROUP="root"
# Archivo de log para el proceso de instalación
LOG_FILE=/root/telegram_bot_manager_install.log # Log en el home de root

# Limpiar log anterior si existe
echo "Iniciando log de instalación en $LOG_FILE..." > "$LOG_FILE"

echo "--- Iniciando Instalación y Configuración del Bot de Telegram desde GitHub (como root) ---" | tee -a "$LOG_FILE"
echo "Este script configurará el entorno en el VPS." | tee -a "$LOG_FILE"
echo "Usuario detectado: $BOT_USER (Grupo: $BOT_GROUP)" | tee -a "$LOG_FILE"
echo "Directorio base: $PROJECT_BASE_DIR" | tee -a "$LOG_FILE"
echo "Repositorio: $REPO_URL" | tee -a "$LOG_FILE"
echo "Directorio de configuración: $CONFIG_DIR" | tee -a "$LOG_FILE"

# --- 1. Limpieza de Instalación Anterior (Opcional pero solicitado) ---
echo ">>> Limpiando instalación anterior en $PROJECT_BASE_DIR (si existe)..." | tee -a "$LOG_FILE"
# Eliminar el directorio base completo del proyecto anterior
rm -rf "$PROJECT_BASE_DIR"
echo "Directorio $PROJECT_BASE_DIR eliminado." | tee -a "$LOG_FILE"

# --- 2. Actualizar Sistema e Instalar Paquetes ---
echo ">>> Actualizando lista de paquetes..." | tee -a "$LOG_FILE"
# Removido sudo
apt update >> "$LOG_FILE" 2>&1 || { echo "Error en apt update. Ver $LOG_FILE"; exit 1; }
echo "Actualización de paquetes completada." | tee -a "$LOG_FILE"

echo ">>> Instalando dependencias del sistema: Python3, pip, venv, sqlite3, git..." | tee -a "$LOG_FILE"
# Removido sudo
apt install -y python3 python3-pip python3-venv sqlite3 git >> "$LOG_FILE" 2>&1 || { echo "Error en apt install. Ver $LOG_FILE"; exit 1; }
echo "Dependencias del sistema instaladas." | tee -a "$LOG_FILE"

# --- 3. Clonar Repositorio ---
echo ">>> Asegurando directorio base $PROJECT_BASE_DIR..." | tee -a "$LOG_FILE"
mkdir -p "$PROJECT_BASE_DIR"
cd "$PROJECT_BASE_DIR"

echo ">>> Clonando repositorio $REPO_URL..." | tee -a "$LOG_FILE"
# Ya no se necesita la comprobación if/else porque limpiamos antes
echo "Clonando repositorio..." | tee -a "$LOG_FILE"
git clone "$REPO_URL" >> "$LOG_FILE" 2>&1 || { echo "Error en git clone. Ver $LOG_FILE"; exit 1; }
cd "$PROJECT_DIR"
echo "Repositorio clonado. Directorio actual: $(pwd)" | tee -a "$LOG_FILE"

# --- 4. Configurar Entorno Virtual y Dependencias Python ---
echo ">>> Creando entorno virtual 'venv'..." | tee -a "$LOG_FILE"
# Ya no se necesita la comprobación if/else porque limpiamos antes
python3 -m venv venv
echo "Entorno virtual creado." | tee -a "$LOG_FILE"

echo ">>> Instalando/Actualizando dependencias de Python..." | tee -a "$LOG_FILE"
# Activar venv temporalmente para el comando pip
source venv/bin/activate

# Asegurarse de que requirements.txt existe y se usa
if [ -f "requirements.txt" ]; then
    echo "Archivo requirements.txt encontrado. Instalando/Actualizando dependencias desde él..." | tee -a "$LOG_FILE"
    pip install -r requirements.txt >> "$LOG_FILE" 2>&1 || { echo "Error en pip install -r requirements.txt. Ver $LOG_FILE"; exit 1; }
else
    # Fallback por si acaso, aunque deberíamos tener requirements.txt
    echo "ADVERTENCIA: Archivo requirements.txt no encontrado. Instalando dependencias conocidas..." | tee -a "$LOG_FILE"
    # Añadir APScheduler aquí también
    pip install python-telegram-bot python-dotenv APScheduler >> "$LOG_FILE" 2>&1 || { echo "Error en pip install directo. Ver $LOG_FILE"; exit 1; }
fi
echo "Dependencias de Python instaladas." | tee -a "$LOG_FILE"

# Desactivar venv (opcional, ya que el script termina pronto)
# deactivate

# --- 5. Crear Directorio y Archivos de Configuración/Log ---
echo ">>> Creando/Asegurando directorio de configuración $CONFIG_DIR..." | tee -a "$LOG_FILE"
# Removido sudo
mkdir -p "$CONFIG_DIR"

echo ">>> Creando/Sobrescribiendo archivo de datos $CONFIG_DIR/config.json con estructura por defecto..." | tee -a "$LOG_FILE"
# Removido sudo
cat << EOF > "${CONFIG_DIR}/config.json"
{
  "listen": ":5667",
   "cert": "/etc/zivpn/zivpn.crt",
   "key": "/etc/zivpn/zivpn.key",
   "obfs":"zivpn",
   "auth": {
    "mode": "passwords",
    "config": ["root","neri","tomas","yasser","daniel","antonio","mono","doncarlos"]
  }
}
EOF
echo "Archivo config.json creado/reiniciado con estructura por defecto." | tee -a "$LOG_FILE"

echo ">>> Creando/Sobrescribiendo archivo de log $CONFIG_DIR/admin_log.json..." | tee -a "$LOG_FILE"
# Removido sudo
sh -c "echo '[]' > ${CONFIG_DIR}/admin_log.json"
echo "Archivo admin_log.json creado/reiniciado." | tee -a "$LOG_FILE"

echo ">>> Creando/Sobrescribiendo archivo de tracking $CONFIG_DIR/manager_tracking.json..." | tee -a "$LOG_FILE"
# Removido sudo
sh -c "echo '[]' > ${CONFIG_DIR}/manager_tracking.json"
echo "Archivo manager_tracking.json creado/reiniciado." | tee -a "$LOG_FILE"

# --- Añadir creación de archivo de gestores del bot ---
echo ">>> Creando/Sobrescribiendo archivo de gestores $CONFIG_DIR/bot_managers.json..." | tee -a "$LOG_FILE"
# Removido sudo
sh -c "echo '[]' > ${CONFIG_DIR}/bot_managers.json"
echo "Archivo bot_managers.json creado/reiniciado." | tee -a "$LOG_FILE"
# --- Fin de añadido ---

echo ">>> Estableciendo permisos para $CONFIG_DIR..." | tee -a "$LOG_FILE"
# Removido sudo, asegura que el propietario sea root:root
chown -R "$BOT_USER":"$BOT_GROUP" "$CONFIG_DIR"
# Asegurar permisos específicos si es necesario (aunque chown -R debería bastar)
# chmod 600 "${CONFIG_DIR}/config.json" # Ejemplo si se quisiera más restricción
# chmod 600 "${CONFIG_DIR}/manager_tracking.json"
# chmod 600 "${CONFIG_DIR}/bot_managers.json" # Añadido
# chmod 600 "${CONFIG_DIR}/admin_log.json"
echo "Propietario de $CONFIG_DIR establecido a $BOT_USER:$BOT_GROUP." | tee -a "$LOG_FILE"

# --- 6. Crear Directorio de Backups Local ---
echo ">>> Creando/Asegurando directorio de backups local en $PROJECT_DIR/backups..." | tee -a "$LOG_FILE"
mkdir -p "$PROJECT_DIR/backups" # Ya pertenece al usuario correcto
echo "Directorio de backups creado." | tee -a "$LOG_FILE"

# --- 7. Configurar Servicio systemd ---
SERVICE_NAME="telegrambot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo ">>> Creando archivo de servicio systemd: $SERVICE_FILE..." | tee -a "$LOG_FILE"

# Usar rutas absolutas
PYTHON_EXEC="$PROJECT_DIR/venv/bin/python"
BOT_SCRIPT="$PROJECT_DIR/bot.py"

# Crear el archivo de servicio
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Telegram Bot Manager Service
After=network.target

[Service]
User=$BOT_USER
Group=$BOT_GROUP
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_EXEC $BOT_SCRIPT
Restart=on-failure
# Opcional: Añadir un pequeño delay antes de reiniciar
# RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Archivo de servicio creado." | tee -a "$LOG_FILE"

echo ">>> Recargando demonio systemd..." | tee -a "$LOG_FILE"
systemctl daemon-reload || { echo "Error en systemctl daemon-reload. Ver $LOG_FILE"; exit 1; }

echo ">>> Habilitando servicio ${SERVICE_NAME} para inicio automático..." | tee -a "$LOG_FILE"
systemctl enable "${SERVICE_NAME}.service" >> "$LOG_FILE" 2>&1 || { echo "Error en systemctl enable. Ver $LOG_FILE"; exit 1; }

echo ">>> Iniciando servicio ${SERVICE_NAME}..." | tee -a "$LOG_FILE"
systemctl start "${SERVICE_NAME}.service" || { echo "Error en systemctl start. El servicio puede haber fallado al iniciar. Revisa con 'systemctl status ${SERVICE_NAME}' y 'journalctl -u ${SERVICE_NAME}'. Ver $LOG_FILE"; exit 1; } # No salir si falla el start inicial, pero advertir

echo "Servicio systemd configurado y iniciado." | tee -a "$LOG_FILE"

# --- 8. Finalización ---
echo "" | tee -a "$LOG_FILE"
echo "--- Instalación y Configuración (Reinstalación Limpia) Completada ---" | tee -a "$LOG_FILE"
echo ""
echo "El código del bot está en $PROJECT_DIR." | tee -a "$LOG_FILE"
echo "Las dependencias están instaladas en $PROJECT_DIR/venv." | tee -a "$LOG_FILE"
echo "Los archivos de datos y logs están en $CONFIG_DIR." | tee -a "$LOG_FILE"
echo "El bot ahora se ejecuta como un servicio systemd llamado '${SERVICE_NAME}'." | tee -a "$LOG_FILE"
echo ""
echo "Próximos pasos:" | tee -a "$LOG_FILE"

# --- 8.1 Crear y Editar .env ---
echo ">>> Creando archivo .env con valores de ejemplo..." | tee -a "$LOG_FILE"
# Navegar al directorio del proyecto
cd "$PROJECT_DIR"
# Crear .env con placeholders
cat << EOF > .env
TELEGRAM_BOT_TOKEN=TU_TOKEN_AQUI
ADMIN_TELEGRAM_ID=TU_ID_DE_ADMIN_AQUI
EOF
echo "Archivo .env creado en $PROJECT_DIR." | tee -a "$LOG_FILE"

# Abrir nano para editar (esto pausará el script hasta que el usuario cierre nano)
echo ""
echo ">>> Por favor, edita el archivo .env con tus credenciales reales." | tee -a "$LOG_FILE"
echo "    Reemplaza 'TU_TOKEN_AQUI' y 'TU_ID_DE_ADMIN_AQUI'."
echo "    Guarda los cambios en nano con Ctrl+X, luego Y, y Enter."
echo "    Presiona Enter para abrir nano..."
read -p "" # Espera a que el usuario presione Enter

# Abrir nano
nano .env

echo ""
echo "Archivo .env editado." | tee -a "$LOG_FILE"

# --- 8.2 Reiniciar servicio para aplicar .env ---
echo ">>> Reiniciando servicio ${SERVICE_NAME} para aplicar la configuración de .env..." | tee -a "$LOG_FILE"
systemctl restart "${SERVICE_NAME}.service" || echo "Advertencia: Falló el reinicio del servicio. Revisa el estado con 'systemctl status ${SERVICE_NAME}'." | tee -a "$LOG_FILE"
echo "Servicio reiniciado." | tee -a "$LOG_FILE"

# --- 8.3 Comandos útiles ---
echo ""
echo "2. Comandos útiles para gestionar el servicio:" | tee -a "$LOG_FILE"
echo "   - Ver estado: systemctl status ${SERVICE_NAME}" | tee -a "$LOG_FILE"
echo "   - Ver logs: journalctl -u ${SERVICE_NAME} -f --no-pager" | tee -a "$LOG_FILE"
echo "   - Detener: systemctl stop ${SERVICE_NAME}" | tee -a "$LOG_FILE"
echo "   - Iniciar: systemctl start ${SERVICE_NAME}" | tee -a "$LOG_FILE"
echo "   - Reiniciar: systemctl restart ${SERVICE_NAME}" | tee -a "$LOG_FILE"
echo ""
echo "Para actualizar el bot en el futuro, vuelve a ejecutar este script './install.sh'. El script reinstalará y reiniciará el servicio." | tee -a "$LOG_FILE"
echo "-----------------------------------------" | tee -a "$LOG_FILE"
echo ""
echo ">>> El log detallado de esta instalación se ha guardado en: $LOG_FILE"
echo "-----------------------------------------"

exit 0
