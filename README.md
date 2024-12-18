
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
- Zone-specific and map-specific cleaning.

### 🚧 **Work in Progress**
- Features like **cleaning specific zones** and **cleaning entire maps** are currently under development and may not work as expected.
- As this is my first integration and my first time using Python, the code might not be the most efficient or well-structured. Your feedback and contributions are greatly appreciated!

## Features

- **Basic Control**:
  - Start, stop, and pause cleaning.
  - Send the robot back to its base.
  - Locate the robot.
  - Adjust fan speed with modes (`auto`, `eco`, `turbo`).
- **Zone and Map Cleaning**:
  - Start cleaning specific zones or entire maps (in progress).
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

### **`vacuum.clean_zone`**

Starts cleaning a specific zone.  
**Note**: This service is under development and may not function correctly.

- **Parameters**:
  - `zone_uuid` (required): The UUID of the zone to clean.

### **`vacuum.clean_map`**

Starts cleaning an entire map.  
**Note**: This service is under development and may not function correctly.

- **Parameters**:
  - `map_uuid` (required): The UUID of the map to clean.

---

## Usage

Once the integration is set up, entities corresponding to your Kobold robots will be added. You can interact with them via the Home Assistant dashboard or automations.

### Supported Features

- **Robot Control**:
  - `vacuum.start`: Starts cleaning.
  - `vacuum.pause`: Pauses cleaning.
  - `vacuum.stop`: Stops cleaning.
  - `vacuum.return_to_base`: Sends the robot to its base.
  - `vacuum.locate`: Finds the robot.
- **Custom Services**:
  - `vacuum.clean_zone`: Cleans a specific zone (in progress).
  - `vacuum.clean_map`: Cleans an entire map (in progress).

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

---

## Troubleshooting

If the integration fails to load, ensure that:

1. You have placed the `kobold_vr7` folder in the correct `custom_components` directory.
2. You have restarted Home Assistant after installing the integration.
3. Your Home Assistant instance has access to the internet for API calls.

Check the logs in **Settings > System > Logs** for detailed error messages.

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
