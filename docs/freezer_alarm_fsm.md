# Freezer Alarm FSM

```mermaid

stateDiagram-v2

    TempNormal
    TempHigh
    Disabled
    OfflineDay
    OfflineNight

    [*]-->TempNormal

    TempNormal-->OfflineDay: Offline & Day
    TempNormal-->OfflineNight: Offline & Night
    TempNormal-->TempHigh: Temp high

    OfflineDay-->OfflineNight: schedule
    OfflineDay-->TempNormal: Online
    OfflineDay-->Disabled: Long Press

    OfflineNight-->OfflineDay: schedule
    OfflineNight-->TempNormal: Online
    OfflineNight-->Disabled: Long Press

    Disabled-->TempNormal: Long Press
    Disabled-->TempNormal: Online<br/>&<br/>Temp Low

    TempHigh-->Disabled

```