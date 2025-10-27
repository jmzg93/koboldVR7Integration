DOMAIN = "kobold_vr7"
CONF_EMAIL = "email"
CONF_OTP = "otp"
CONF_ID_TOKEN = "id_token"
CONF_MARKET = "market"
ORBITAL_HOST = "https://orbital.ksecosys.com"
AUTH_HOST = "https://mykobold.eu.auth0.com"
COMPANION_HOST = "https://api-2-prod.companion.kobold.vorwerk.com"
COMPANION_WS_URL = "wss://api-2-prod.companion.kobold.vorwerk.com/api/ws"
MOBILE_APP_VERSION = "3.12.1"
MOBILE_APP_BUILD = "40408"
MOBILE_APP_OS = "android"
MOBILE_APP_OS_VERSION = "11"
MOBILE_APP_USER_AGENT = "okhttp/5.1.0"
MOBILE_APP_ACCEPT_ENCODING = "gzip"
SIGNAL_ROBOT_BATTERY = "kobold_vr7_battery"

# Mercados soportados y el idioma asociado que necesitan las APIs
DEFAULT_MARKET = "es"
SUPPORTED_MARKETS = {
    "de": {
        "label": "Alemania",
        "locale": "de",
        "accept_language": "de-DE",
    },
    "es": {
        "label": "España",
        "locale": "es",
        "accept_language": "es-ES",
    },
    "fr": {
        "label": "Francia",
        "locale": "fr",
        "accept_language": "fr-FR",
    },
    "it": {
        "label": "Italia",
        "locale": "it",
        "accept_language": "it-IT",
    },
    "en": {
        "label": "Reino Unido / Internacional",
        "locale": "en",
        "accept_language": "en-EN",
    },
}

# Descripciones amigables para los códigos de error recibidos por WebSocket
ERROR_CODE_DESCRIPTIONS = {
    "navigation_path_problems_returning_home": "Problemas de navegación al regresar a la base",
    "brush_stuck": "Cepillo bloqueado",
    "dustbin_missing": "Depósito de polvo no colocado",
    "bin_full": "Depósito de polvo lleno",
    "cleaning_path_blocked": "Trayectoria de limpieza bloqueada",
}
