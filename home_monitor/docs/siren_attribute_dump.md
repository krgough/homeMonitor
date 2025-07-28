# Hive Siren

Siren attribute dump below. Taken on 2025-07-20. Hive are removing support for the alarm System
so I'm trying to add it to my rpi setup to control it myself.

## Pairing
You need to joint the device then within a few minutes write the eui of the coordinator
to the `iasCieAddress` attribute in the `IAS zone Cluster`

```bash
at+pjoin:ff
```
Note the node address of the device once it joins then us the siren_pairing script to wite the iasCieAddress


## Custom Commands

It was possible in the hive app to do the folowing...
- turn off the tamper alarm for 60mins
- turn off the blue led indicator

I think these must have been implemeted as custom Commands

## Attribute Dump

Serial port opened.../dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-port0
Serial port read handler thread started.
Serial port write handler thread started.
rxQueue is ON
listenerQueue is OFF

Network Parameters: PanID=1DEA, Channel=19

Controller EUI=0021ED00000905FC, nodeID=0000
Node EUI      =CCCCCCFFFEB99522, nodeID=B65A


Node type = FFD, Manufacturer Id = 1168
Endpoints: ['01', '02', 'F2']

Simple Descriptor, Endpoint=01:
ProfileID  = 0104
DeviceID   = 0403v01. IAS Warning Device
InCluster  = ['0000', '0001', '0003', '0500', '0502', '0B05']
OutCluster = ['0019']

Simple Descriptor, Endpoint=02:
ProfileID  = 0104
DeviceID   = 0101v01. Dimmable Light
InCluster  = ['0000', '0003', '0004', '0005', '0006', '0008']
OutCluster = []

Simple Descriptor, Endpoint=F2:
ProfileID  = A1E0
DeviceID   = 0061v01. ZGP Proxy
InCluster  = []
OutCluster = ['0021']
Endpoints: ['01', '02', 'F2']

Endpoint=01, Cluster=0000,Basic Cluster,server
0000,20,zclVersion                              ,03                  ,ZCL_NOT_FOUND
0001,20,applicationVersion                      ,01                  ,ZCL_NOT_FOUND
0002,20,stackVersion                            ,06                  ,ZCL_NOT_FOUND
0003,20,hardwareVersion                         ,02                  ,ZCL_NOT_FOUND
0004,42,manufacturerName                        ,LDS                 ,ZCL_NOT_FOUND
0005,42,modelIdentifier                         ,SIREN001            ,ZCL_NOT_FOUND
0006,42,dateCode                                ,15102020            ,ZCL_NOT_FOUND
0007,30,powerSource                             ,84                  ,ZCL_NOT_FOUND
0008,30,applicationProfileVersion               ,FF                  ,ZCL_NOT_FOUND
0009,30,genericDeviceType                       ,FF                  ,ZCL_NOT_FOUND
000A,41,productCode                             ,010700010           ,ZCL_NOT_FOUND
000B,42,productUrl                              ,www.hivehome.com    ,ZCL_NOT_FOUND
4000,42,swBuildId                               ,1.46                ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND
4020,20,***MSP: sirenAntiTamperSwitch           ,00                  ,ZCL_NOT_FOUND
4021,20,***MSP: powerSupplyType                 ,01                  ,ZCL_NOT_FOUND
4022,20,***MSP: rfJammingState                  ,00                  ,ZCL_NOT_FOUND
4023,20,***MSP: batteryCharging                 ,00                  ,ZCL_NOT_FOUND

