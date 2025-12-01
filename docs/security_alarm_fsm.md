# Security Alarm FSM

```mermaid

---
title: Security Alarm FSM
---

stateDiagram-v2

    [*]-->DISARMED

    DEACTIVATED-->DISARMED : Long Press

    DISARMED-->ARMED : Schedule
    DISARMED-->DEACTIVATED : Long Press

    ARMED-->TRIGGERED : Sensor Triggered
    ARMED-->DISARMED : Schedule
    ARMED-->DEACTIVATED : Long Press

    TRIGGERED-->DISARMED : Schedule
    TRIGGERED-->DEACTIVATED : Long Press

```
