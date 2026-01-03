# Smart Learning Thermostat for Home Assistant

![Smart Learning Thermostat Logo](logo.png)

The **Smart Learning Thermostat** is a proactive heating controller for Home Assistant. Inspired by modern smart thermostats, it learns your home's thermal characteristics to ensure your rooms reach the desired temperature exactly when you need them to, while minimizing energy waste.

## 🌟 Key Features

* **Adaptive Learning**: Automatically calculates and refines your home's **Heat Up Rate** and **Heat Loss Rate** based on actual performance data.
* **Proactive Pre-heating**: Predicts how long it will take to reach your `Comfort Temperature` and starts the boiler early so your home is ready the moment your schedule begins.
* **Overshoot Protection**: Monitors "thermal lag" and shuts off the boiler before the target is reached to prevent the room from becoming too hot.
* **Intelligent Prediction**: A dedicated sensor provides the exact time for the next heating cycle, adjusted for preheating (e.g., "07:15" or "Mon 06:30").
* **Hysteresis Management**: Built-in adjustable hysteresis prevents boiler short-cycling, protecting your hardware.

## 📊 Diagnostic & Prediction Sensors

The integration automatically creates diagnostic entities to give you full visibility into your heating system's efficiency:

* **Heat Up Rate**: Measures thermal gain in **°C/min**.
* **Heat Loss Rate**: Measures how fast your room cools when the heating is off (**°C/min**).
* **Learned Overshoot**: Displays the calculated thermal overshoot in **°C**.
* **Next Fire Time**: Displays "Now" if active, "Preheating" during early starts, or a formatted timestamp for the next predicted run.

## ⚙️ Configuration Parameters

Accessible via the **Options Flow**, you can tune your thermostat without restarting:

* **Comfort Temperature**: Your target temperature for active schedule periods.
* **Setback Temperature**: The energy-saving "economy" temperature used when the schedule is off.
* **Hysteresis**: The temperature buffer to prevent frequent switching.
* **Max Boiler Runtime**: A safety watchdog that forces the boiler off if a cycle runs too long.
* **Min Burn Time**: The minimum runtime required for the system to trust and "learn" from a heating cycle.

## 📦 Installation

### HACS (Recommended)
1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the top right and select **Custom repositories**.
3. Paste your GitHub URL and select **Integration** as the category.
4. Click **Download**, then restart Home Assistant.

### Manual
1. Download the `smart_learning_thermostat` folder.
2. Copy it to your `custom_components/` directory.
3. Restart Home Assistant.

## 🚀 Getting Started

1. Navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** and search for **Smart Learning Thermostat**.
3. Define your **Heater Switch**, **Temperature Sensor**, and optional **Schedule Entity**.

## 📝 License
This project is licensed under the MIT License.
