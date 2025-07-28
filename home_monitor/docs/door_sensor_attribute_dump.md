zb_dump -p /dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-port0 -f -i -n 58FD
Serial port opened.../dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-port0
Serial port read handler thread started.
Serial port write handler thread started.
rxQueue is ON
listenerQueue is OFF

Network Parameters: PanID=1DEA, Channel=19

Controller EUI=0021ED00000905FC, nodeID=0000
Node EUI      =00124B00160561DE, nodeID=58FD


Node type = ZED, Manufacturer Id = 1039
Endpoints: ['06']

Simple Descriptor, Endpoint=06:
ProfileID  = 0104
DeviceID   = 0402v00. IAS Zone
InCluster  = ['0000', '0001', '0003', '0020', '0402', '0500']
OutCluster = ['0019']
Poll Control EP = 06

Setting poll control binding..
Reading long poll interval...
Setting long poll to 5.0s 0x00000014, original was 0x000004B0 (unit is 250ms)
Reading short poll interval...
Setting short poll to 0.5s 0x0002, original was 0x0004 (unit is 250ms)
Reading checkin interval...
Setting checkin interval to 30.0s 0x00000078, original was 0x000004B0 (units of 250ms) 

*** Short poll interval, Long poll interval and check-in interval have been modified to allow attribute dump
Original short poll interval = 0004

Original long poll interval  = 000004B0

Original check-in interval   = 000004B0

Attempting to start fast poll...
Waiting for device to checkIn...
Endpoints: ['06']

Endpoint=06, Cluster=0000,Basic Cluster,server
0000,20,zclVersion                              ,01                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0001,20,applicationVersion                      ,05                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0002,20,stackVersion                            ,26                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0003,20,hardwareVersion                         ,00                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0004,42,manufacturerName                        ,HiveHome.com        ,ZCL_UNSUPPORTED_ATTRIBUTE
0005,42,modelIdentifier                         ,DWS003              ,ZCL_UNSUPPORTED_ATTRIBUTE
0006,42,dateCode                                ,20181205            ,ZCL_UNSUPPORTED_ATTRIBUTE
0007,30,powerSource                             ,03                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0008,23,applicationProfileVersion               ,01020100            ,ZCL_UNSUPPORTED_ATTRIBUTE
TYPE ERROR in zigbeeCluster Library !!!!!!!!!!!!!!!
0010,42,locationDescription                     ,                    ,ZCL_UNSUPPORTED_ATTRIBUTE
0011,30,physicalEnvironment                     ,00                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0012,10,deviceEnabled                           ,01                  ,ZCL_UNSUPPORTED_ATTRIBUTE

Endpoint=06, Cluster=0001,Power Configuration Cluster,server
0020,20,batteryVoltage                          ,1E                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0021,20,batteryPercentageRemaining              ,B5                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0030,42,batteryManufacturer                     ,CR123A              ,ZCL_UNSUPPORTED_ATTRIBUTE
0031,30,batterySize                             ,02                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0032,21,batteryAHrRating                        ,009B                ,ZCL_UNSUPPORTED_ATTRIBUTE
0033,20,batteryQuantity                         ,01                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0034,20,batteryRatedVoltage                     ,1E                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0036,20,batteryVoltageMinThreshold              ,19                  ,ZCL_UNSUPPORTED_ATTRIBUTE

Endpoint=06, Cluster=0003,Identify Cluster,server
0000,21,identifyTime                            ,0000                ,ZCL_UNSUPPORTED_ATTRIBUTE
0001,18,commissionState                         ,03                  ,ZCL_UNSUPPORTED_ATTRIBUTE

Endpoint=06, Cluster=0020,Poll Control Cluster,server
0000,23,checkInInterval                         ,00000078            ,ZCL_UNSUPPORTED_ATTRIBUTE
0001,23,longPollInterval                        ,00000014            ,ZCL_UNSUPPORTED_ATTRIBUTE
0002,21,shortPollInterval                       ,0002                ,ZCL_UNSUPPORTED_ATTRIBUTE
0003,21,fastPollTimeout                         ,0006                ,ZCL_UNSUPPORTED_ATTRIBUTE
0004,23,checkInIntervalMin                      ,00000078            ,ZCL_UNSUPPORTED_ATTRIBUTE
0005,23,LongPollIntervalMin                     ,00000014            ,ZCL_UNSUPPORTED_ATTRIBUTE
0006,21,fastPollTimeoutMax                      ,0078                ,ZCL_UNSUPPORTED_ATTRIBUTE

Endpoint=06, Cluster=0402,Temperature Measurement Cluster,server
0000,29,measuredValue                           ,0A5A                ,ZCL_UNSUPPORTED_ATTRIBUTE
0001,29,minMeasuredValue                        ,F63C                ,ZCL_UNSUPPORTED_ATTRIBUTE
0002,29,maxMeasuredValue                        ,2134                ,ZCL_UNSUPPORTED_ATTRIBUTE
0003,21,tolerance                               ,0032                ,ZCL_UNSUPPORTED_ATTRIBUTE

Endpoint=06, Cluster=0500,IAS Zone Cluster,server
0000,30,zoneState                               ,00                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0001,31,zoneType                                ,0015                ,ZCL_UNSUPPORTED_ATTRIBUTE
0002,19,zoneStatus                              ,0021                ,ZCL_UNSUPPORTED_ATTRIBUTE
0010,F0,iasCieAddress                           ,0000000000000000    ,ZCL_UNSUPPORTED_ATTRIBUTE
0011,20,zoneId                                  ,06                  ,ZCL_UNSUPPORTED_ATTRIBUTE

Endpoint=06, Cluster=0019,OTA Cluster,client
0000,F0,upgradeServerId                         ,0021ED00000905FC    ,ZCL_UNSUPPORTED_ATTRIBUTE
0001,23,file Offset                             ,FFFFFFFF            ,ZCL_UNSUPPORTED_ATTRIBUTE
0002,23,current File Version                    ,05042603            ,ZCL_UNSUPPORTED_ATTRIBUTE
0003,21,current ZigBee Stack Version            ,0002                ,ZCL_UNSUPPORTED_ATTRIBUTE
0004,23,downloaded File Version                 ,FFFFFFFF            ,ZCL_UNSUPPORTED_ATTRIBUTE
0005,21,downloaded ZigBee Stack Version         ,FFFF                ,ZCL_UNSUPPORTED_ATTRIBUTE
0006,30,image Upgrade Status                    ,00                  ,ZCL_UNSUPPORTED_ATTRIBUTE
0007,21,manufacturerId                          ,1039                ,ZCL_UNSUPPORTED_ATTRIBUTE
0008,21,imageTypeId                             ,FFFF                ,ZCL_UNSUPPORTED_ATTRIBUTE
0009,21,minimumBlockRequestDelay                ,00FA                ,ZCL_UNSUPPORTED_ATTRIBUTE

Binding Table:
BTable:58FD,00
Length:01
No. |     SrcAddr      | SrcEP | ClusterID |      DstAddr     | DstEP
0. | 00124B00160561DE |  06   |   0020    | 0021ED00000905FC |  01

Attempting reset of original short poll interval, long poll interval and check-in interval
Reset is complete.

Serial write thread exit
Serial read thread exit

All Done
