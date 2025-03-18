import logging
import os
import environ
import subprocess
from django.http import HttpResponseForbidden
from django.shortcuts import render

# Load environment variables
env = environ.Env()
environ.Env.read_env(env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Allowed Network Configurations
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
ALLOWED_SSIDS = env.list("ALLOWED_SSIDS", default=[])

logger = logging.getLogger(__name__)

class IPWhitelistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_ssid = self.get_current_ssid()
        
        # Debugging: Print loaded SSIDs
        print(f"Loaded ALLOWED_SSIDS: {ALLOWED_SSIDS}")
        print(f"Detected SSID: {current_ssid}")

        # ✅ Allow if connected to the allowed WiFi SSID
        if current_ssid and current_ssid in ALLOWED_SSIDS:
            return self.get_response(request)

        # ❌ Block access otherwise
        logger.warning(f"Unauthorized access attempt (SSID: {current_ssid})")
        return self.custom_forbidden_response(request)

    def get_current_ssid(self):
        """Get the current connected WiFi SSID (Windows & Linux/macOS)"""
        try:
            if os.name == "nt":  # Windows
                output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode(errors="ignore")
                for line in output.split("\n"):
                    if "SSID" in line and "BSSID" not in line:
                        return line.split(": ", 1)[1].strip()

            else:  # Linux/macOS
                try:
                    output = subprocess.check_output("iwgetid -r", shell=True).decode(errors="ignore").strip()
                    if output:
                        return output  # ✅ Primary method works

                    # 🔄 Fallback: Check `/proc/net/wireless`
                    with open("/proc/net/wireless") as f:
                        lines = f.readlines()
                        if len(lines) > 2:
                            return lines[2].split()[0].strip(":")
                except FileNotFoundError:
                    logger.error("Command `iwgetid` not found. Install `wireless-tools` package.")
                    return None  # Explicitly return if command is missing

        except Exception as e:
            logger.error(f"Failed to get WiFi SSID: {e}")
            return None  # ❌ Return None if SSID retrieval fails

        else:  
            logger.info("No SSID found.")  
            return None  # ⬅ Explicitly return None in the `else` block


    def custom_forbidden_response(self, request):
        """Render a custom 403 Forbidden page"""
        return render(request, "front/includes/403_forbidden.html", status=403)
