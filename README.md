[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support%20My%20Work-orange)](https://buymeacoffee.com/jmzg93)

# Kobold Home Assistant Integration

💡 **Support My Work**  
Hi there! If you enjoy this project and would like to support my work, consider buying me a coffee. Your contributions help me continue developing and sharing tools like this one. [Click here to support me! ☕](https://buymeacoffee.com/jmzg93)

---

## Tested Robot
- **Kobold VR7**

## Description

This integration allows Home Assistant users to control and monitor their Kobold vacuum robots via the official Kobold API (version 2). It includes support for advanced features like:
- Real-time robot status updates via WebSocket.
- Start, pause, and return to base commands.
- Monitoring battery status, errors, and available commands.

## Features

- **Basic Control**:
    - Start and pause cleaning.
    - Send the robot back to its base.
- **Monitoring**:
    - Robot state (cleaning, docked, idle, etc.).
    - Battery level.
    - Charging status.
    - Available commands.
- **WebSocket Support**:
    - Real-time robot status updates.

## Prerequisites

- An active Kobold account.
- At least one Kobold vacuum robot configured via the official Kobold app.
- A running Home Assistant instance.

## Installation

### Manual

1. Clone or download this repository.
2. Copy the folder `custom_components/KoboldIntegration` into the `custom_components` directory of your Home Assistant installation.
3. Restart Home Assistant.

### Configuration

1. Go to **Settings > Devices & Integrations** in Home Assistant.
2. Click **Add Integration** and search for **Kobold**.
3. Enter your email and the OTP code sent to the email associated with your robot.

## Usage

Once the integration is set up, entities corresponding to your Kobold robots will be added. You can interact with them via the Home Assistant dashboard or automations.

### Supported Features

- **Robot Control**:
    - `vacuum.start`: Starts cleaning.
    - `vacuum.pause`: Pauses cleaning.
    - `vacuum.return_to_base`: Sends the robot to its base.
- **Automations**:
    - Use the entities and attributes to create automations based on state, battery level, errors, and more.

### Entity Attributes

| Attribute            | Description                                  |
|---------------------|----------------------------------------------|
| `state`             | Current state of the robot (`cleaning`, `idle`, `docked`, etc.). |
| `battery_level`     | Robot's battery level as a percentage.       |
| `is_charging`       | Indicates if the robot is charging.          |
| `errors`            | List of current errors (if any).             |
| `available_commands`| Commands currently available for the robot.  |