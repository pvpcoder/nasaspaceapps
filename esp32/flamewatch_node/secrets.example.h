// Copy this file to secrets.h (same folder) and fill it in.
// secrets.h is git-ignored, so passwords never reach GitHub.
#pragma once

// 0 = normal WiFi / phone hotspot (recommended for the demo)
// 1 = eduroam (WPA2-Enterprise)
#define USE_EDUROAM 0

// ---- Phone hotspot ----
// iPhone: turn on "Maximize Compatibility". Android: set the band to 2.4 GHz.
const char* WIFI_SSID = "YOUR_HOTSPOT_NAME";
const char* WIFI_PASS = "YOUR_HOTSPOT_PASSWORD";

// ---- eduroam ----
const char* EAP_SSID     = "eduroam";
const char* EAP_IDENTITY = "you@school.ca";   // usually the same as the username
const char* EAP_USERNAME = "you@school.ca";
const char* EAP_PASSWORD = "your-password";

// ---- Wireless (OTA) uploads ----
const char* OTA_PASSWORD = "change-me";
