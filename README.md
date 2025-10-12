[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support%20My%20Work-orange)](https://buymeacoffee.com/jmzg93)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue)](https://www.paypal.com/donate?business=j_manuel_za@hotmail.com)

# Kobold VR7 Home Assistant Integration

💡 **Support My Work**  
Hi there! If you enjoy this project and would like to support my work, consider buying me a coffee or donating via PayPal. Your contributions help me continue developing and sharing tools like this one.
- [Buy Me a Coffee ☕](https://buymeacoffee.com/jmzg93)
- [Donate via PayPal 💙](https://www.paypal.com/donate?business=j_manuel_za@hotmail.com)

---

## Tested Robot
- **Kobold VR7**

## Description

This integration allows Home Assistant users to control and monitor their Kobold vacuum robots via the official Kobold API (version 2). It includes support for advanced features like:
- Real-time robot status updates via WebSocket.
- Start, pause, stop, and return-to-base commands.
- Monitoring battery status, errors, and available commands.
- Zone-specific and map-specific cleaning (only show maps with name).

### 🚧 **Work in Progress**
- As this is my first integration and my first time using Python, the code might not be the most efficient or well-structured. Your feedback and contributions are greatly appreciated!

## Features

- **Basic Control**:
  - Start, stop, and pause cleaning.
  - Send the robot back to its base.
  - Locate the robot.
  - Adjust fan speed with modes (`auto`, `eco`, `turbo`).
- **Zone and Map Cleaning**:
  - Start cleaning specific zones or entire maps.
- **Monitoring**:
  - Robot state (cleaning, docked, idle, etc.).
  - Battery level.
  - Charging status.
  - Error reporting.
  - Real-time updates via WebSocket.

## Prerequisites

- An active Kobold account.
- At least one Kobold vacuum robot configured via the official Kobold app.
- A running Home Assistant instance.

## Installation

### Installation via HACS

1. Ensure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance.
2. Go to **HACS > Integrations**.
3. Click on the three dots menu in the top right corner and select **Custom repositories**.
4. Add the repository URL `https://github.com/jmzg93/koboldHAIntegration` and select the category **Integration**.
5. Click **Add**.
6. The Kobold VR7 integration should now appear in the list of available integrations. Click **Install**.
7. Restart Home Assistant.

### Manual Installation

1. Clone or download this repository.
2. Copy the folder `custom_components/kobold_vr7` into the `custom_components` directory of your Home Assistant installation.
3. Restart Home Assistant.

### Configuration

1. Go to **Settings > Devices & Integrations** in Home Assistant.
2. Click **Add Integration** and search for **Kobold**.
3. Enter your email and the OTP code sent to the email associated with your robot.

---

## Services

The Kobold integration includes the following custom services:

### **`kobold_vr7.clean_zone`**

Starts cleaning one or multiple specific zones (must be from the same map).

- **Parameters**:
  - `zones_uuid` (required): The UUID of the zone(s) to clean. Multiple zones can be specified using comma separation (e.g., `"zone123456789,zone987654321"`).

### **`kobold_vr7.clean_map`**

Starts cleaning an entire map.

- **Parameters**:
  - `map_uuid` (required): The UUID of the map to clean.

---

## Usage

Once the integration is set up, entities corresponding to your Kobold robots will be added. You can interact with them via the Home Assistant dashboard or automations.

### Additional Documentation

- [Lovelace dashboard example](docs/lovelace-dashboard-example.md) – replicate the sample subview, automations, scripts, sensors, and helpers used to control the Kobold VR7 from Home Assistant.

> **Note:** The examples reference the `vacuum.roomba` entity. Replace it with the entity exposed by your own Kobold robot before applying the configurations.

### Supported Features

- **Robot Control**:
  - `vacuum.start`: Starts cleaning.
  - `vacuum.pause`: Pauses cleaning.
  - `vacuum.stop`: Stops cleaning.
  - `vacuum.return_to_base`: Sends the robot to its base.
  - `vacuum.locate`: Finds the robot.
- **Custom Services**:
  - `kobold_vr7.clean_zone`: Cleans a specific zone.
  - `kobold_vr7.clean_map`: Cleans an entire map.

---

## Entity Attributes

The integration provides detailed attributes for your robot entities:

| Attribute            | Description                                  |
|---------------------|----------------------------------------------|
| `state`             | Current state of the robot (`cleaning`, `idle`, `docked`, etc.). |
| `battery_level`     | Robot's battery level as a percentage.       |
| `is_charging`       | Indicates if the robot is charging.          |
| `errors`            | List of current errors (if any).             |
| `available_commands`| Commands currently available for the robot.  |
| `maps`              | List of available floorplans.                |
| `zones`             | Detailed information about zones in each map.|
| `fan_speed`         | Current fan speed mode (`auto`, `eco`, `turbo`). |
| `bag_status`        | Status of the vacuum's bag/container.        |

---

## Troubleshooting

If the integration fails to load, ensure that:

1. You have placed the `kobold_vr7` folder in the correct `custom_components` directory.
2. You have restarted Home Assistant after installing the integration.
3. Your Home Assistant instance has access to the internet for API calls.
4. Your Kobold account is active and the robot is properly set up in the official app.

Check the logs in **Settings > System > Logs** for detailed error messages. You can increase the logging level for this integration by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.kobold_vr7: debug
```

### Known Issues

If you see warnings in your logs about blocking SSL operations or entity service schemas, make sure you're using version 2.0.1 or later of this integration which addresses these Home Assistant compatibility issues.

#### System-Specific Notes
- On Raspberry Pi systems, some users may experience SSL-related warnings in the logs. Version 2.0.2 addresses these issues with an improved SSL context handling.
- If you encounter WebSocket connection issues, try increasing your network timeout settings or check if your network is blocking WebSocket connections.

---

## Multilingual Support

Starting from version 2.0.2, this integration supports multiple languages:
- English
- Spanish
- German

The language is automatically selected based on your Home Assistant locale settings.

---

## Contributing
We welcome contributions! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) file to get started.  
Have questions? Open an issue or reach out directly at [j_manuel_za@hotmail.com](mailto:j_manuel_za@hotmail.com).

---

## License
[LICENSE.md](LICENSE.md)

---

💙 **Thank you for supporting this project!**  
If you encounter issues or have feature requests, feel free to open an issue on GitHub. Your feedback helps improve the integration for everyone!

## Changelog

### 2.0.6 (2025-10-12)
- Added a dedicated battery sensor entity for each Kobold robot with shared device information
- Removed the deprecated battery attribute from the vacuum entity while keeping the state synchronized
- Ensured battery updates run on the Home Assistant event loop to avoid thread-safety issues
- Simplified battery sensor naming to avoid repeating the robot name in generated entity IDs

### 2.0.5 (2025-05-30)
- Enhanced zone cleaning to support multiple zones at once via comma-separated UUIDs
- Added validation to ensure all zones belong to the same map when cleaning multiple zones
- Improved error handling and logging for zone cleaning
- Updated documentation to reflect the new multi-zone cleaning capability

### 2.0.4 (2025-06-01)
- Implemented zone-specific and map-specific cleaning features
- Fixed the way robot maps are processed to make zone cleaning fully functional
- Updated documentation to reflect the new features
- Made robot map responses more resilient by making fields optional
- Improved default cleaning behavior: standard start command now cleans without map constraints
- Added clearer documentation for map and zone selection via Home Assistant services

### 2.0.3 (2025-05-20)
- Fixed an issue with the CleaningCenter constructor that required mandatory parameters
- Added default values for bag_status, base_error and state in CleaningCenter
- Improved robustness when handling incomplete WebSocket responses

### 2.0.2 (2025-05-17)
- Added default values for available commands to prevent errors with incomplete responses
- Fixed SSL context creation in WebSocket client to avoid blocking calls on Raspberry Pi systems
- Improved error handling and logging
- Added multilingual support with German and Spanish translations
- Added dynamic language detection to use the Home Assistant configured locale
- Enhanced attribute reporting with bag status and fan speed information
- Improved troubleshooting documentation

### 2.0.1 (2025-05-13)
- Fixed Home Assistant 2025.5.0+ compatibility issues:
  - Updated WebSocket client to avoid blocking SSL operations
  - Fixed entity service registrations to use proper schema format
  - Properly implemented activity property using VacuumActivity enum
