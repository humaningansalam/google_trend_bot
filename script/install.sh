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
echo $(cat LAST_CHANGE) > latest
export LATEST=$(cat latest)
wget "${CHROMIUM_URL}%2F${LATEST}%2Fchrome-linux.zip?alt=media" -O chrome-linux.zip
unzip chrome-linux.zip
mv chrome-linux /usr/bin/chromium
chmod -R +x /usr/bin/chromium
CHROMIUM_VERSION=$(/usr/bin/chromium/chrome --version | grep -oP '[0-9.]+')
wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE" -O LATEST_RELEASE
CHROMEDRIVER_VERSION=$(cat LATEST_RELEASE)
wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" -O chromedriver_linux64.zip
unzip chromedriver_linux64.zip
mv chromedriver /usr/bin/chromedriver
chmod +x /usr/bin/chromedriver
rm LAST_CHANGE chrome-linux.zip LATEST_RELEASE chromedriver_linux64.zip