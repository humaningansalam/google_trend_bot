#!/bin/bash

ARCH=$(uname -m)

if [[ "$ARCH" == "x86_64" ]]; then
  CHROMIUM_URL="https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64"
elif [[ "$ARCH" == "aarch64" ]]; then
  CHROMIUM_URL="https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_ARM64"
else
  echo "Unsupported architecture: $ARCH"
  exit 1
fi


wget -q "${CHROMIUM_URL}%2FLAST_CHANGE?alt=media" -O LAST_CHANGE
export LATEST=$(cat LAST_CHANGE)
wget "${CHROMIUM_URL}%2F${LATEST}%2Fchrome-linux.zip?alt=media" -O chrome-linux.zip
unzip chrome-linux.zip
mv chrome-linux /usr/bin/chromium
chmod -R +x /usr/bin/chromium

rm LAST_CHANGE chrome-linux.zip
