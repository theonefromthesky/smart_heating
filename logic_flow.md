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

    CheckSchedChange{"Did Schedule State<br/>Change?"}:::decision
    CheckSchedChange -- Yes --> ResetManual["Reset Manual Mode<br/>Return to Auto"]:::action
    CheckSchedChange -- No --> CheckManual

    ResetManual --> CheckManual
    
    %% --- Target Calculation ---
    CheckManual{"Manual Override<br/>Active?"}:::decision
    CheckManual -- Yes --> KeepTarget[Keep User Target]:::state
    CheckManual -- No --> CheckSchedState

    subgraph Auto_Mode [Auto Mode Logic]
        CheckSchedState{"Schedule Entity<br/>is ON?"}:::decision
        CheckSchedState -- Yes --> SetComfort[Target = Comfort Temp]:::state
        CheckSchedState -- No --> CheckPreheat
        
        CheckPreheat{"Preheat Enabled?"}:::decision
        CheckPreheat -- No --> SetSetback[Target = Setback Temp]:::state
        
        %% FIXED LINE BELOW: Added double quotes around the text
        CheckPreheat -- Yes --> CalcPreheat[["Calculate Time Needed<br/>(Diff / HeatUpRate)"]]
        
        CalcPreheat --> CheckTime{"Is it time to<br/>Heat Up?"}:::decision
        CheckTime -- Yes --> SetPreheat["Target = Comfort Temp<br/>(Preheat Mode)"]:::state
        CheckTime -- No --> SetSetback
    end

    %% --- Hysteresis Logic ---
    KeepTarget --> CalcPoints
    SetComfort --> CalcPoints
    SetSetback --> CalcPoints
    SetPreheat --> CalcPoints

    CalcPoints["Calculate Thresholds<br/>ON Point = Target - Hysteresis<br/>OFF Point = Target - Overshoot"]:::action
    CalcPoints --> CheckBoilerState

    CheckBoilerState{"Is Boiler<br/>Currently ON?"}:::decision
    
    %% --- Boiler is ON ---
    CheckBoilerState -- Yes --> CheckTargetReached
    CheckTargetReached{"Current Temp >=<br/>OFF Point?"}:::decision
    CheckTargetReached -- Yes --> TurnOff[Turn Boiler OFF]:::action
    CheckTargetReached -- No --> CheckSafety
    
    CheckSafety{"Runtime ><br/>Max On Time?"}:::decision
    CheckSafety -- Yes (Safety Cutoff) --> TurnOff
    CheckSafety -- No --> DoNothing[Maintain State]:::state

    %% --- Boiler is OFF ---
    CheckBoilerState -- No --> CheckDemand
    CheckDemand{"Current Temp <=<br/>ON Point?"}:::decision
    CheckDemand -- Yes --> TurnOn[Turn Boiler ON]:::action
    CheckDemand -- No --> DoNothing

    %% --- Learning Cycle ---
    TurnOff -- Calculate Rate --> UpdateLearning[["Update Learned<br/>Heat Up Rate"]]:::trigger
    TurnOn -- Reset Timer --> End([End Loop]):::trigger
    DoNothing --> End
    UpdateLearning --> End
    BoilerOFF --> End
