#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_DIR="$ROOT_DIR/node"
VENV_DIR="$NODE_DIR/.venv-node"
ENV_FILE="$NODE_DIR/.env"

prompt_default() {
  local prompt="$1"
  local default="$2"
  local value

  read -r -p "$prompt [$default]: " value
  echo "${value:-$default}"
}

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Run this script as your normal Pi user, not with sudo."
  echo "It will use sudo only for system packages."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found."
  exit 1
fi

NODE_ID="${SKYHUB_NODE_NODE_ID:-}"
SERVER_WS_BASE_URL="${SKYHUB_NODE_SERVER_WS_BASE_URL:-}"
CAMERA_DRIVER="${SKYHUB_NODE_CAMERA_DRIVER:-picamera2}"
ENVIRONMENT_SENSOR_DRIVER="${SKYHUB_NODE_ENVIRONMENT_SENSOR_DRIVER:-bme280}"
BME280_I2C_BUS="${SKYHUB_NODE_BME280_I2C_BUS:-1}"
BME280_I2C_ADDRESS="${SKYHUB_NODE_BME280_I2C_ADDRESS:-0x77}"

if [[ -z "$NODE_ID" ]]; then
  NODE_ID="$(prompt_default "Node id" "pi5-hqcam")"
fi

if [[ -z "$SERVER_WS_BASE_URL" ]]; then
  SERVER_HOST="$(prompt_default "SkyHub server host or IP" "WINDOWS_IP")"
  SERVER_PORT="$(prompt_default "SkyHub server port" "8000")"

  if [[ "$SERVER_HOST" == "WINDOWS_IP" ]]; then
    echo "Please rerun with your actual Windows/server IP address."
    exit 1
  fi

  SERVER_WS_BASE_URL="ws://${SERVER_HOST}:${SERVER_PORT}/ws/nodes"
fi

echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-picamera2 i2c-tools

if command -v raspi-config >/dev/null 2>&1; then
  echo "Enabling I2C..."
  sudo raspi-config nonint do_i2c 0 || echo "Could not enable I2C automatically; enable it with raspi-config."
fi

echo "Creating node virtual environment at $VENV_DIR..."
python3 -m venv --system-site-packages "$VENV_DIR"

echo "Installing node Python dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$NODE_DIR/requirements.txt"

echo "Writing $ENV_FILE..."
cat > "$ENV_FILE" <<EOF
SKYHUB_NODE_NODE_ID=$NODE_ID
SKYHUB_NODE_CAMERA_DRIVER=$CAMERA_DRIVER
SKYHUB_NODE_SERVER_WS_BASE_URL=$SERVER_WS_BASE_URL
SKYHUB_NODE_ENVIRONMENT_SENSOR_DRIVER=$ENVIRONMENT_SENSOR_DRIVER
SKYHUB_NODE_ENVIRONMENT_INTERVAL_SECONDS=30
SKYHUB_NODE_BME280_I2C_BUS=$BME280_I2C_BUS
SKYHUB_NODE_BME280_I2C_ADDRESS=$BME280_I2C_ADDRESS
EOF

echo
echo "SkyHub node install complete."
echo
echo "Run it with:"
echo "  python3 skyhub.py node"
echo
echo "Current node config:"
echo "  node id: $NODE_ID"
echo "  camera driver: $CAMERA_DRIVER"
echo "  environment sensor: $ENVIRONMENT_SENSOR_DRIVER"
echo "  bme280 i2c: bus $BME280_I2C_BUS address $BME280_I2C_ADDRESS"
echo "  server websocket base url: $SERVER_WS_BASE_URL"
