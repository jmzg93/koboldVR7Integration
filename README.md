# Kobold Home Assistant Integration
## Robot testeado
- **Kobold VR7**
## Descripción

Esta integración permite a los usuarios de Home Assistant controlar y monitorizar sus robots aspiradores Kobold a través de la API oficial de Kobold version 2. Incluye soporte para funciones avanzadas como:
- Control en tiempo real de los estados del robot mediante WebSocket.
- Inicio, pausa y retorno a la base.
- Monitorización del estado de la batería, errores y comandos disponibles.

## Características

- **Control básico**:
    - Iniciar y pausar la limpieza.
    - Enviar el robot a la base.
- **Monitorización**:
    - Estado del robot (limpiando, en base, etc.).
    - Nivel de batería.
    - Estado de carga.
    - Disponibilidad de comandos.
- **Soporte para WebSocket**:
    - Actualización en tiempo real del estado del robot.

## Requisitos Previos

- Una cuenta activa en Kobold.
- Al menos un robot aspirador Kobold configurado en la aplicación oficial de Kobold.
- Home Assistant instalado y configurado.

## Instalación

### Manual

1. Clona o descarga este repositorio.
2. Copia la carpeta `custom_components/KoboldIntegration` en el directorio `custom_components` de tu instalación de Home Assistant.
3. Reinicia Home Assistant.

### Configuración

1. Accede a **Configuración > Dispositivos e Integraciones** en Home Assistant.
2. Haz clic en **Añadir Integración** y busca **Kobold**.
3. Ingresa tu correo electrónico y el token de autenticación (`id_token`) obtenido desde la aplicación oficial de Kobold.

## Uso

Una vez configurada la integración, se añadirán las entidades correspondientes para tus robots Kobold. Puedes interactuar con ellos mediante el panel de Home Assistant o automatizaciones.

### Funcionalidades Soportadas

- **Control del robot**:
    - `vacuum.start`: Inicia la limpieza.
    - `vacuum.pause`: Pausa la limpieza.
    - `vacuum.return_to_base`: Envía el robot a la base.
- **Automatizaciones**:
    - Usa las entidades y atributos para crear automatizaciones basadas en el estado, nivel de batería, errores, etc.

### Atributos de la Entidad

| Atributo            | Descripción                                  |
|---------------------|----------------------------------------------|
| `state`             | Estado actual del robot (`cleaning`, `idle`, `docked`, etc.). |
| `battery_level`     | Nivel de batería del robot en porcentaje.    |
| `is_charging`       | Indica si el robot está cargando.            |
| `errors`            | Lista de errores actuales (si existen).     |
| `available_commands`| Comandos disponibles para el robot.          |

### Ejemplo de Automatización

```yaml
alias: Pausar limpieza al salir de casa
trigger:
  - platform: state
    entity_id: group.family
    to: 'not_home'
condition: []
action:
  - service: vacuum.pause
    target:
      entity_id: vacuum.kobold