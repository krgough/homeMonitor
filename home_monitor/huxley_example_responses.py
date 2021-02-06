'''
Created on 14 Sep 2018

@author: Keith.Gough
'''

# https://huxley.apphb.com/delays/wat/To/win/50/None?AccessToken=5de1b845-b7c1-450f-97e4-759fd279588a&expand=True

DELAYS_EXAMPLE = """
{
  "generatedAt": "2018-09-14T05:47:24.1762002+00:00",
  "locationName": "London Waterloo",
  "crs": "WAT",
  "filterLocationName": "Winchester",
  "filtercrs": "WIN",
  "delays": true,
  "totalTrainsDelayed": 1,
  "totalDelayMinutes": 16,
  "totalTrains": 8,
  "delayedTrains": [
    {
      "previousCallingPoints": null,
      "subsequentCallingPoints": [
        {
          "callingPoint": [
            {
              "locationName": "Woking",
              "crs": "WOK",
              "st": "06:56",
              "et": "07:11",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Basingstoke",
              "crs": "BSK",
              "st": "07:16",
              "et": "07:31",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Winchester",
              "crs": "WIN",
              "st": "07:33",
              "et": "07:47",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Eastleigh",
              "crs": "ESL",
              "st": "07:43",
              "et": "07:56",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Southampton Airport Parkway",
              "crs": "SOA",
              "st": "07:48",
              "et": "08:00",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Southampton Central",
              "crs": "SOU",
              "st": "07:57",
              "et": "08:08",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Totton",
              "crs": "TTN",
              "st": "08:04",
              "et": "08:13",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Ashurst New Forest",
              "crs": "ANF",
              "st": "08:09",
              "et": "08:18",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Beaulieu Road",
              "crs": "BEU",
              "st": "08:13",
              "et": "08:22",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Brockenhurst",
              "crs": "BCU",
              "st": "08:19",
              "et": "08:28",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Sway",
              "crs": "SWY",
              "st": "08:25",
              "et": "08:33",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "New Milton",
              "crs": "NWM",
              "st": "08:29",
              "et": "08:38",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Hinton Admiral",
              "crs": "HNA",
              "st": "08:34",
              "et": "08:42",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Christchurch",
              "crs": "CHR",
              "st": "08:38",
              "et": "08:47",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Pokesdown",
              "crs": "POK",
              "st": "08:42",
              "et": "08:51",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Bournemouth",
              "crs": "BMH",
              "st": "08:46",
              "et": "08:55",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Branksome",
              "crs": "BSM",
              "st": "08:53",
              "et": "09:00",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Parkstone (Dorset)",
              "crs": "PKS",
              "st": "08:56",
              "et": "09:03",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Poole",
              "crs": "POO",
              "st": "08:59",
              "et": "09:07",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Hamworthy",
              "crs": "HAM",
              "st": "09:05",
              "et": "09:12",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Wareham",
              "crs": "WRM",
              "st": "09:11",
              "et": "09:18",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Wool",
              "crs": "WOO",
              "st": "09:18",
              "et": "09:24",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Moreton (Dorset)",
              "crs": "MTN",
              "st": "09:25",
              "et": "09:31",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Dorchester South",
              "crs": "DCH",
              "st": "09:32",
              "et": "09:38",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Upwey",
              "crs": "UPW",
              "st": "09:39",
              "et": "09:45",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            },
            {
              "locationName": "Weymouth",
              "crs": "WEY",
              "st": "09:44",
              "et": "09:50",
              "at": null,
              "isCancelled": false,
              "length": 5,
              "detachFront": false,
              "adhocAlerts": null
            }
          ],
          "serviceType": 0,
          "serviceChangeRequired": false,
          "assocIsCancelled": false
        }
      ],
      "origin": [
        {
          "locationName": "London Waterloo",
          "crs": "WAT",
          "via": null,
          "futureChangeTo": null,
          "assocIsCancelled": false
        }
      ],
      "destination": [
        {
          "locationName": "Weymouth",
          "crs": "WEY",
          "via": null,
          "futureChangeTo": null,
          "assocIsCancelled": false
        }
      ],
      "currentOrigins": null,
      "currentDestinations": null,
      "rsid": "SW911100",
      "sta": null,
      "eta": null,
      "std": "06:30",
      "etd": "06:46",
      "platform": "11",
      "operator": "South Western Railway",
      "operatorCode": "SW",
      "isCircularRoute": false,
      "isCancelled": false,
      "filterLocationCancelled": false,
      "serviceType": 0,
      "length": 5,
      "detachFront": false,
      "isReverseFormation": false,
      "cancelReason": "This train has been cancelled because of engineering works not being finished on time",
      "delayReason": "This train has been delayed by engineering works not being finished on time",
      "serviceID": "bGA1Ua1X7SpLZ7IUF2bwnw==",
      "serviceIdPercentEncoded": "bGA1Ua1X7SpLZ7IUF2bwnw%3d%3d",
      "serviceIdGuid": "5135606c-57ad-2aed-4b67-b2141766f09f",
      "serviceIdUrlSafe": "bGA1Ua1X7SpLZ7IUF2bwnw",
      "adhocAlerts": null
    }
  ]
}


https://huxley.apphb.com/delays/wat/To/win/50/None?AccessToken=5de1b845-b7c1-450f-97e4-759fd279588a&expand=False
{
  "generatedAt": "2018-09-14T05:53:43.9850946+00:00",
  "locationName": "London Waterloo",
  "crs": "WAT",
  "filterLocationName": "Winchester",
  "filtercrs": "WIN",
  "delays": true,
  "totalTrainsDelayed": 0,
  "totalDelayMinutes": 0,
  "totalTrains": 7,
  "delayedTrains": []
}

"""