Endpoint=01, Cluster=0001,Power Configuration Cluster,server
0020,20,batteryVoltage                          ,27                  ,ZCL_NOT_FOUND
0021,20,batteryPercentageRemaining              ,A0                  ,0001,FFFE,02
0031,30,batterySize                             ,02                  ,ZCL_NOT_FOUND
0033,20,batteryQuantity                         ,01                  ,ZCL_NOT_FOUND
0035,18,batteryAlarmMask                        ,00                  ,ZCL_NOT_FOUND
0036,20,batteryVoltageMinThreshold              ,21                  ,ZCL_NOT_FOUND
0037,20,batteryVoltageThreshold1                ,23                  ,ZCL_NOT_FOUND
0038,20,batteryVoltageThreshold2                ,25                  ,ZCL_NOT_FOUND
0039,20,batteryVoltageThreshold3                ,27                  ,ZCL_NOT_FOUND
003E,1B,batteryAlarmState                       ,00000000            ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=01, Cluster=0003,Identify Cluster,server
0000,21,identifyTime                            ,0000                ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=01, Cluster=0500,IAS Zone Cluster,server
0000,30,zoneState                               ,01                  ,ZCL_NOT_FOUND
0001,31,zoneType                                ,0225                ,ZCL_NOT_FOUND
0002,19,zoneStatus                              ,0000                ,ZCL_NOT_FOUND
0010,F0,iasCieAddress                           ,0021ED00000905FC    ,ZCL_NOT_FOUND
0011,20,zoneId                                  ,05                  ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=01, Cluster=0502,IAS WD Cluster,server
0000,21,MaxDuration                             ,04B0                ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=01, Cluster=0B05,Diagnostics Cluster,server
011C,20,lastMessageLQI                          ,D0                  ,ZCL_NOT_FOUND
011D,28,lastMessageRSSI                         ,D0                  ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=01, Cluster=0019,OTA Cluster,client
0000,F0,upgradeServerId                         ,0021ED00000905FC    ,ZCL_UNSUPPORTED_ATTRIBUTE
0001,23,file Offset                             ,FFFFFFFF            ,ZCL_UNSUPPORTED_ATTRIBUTE
0002,23,current File Version                    ,01466550            ,ZCL_UNSUPPORTED_ATTRIBUTE
0006,30,image Upgrade Status                    ,00                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0007,21,manufacturerId                          ,1168                ,ZCL_UNSUPPORTED_ATTRIBUTE
0008,21,imageTypeId                             ,FFFF                ,ZCL_UNSUPPORTED_ATTRIBUTE
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_UNSUPPORTED_ATTRIBUTE

Endpoint=02, Cluster=0000,Basic Cluster,server
0000,20,zclVersion                              ,03                  ,ZCL_NOT_FOUND
0001,20,applicationVersion                      ,01                  ,ZCL_NOT_FOUND
0002,20,stackVersion                            ,06                  ,ZCL_NOT_FOUND
0003,20,hardwareVersion                         ,02                  ,ZCL_NOT_FOUND
0004,42,manufacturerName                        ,LDS                 ,ZCL_NOT_FOUND
0005,42,modelIdentifier                         ,SIREN001            ,ZCL_NOT_FOUND
0006,42,dateCode                                ,15102020            ,ZCL_NOT_FOUND
0007,30,powerSource                             ,84                  ,ZCL_NOT_FOUND
0008,30,applicationProfileVersion               ,FF                  ,ZCL_NOT_FOUND
0009,30,genericDeviceType                       ,FF                  ,ZCL_NOT_FOUND
000A,41,productCode                             ,010700010           ,ZCL_NOT_FOUND
000B,42,productUrl                              ,www.hivehome.com    ,ZCL_NOT_FOUND
4000,42,swBuildId                               ,1.46                ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND
4020,20,***MSP: sirenAntiTamperSwitch           ,00                  ,ZCL_NOT_FOUND
4021,20,***MSP: powerSupplyType                 ,00                  ,ZCL_NOT_FOUND
4022,20,***MSP: rfJammingState                  ,00                  ,ZCL_NOT_FOUND
4023,20,***MSP: batteryCharging                 ,00                  ,ZCL_NOT_FOUND

Endpoint=02, Cluster=0003,Identify Cluster,server
0000,21,identifyTime                            ,0000                ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=02, Cluster=0004,Groups Cluster,server
0000,18,nameSupport                             ,00                  ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=02, Cluster=0005,Scenes Cluster,server
0000,20,sceneCount                              ,00                  ,ZCL_NOT_FOUND
0001,20,currentScene                            ,00                  ,ZCL_NOT_FOUND
0002,21,currentGroup                            ,0000                ,ZCL_NOT_FOUND
0003,10,sceneValid                              ,00                  ,ZCL_NOT_FOUND
0004,18,nameSupport                             ,00                  ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=02, Cluster=0006,On/Off Cluster,server
0000,10,onOff                                   ,00                  ,0001,FFFE,
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=02, Cluster=0008,Level Control Cluster,server
0000,20,currentLevel                            ,FE                  ,000A,003C,01
0001,21,remainingTime                           ,0000                ,ZCL_NOT_FOUND
FFFD,21,Ember: Cluster Version                  ,0001                ,ZCL_NOT_FOUND

Endpoint=F2, Cluster=0021,Green Power Cluster,client

Binding Table:
BTable:B65A,00
Length:01
No. |     SrcAddr      | SrcEP | ClusterID |      DstAddr     | DstEP
0. | CCCCCCFFFEB99522 |  01   |   0500    | 0021ED00000905FC |  02

Serial write thread exit
Serial read thread exit

All Done