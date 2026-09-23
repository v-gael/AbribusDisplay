#!/bin/bash
set -e

# =============================================================
# Setup automatique écran SPI 3.5" (clone waveshare35a) sur
# Raspberry Pi OS. A executer avec sudo sur un OS neuf.
# =============================================================

CONFIG_FILE="/boot/firmware/config.txt"
OVERLAYS_DIR="/boot/firmware/overlays"

# --- Compat anciennes versions de Raspberry Pi OS (chemin /boot/) ---
if [ ! -f "$CONFIG_FILE" ]; then
  CONFIG_FILE="/boot/config.txt"
  OVERLAYS_DIR="/boot/overlays"
fi

echo "=== Setup écran SPI 3.5\" (waveshare35a) ==="
echo ""

# --- Vérification root ---
if [ "$EUID" -ne 0 ]; then
  echo "Ce script doit être lancé avec sudo."
  echo "Usage : sudo ./setup-ecran-pi.sh"
  exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Erreur : impossible de trouver config.txt (ni /boot/firmware/ ni /boot/)."
  exit 1
fi

echo "Fichier config.txt détecté : $CONFIG_FILE"
echo ""

# --- Choix de la rotation ---
# 90 : écran monté à l'horizontale alors que le framebuffer natif est en
# portrait (320x480) — valeur validée empiriquement sur ce déploiement.
read -p "Orientation de l'écran - rotate (0/90/180/270) [défaut: 90] : " ROTATE
ROTATE=${ROTATE:-90}

# --- Sauvegarde de config.txt ---
BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo "Sauvegarde créée : $BACKUP_FILE"
echo ""

# --- 1. Activer le SPI ---
echo "--- Activation du SPI ---"
if grep -q "^dtparam=spi=on" "$CONFIG_FILE"; then
  echo "SPI déjà activé."
elif grep -q "^#dtparam=spi=on" "$CONFIG_FILE"; then
  sed -i "s/^#dtparam=spi=on/dtparam=spi=on/" "$CONFIG_FILE"
  echo "SPI activé (ligne décommentée)."
else
  echo "dtparam=spi=on" >> "$CONFIG_FILE"
  echo "SPI activé (ligne ajoutée)."
fi
echo ""

# --- 2. Désactiver le driver KMS (conflit avec fbtft) ---
echo "--- Désactivation de vc4-kms-v3d ---"
if grep -q "^dtoverlay=vc4-kms-v3d" "$CONFIG_FILE"; then
  sed -i "s/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/" "$CONFIG_FILE"
  echo "vc4-kms-v3d commenté."
elif grep -q "^#dtoverlay=vc4-kms-v3d" "$CONFIG_FILE"; then
  echo "vc4-kms-v3d déjà commenté."
else
  echo "Ligne vc4-kms-v3d non trouvée (peut-être absente sur cette version) - on continue."
fi
echo ""

# --- 3. Télécharger et installer l'overlay waveshare35a ---
echo "--- Installation de l'overlay waveshare35a ---"
if [ -f "$OVERLAYS_DIR/waveshare35a.dtbo" ]; then
  echo "Overlay déjà présent dans $OVERLAYS_DIR, on le remplace par une version fraîche."
fi

TMP_DIR=$(mktemp -d)
wget -q -O "$TMP_DIR/Waveshare35a.zip" "https://files.waveshare.com/wiki/common/Waveshare35a.zip"
unzip -o -q "$TMP_DIR/Waveshare35a.zip" -d "$TMP_DIR"

DTBO_FILE=$(find "$TMP_DIR" -name "waveshare35a.dtbo" | head -n 1)
if [ -z "$DTBO_FILE" ]; then
  echo "Erreur : waveshare35a.dtbo introuvable dans l'archive téléchargée."
  rm -rf "$TMP_DIR"
  exit 1
fi

cp "$DTBO_FILE" "$OVERLAYS_DIR/waveshare35a.dtbo"
rm -rf "$TMP_DIR"
echo "Overlay copié dans $OVERLAYS_DIR/waveshare35a.dtbo"
echo ""

# --- 4. Ajouter la config écran dans config.txt ---
echo "--- Ajout de la configuration écran ---"
if grep -q "dtoverlay=waveshare35a" "$CONFIG_FILE"; then
  echo "Configuration waveshare35a déjà présente dans config.txt, rien à ajouter."
  echo "(Si tu veux changer la rotation, édite manuellement la ligne dtoverlay=waveshare35a,rotate=XX)"
else
  {
    echo ""
    echo "# --- Ecran SPI 3.5\" waveshare35a (ajouté par setup-ecran-pi.sh) ---"
    echo "dtoverlay=waveshare35a,rotate=${ROTATE}"
    echo "hdmi_force_hotplug=1"
    echo "hdmi_group=2"
    echo "hdmi_mode=1"
    echo "hdmi_mode=87"
    echo "hdmi_cvt 480 320 60 6 0 0 0"
    echo "hdmi_drive=2"
  } >> "$CONFIG_FILE"
  echo "Configuration ajoutée avec rotate=${ROTATE}."
fi
echo ""

# --- 5. Désactiver le getty sur tty1 (bloque fbi sinon : il ne peut pas
# prendre le contrôle de la console pour passer en mode graphique) ---
echo "--- Désactivation de getty@tty1 ---"
systemctl stop getty@tty1.service 2>/dev/null || true
systemctl disable getty@tty1.service 2>/dev/null || true
echo "getty@tty1 désactivé."
echo ""

# --- 6. Installer Docker (fbi tourne dans le conteneur, plus besoin sur l'hôte) ---
echo "--- Installation de Docker ---"
if command -v docker >/dev/null 2>&1; then
  echo "Docker déjà installé."
else
  curl -fsSL https://get.docker.com | sh
  echo "Docker installé (Engine + plugin compose)."
fi

if [ -n "$SUDO_USER" ]; then
  usermod -aG docker "$SUDO_USER"
  echo "Utilisateur $SUDO_USER ajouté au groupe docker (effectif après redémarrage)."
fi
echo ""

# --- Résumé ---
echo "=== Setup terminé ==="
echo ""
echo "Un redémarrage est nécessaire pour appliquer la configuration."
echo "Après reboot, vérifie avec :"
echo "  dmesg | grep -i ili9486"
echo "  dmesg | grep -i ads7846"
echo ""
read -p "Redémarrer maintenant ? (y/N) : " CONFIRM_REBOOT
if [[ "$CONFIRM_REBOOT" =~ ^[Yy]$ ]]; then
  reboot
else
  echo "N'oublie pas de redémarrer manuellement avec : sudo reboot"
fi