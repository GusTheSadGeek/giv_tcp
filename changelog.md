
# Change Log
All notable changes to this project will be documented in this file.
 
The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [2.1.7] - 2023-03-10
BUG FIXES:
- Updated max mppt pv voltage to match datasheet (550v)

## [2.1.3] - 2023-03-04
BUG FIXES:
- modified givenergy-modbus library to calulate inverter type from registers, not from serial number
- Fixed day/Night rate stability in dynamic mode

## [2.1.3] - 2023-02-12

BUG FIXES:
- Fixed error on garbage invertor output
- Fixed Force Charge/Export power rate setting from 100(%) to maxInvertorRate

NEW FEATURES:
- Per Invertor MQTT Topic now available
- Overlapping ForceCharge\Export now handled gracefully. You can extend a current Force action byt recalling it with a new duration and it will set a new Force end time

## [2.1.2] - 2023-02-09

BREAKING CHANGES:
- Charge and Discharge rates now use absolute power values (2600W) not percentage (100%) to align with Cloud portal and to give correct operation
- Prevented the REST readData call (pubFromPickle) from triggering another read 
 
BUG FIXES:
- Worked on race conditions by using critical sections to replace file locks
- Fix select entities error when setting to a non-float value

UPDATES:
- Changed logging levels so that Info now just shows which operations are called and everything else is Debug
- Force Charge, Force Export and Temp Pause controls now allow you to Cancel, reverting to preious settings immediately
- Updated Battery Reserve and Cut-off entities to correctly reflect invertor behaviour
- Updated Redis scheduling for control lockout
 
NEW FEATURES:
- Added "None" as a smoothing option
- Added invertor firmware to output
- Allow dynamic Day/Night energy slots as well as fixed time (Go vs Intelligent) New "select" entity created to allow external automations to change rate (DYNAMICTARIFF ENV can be set to true to ignore day/night ENV and change rates based on the value of the Select entity)
- Ability to accept dual array installations for Solcast Smart Target (new ENV) 


## [2.0.1] - 2022-09-18
 
Update to GivLUT to allow battery max power to go up to 4000w to account for Gen2 invertors

## [2.0.0rc2] - 2022-09-17
 
Major update including various stability fixes and new features
 
### Added
- Force Export boost function (and restore)
- Force Charge boost function (and restore)
- Temporary charge and discharge pause (and restore)
- Change timeslot start and end
- All new control functions are avalable via:
  - Select devices (Home assistant)
  - MQTT Topic
  - REST

- Smart target charge using Solcast forecast and load energy stats. Thanks to [Stephen Lewis](https://github.com/salewis38/palm)
  - Only avaiable in docker container or Home Assistant Addon

- User defined port for web dashboard. Thanks to [Dan Gallo](https://github.com/DanielGallo/GivEnergy-Smart-Home-Display/tree/givtcp)
  - Only avaiable in docker container or Home Assistant Addon

- Data smoothing across energy and battery data (not power)
- log to file by default
- Cache data stored in user defined folder. Useful to delete in the event of problems 

#### New ENV
- CACHELOCATION="/config/GivTCP" - if using Home assistant addon, make sure this starts with /config
- DATASMOOTHER="High" - High, medium or low. Level of aggression on smoothing large jumps in data
- SMARTTARGET=True - If True, then the three below ENV must be set. This will update your Target SOC 20mins before it is due to start charging
- GEAPI="" - API key from your GE account
- SOLCASTAPI="" - Solcast API key 
- SOLCASTSITEID="" - Solcast site ID
- DEBUG_FILE_LOCATION - has been removed

### Changed
- Re-structred the lookup tables into single class
- Data structure for all data points using new class type
- Logging to file now uses a rotating file handler and will keep 7 days of logs
- Underlying [givenergy-modbus](https://github.com/dewet22/givenergy-modbus) errors supressed in logging
- Mode control now automatically updates (dis)charge schedule as appropriate
### Fixed
- Obey Print Raw ENV
- Midnight data sticking for Energy Today stats
- many more...
