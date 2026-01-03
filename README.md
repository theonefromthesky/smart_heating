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

```mermaid
flowchart TD
    %% --- Styles ---
    classDef trigger fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef decision fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef action fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px;
    classDef state fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;

    %% --- Entry Points ---
    Start([Trigger: Timer / Sensor Update / Schedule Change]):::trigger
    Start --> CheckHVAC

    %% --- Core Logic ---
    CheckHVAC{HVAC Mode is OFF?}:::decision
    CheckHVAC -- Yes --> BoilerOFF[Ensure Boiler OFF]:::action
    CheckHVAC -- No --> CheckSchedChange

    CheckSchedChange{Did Schedule State<br/>Change?}:::decision
    CheckSchedChange -- Yes --> ResetManual[Reset Manual Mode<br/>Return to Auto]:::action
    CheckSchedChange -- No --> CheckManual

    ResetManual --> CheckManual
    
    %% --- Target Calculation ---
    CheckManual{Manual Override<br/>Active?}:::decision
    CheckManual -- Yes --> KeepTarget[Keep User Target]:::state
    CheckManual -- No --> CheckSchedState

    subgraph Auto_Mode [Auto Mode Logic]
        CheckSchedState{Schedule Entity<br/>is ON?}:::decision
        CheckSchedState -- Yes --> SetComfort[Target = Comfort Temp]:::state
        CheckSchedState -- No --> CheckPreheat
        
        CheckPreheat{Preheat Enabled?}:::decision
        CheckPreheat -- No --> SetSetback[Target = Setback Temp]:::state
        CheckPreheat -- Yes --> CalcPreheat[[Calculate Time Needed<br/>(Diff / HeatUpRate)]]
        
        CalcPreheat --> CheckTime{Is it time to<br/>Heat Up?}:::decision
        CheckTime -- Yes --> SetPreheat[Target = Comfort Temp<br/>(Preheat Mode)]:::state
        CheckTime -- No --> SetSetback
    end

    %% --- Hysteresis Logic ---
    KeepTarget --> CalcPoints
    SetComfort --> CalcPoints
    SetSetback --> CalcPoints
    SetPreheat --> CalcPoints

    CalcPoints[Calculate Thresholds<br/>ON Point = Target - Hysteresis<br/>OFF Point = Target - Overshoot]:::action
    CalcPoints --> CheckBoilerState

    CheckBoilerState{Is Boiler<br/>Currently ON?}:::decision
    
    %% --- Boiler is ON ---
    CheckBoilerState -- Yes --> CheckTargetReached
    CheckTargetReached{Current Temp >=<br/>OFF Point?}:::decision
    CheckTargetReached -- Yes --> TurnOff[Turn Boiler OFF]:::action
    CheckTargetReached -- No --> CheckSafety
    
    CheckSafety{Runtime ><br/>Max On Time?}:::decision
    CheckSafety -- Yes (Safety Cutoff) --> TurnOff
    CheckSafety -- No --> DoNothing[Maintain State]:::state

    %% --- Boiler is OFF ---
    CheckBoilerState -- No --> CheckDemand
    CheckDemand{Current Temp <=<br/>ON Point?}:::decision
    CheckDemand -- Yes --> TurnOn[Turn Boiler ON]:::action
    CheckDemand -- No --> DoNothing

    %% --- Learning Cycle ---
    TurnOff -- Calculate Rate --> UpdateLearning[[Update Learned<br/>Heat Up Rate]]:::trigger
    TurnOn -- Reset Timer --> End([End Loop]):::trigger
    DoNothing --> End
    UpdateLearning --> End
    BoilerOFF --> End
```
