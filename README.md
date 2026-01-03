Smart Learning Thermostat for Home Assistant
A modern, proactive heating controller for Home Assistant that learns your home's thermal characteristics to provide precise comfort while saving energy. Similar to a Nest thermostat, it predicts exactly when to fire your boiler to reach your target temperature right on time.

🚀 Key Features
Adaptive Learning: Automatically calculates your home's Heat Up Rate and Heat Loss Rate based on real-world performance.

Smart Pre-heating: Uses learned data to start heating early, ensuring your room is at the Comfort Temperature exactly when your schedule starts.

Overshoot Protection: Learns how much your radiators continue to heat the room after the boiler is off and adjusts the cutoff point to prevent wasting gas.

Next-Fire Prediction: A dedicated sensor tells you exactly when the heating will next turn on (e.g., "07:15" or "Mon 06:30").

Hysteresis Control: Prevents "short-cycling" of your boiler, extending the life of your heating system.

Diagnostic Sensors: Includes 4 built-in sensors to monitor your home's thermal efficiency in real-time.

🛠️ Diagnostic Sensors Included
Once installed, the integration provides the following diagnostic entities:

Heat Up Rate: How many °C your room gains per minute.

Heat Loss Rate: How fast your room cools down when the heating is off.

Learned Overshoot: The "thermal lag" of your system in °C.

Next Fire Time: The calculated start time for the next heating cycle.

📦 Installation
Option 1: HACS (Recommended)
Open HACS in your Home Assistant instance.

Click the three dots in the top right and select Custom repositories.

Paste your GitHub URL and select Integration as the category.

Click Install.

Restart Home Assistant.

Option 2: Manual
Download the smart_learning_thermostat folder from this repository.

Copy it into your custom_components/ directory.

Restart Home Assistant.

⚙️ Setup & Configuration
Go to Settings > Devices & Services.

Click Add Integration and search for Smart Learning Thermostat.

Follow the UI prompts to select your:

Boiler Switch: The switch or actuator that turns your heater on.

Temperature Sensor: The main sensor for the room.

Schedule Entity (Optional): A Home Assistant schedule or input_boolean that defines your "On" times.

Options Flow
You can change all parameters (Comfort Temp, Setback Temp, Max Runtime) at any time by clicking Configure on the integration page.

📝 License
This project is licensed under the MIT License - see the LICENSE file for details.
