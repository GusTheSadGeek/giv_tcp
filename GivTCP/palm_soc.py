#!/usr/bin/env python3
"""PALM - PV Active Load Manager."""

import sys
import time
import json
from datetime import datetime, timedelta
from typing import Tuple
import requests
import palm_settings as stgs
from settings import GiV_Settings
from GivLUT import GivLUT
import write as wr


# This software in any form is covered by the following Open Source BSD license:
#
# Copyright 2022, Steve Lewis
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted
# provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions
# and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other materials provided
# with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY
# WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

###########################################
# This code sets overnight charge point, based on SolCast forecast & actual usage
#
###########################################

# Chamgelog:

# v0.8.3aSoC   28/Jul/22 Branch from palm - SoC only
# v0.8.3bSoC   05/Aug/22 Improved commenting, removed legacy code

PALM_VERSION = "v0.8.3bSoC"

#  Future improvements:
#
# -*- coding: utf-8 -*-
logger = GivLUT.logger



class GivEnergyObj:
    """Class for GivEnergy inverter, used to interface to the inverter, store local data, etc"""

    def __init__(self):
        self.soc: int = 0
        self.base_load = stgs.GE.base_load

    def get_load_hist(self, time_now_mins):
        """Download historical consumption data from GivEnergy and pack array for next SoC calc"""

        day_delta = 0 if (time_now_mins > 1430) else 1  # Use latest full day
        day = datetime.strftime(datetime.now() - timedelta(day_delta), '%Y-%m-%d')
        url = stgs.GE.url + "data-points/" + day
        key = stgs.GE.key
        headers = {
            'Authorization': 'Bearer  ' + key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        params = {
        'page': '1',
        'pageSize': '2000',
        }

        try:
            resp = requests.request('GET', url, headers=headers, params=params)
        except requests.exceptions.RequestException as error:
            logger.error(error)
            return

        if len(resp.content) > 100:  # Basic error check... could be improved over time
            history = json.loads(resp.content.decode('utf-8'))
            index = 0
            counter = 0
            current_energy = prev_energy = 0
            while index < 284:
                try:
                    current_energy = float(history['data'][index]['today']['consumption'])
                except:
                    break
                if counter == 0:
                    self.base_load[counter] = round(current_energy, 1)
                else:
                    self.base_load[counter] = round(current_energy - prev_energy, 1)
                counter += 1
                prev_energy = current_energy
                index += 12
            logger.info("Load Calc Summary: "+ str(current_energy) + " " + str(self.base_load))

    def set_inverter_register(self, register: str, value: str):
        """Set target charge for overnight charging."""

        url = stgs.GE.url + "settings/" + register + "/write"
        key = stgs.GE.key
        headers = {
            'Authorization': 'Bearer  ' + key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        payload = {
            'value': value
        }

        resp = ""
        if not DEBUG_MODE:
            try:
                resp = requests.request('POST', url, headers=headers, json=payload)
            except requests.exceptions.RequestException as error:
                logger.error(error)
                return

        if register == "64":
            reg_str = "(AC Charge 1 Start Time)"
        elif register == "71":
            reg_str = "(Battery Reserve)"
        elif register == "77":
            reg_str = "(AC Charge Upper % Limit)"
        else:
            reg_str = "(Unknown)"

        logger.info("Setting "+ str(reg_str)+ " to "+ str(value)+ "%")

    def set_soc(self, tgt_soc):
        """ Sets start time and target SoC for overnight charge."""
#        self.set_inverter_register("77", tgt_soc)
        result={}
        logger.debug("Setting Charge Target to: "+ str(tgt_soc)+ "%")
        payload={}
        payload['chargeToPercent']= tgt_soc
        result=wr.setChargeTarget(payload)
        logger.debug(result)
        
    def restore_params(self):
        """Restore inverter parameters after overnight charge"""

        self.set_inverter_register("77", 100)
        self.set_inverter_register("64", stgs.GE.start_time)
        self.set_inverter_register("71", stgs.GE.batt_reserve)


    def compute_tgt_soc(self, gen_fcast, wgt_10: int, wgt_50: int, wgt_90: int, month: str, commit: bool):
        """Compute tomorrow's overnight SoC target"""

        batt_max_charge: float = stgs.GE.batt_max_charge

        tgt_soc = 100
        if gen_fcast.pv_est50_day[0] > 0:
            if month in stgs.GE.winter:
                logger.info("Info; winter month, SoC set to 100%")
            else:

                #  Step through forecast generation and consumption for coming day to identify
                #  lowest minimum before overcharge and maximum overcharge. If there is overcharge
                #  and the first min is above zero, reduce overnight charge for min export.

                batt_charge: float = [0] * 24
                batt_charge[0] = batt_max_charge
                max_charge = 0
                min_charge = batt_max_charge

                logger.info("")
                logger.info("{:>10} {:>10} {:>10}  {:>10} {:>10}".format(
                    "Hour", "Charge", "Cons", "Gen", "SoC"))

                index = 0
                while index < 24:
                    if index > 4:  # Battery is in Eco mode
                        total_load = ge.base_load[index]
                    else:  # Battery is in Charge mode
                        total_load = 0
                    est_gen = (gen_fcast.pv_est10_hrly[index] * wgt_10 +
                        gen_fcast.pv_est50_hrly[index] * wgt_50 +
                        gen_fcast.pv_est90_hrly[index] * wgt_90) / (wgt_10 + wgt_50 + wgt_90)
                    if index > 0:
                        batt_charge[index] = (batt_charge[index - 1] +
                            max(-1 * stgs.GE.charge_rate,
                                min(stgs.GE.charge_rate, est_gen - total_load)))
                        # Capture min charge on lowest down-slope before charge exceeds 100%
                        if (batt_charge[index] <= batt_charge[index - 1] and
                            max_charge < batt_max_charge):
                            min_charge = min(min_charge, batt_charge[index])
                        elif index > 4:  # Charging after overnight boost
                            max_charge = max(max_charge, batt_charge[index])

                    logger.info("{:>10} {:>10} {:>10}  {:>10} {:>10}".format(
                        index, round(batt_charge[index], 2), round(total_load, 2),
                        round(est_gen, 2), int(100 * batt_charge[index] / batt_max_charge)))

                    index += 1

                max_charge_pcnt = int(100 * max_charge / batt_max_charge)
                min_charge_pcnt = int(100 * min_charge / batt_max_charge)

                #  Reduce nightly charge to capture max export
                if month in stgs.GE.shoulder:
                    tgt_soc = max(stgs.GE.max_soc_target, 100 - min_charge_pcnt, 200 - max_charge_pcnt)
                else:
                    tgt_soc = max(stgs.GE.min_soc_target, 100 - min_charge_pcnt, 200 - max_charge_pcnt)
                tgt_soc = int(min(max(tgt_soc, 0), 100))  # Limit range

                logger.info("")
                logger.info("{:<25} {:>10} {:>10} {:>10} {:>10} {:>10}".format("SoC Calc Summary;",
                    "Max Charge", "Min Charge", "Max %", "Min %", "Target SoC"))
                logger.info("{:<25} {:>10} {:>10} {:>10} {:>10} {:>10}".format("SoC Calc Summary;",
                    round(max_charge, 2), round(min_charge, 2),
                    max_charge_pcnt, min_charge_pcnt, tgt_soc))
                logger.info("{:<25} {:>10} {:>10} {:>10} {:>10} {:>10}".format("SoC (Adjusted);",
                    round(max_charge, 2), round(min_charge, 2),
                    max_charge_pcnt - 100 + tgt_soc, min_charge_pcnt - 100 + tgt_soc, "\n"))

        else:
            logger.error("Incomplete Solcast data, setting target SoC to 100%")

        logger.info("SoC Summary; "+ LONG_TIME_NOW_VAR + "; Tom Fcast Gen (kWh); "+
            str(gen_fcast.pv_est10_day[0])+ ";"+ str(gen_fcast.pv_est50_day[0])+ ";"+
            str(gen_fcast.pv_est90_day[0])+ "; SoC Target (%); "+ str(tgt_soc))
        logger.info("")

        if commit:
            self.set_soc(tgt_soc)

# End of GivEnergyObj() class definition

class SolcastObj:
    """Stores and manipulates daily Solcast forecast."""

    def __init__(self):
        # Skeleton solcast summary array
        self.pv_est10_day: [int] = [0] * 7
        self.pv_est50_day: [int] = [0] * 7
        self.pv_est90_day: [int] = [0] * 7

        self.pv_est10_hrly: [int] = [0] * 24
        self.pv_est50_hrly: [int] = [0] * 24
        self.pv_est90_hrly: [int] = [0] * 24

    def update(self):
        """Updates forecast generation from Solcast server."""

        def get_solcast(url) -> Tuple[bool, str]:
            """Download latest Solcast forecast."""

            solcast_url = url + stgs.Solcast.cmd + "&api_key=" + stgs.Solcast.key
            try:
                req = requests.get(solcast_url, timeout=5)
                req.raise_for_status()
            except requests.exceptions.RequestException as error:
                logger.error(error)
                return False, ""

            if len(req.content) < 50:
                logger.error("Warning: Solcast data missing/short")
                logger.error(req.content)
                return False, ""

            solcast_data = json.loads(req.content.decode('utf-8'))
            return True, solcast_data
        #  End of get_solcast()

        # Download latest data for each array, abort if unsuccessful

        result, solcast_data_1 = get_solcast(stgs.Solcast.url_se)
        if not result:
            logger.error("Error; Problem reading Solcast data, using previous values (if any)")
            return

        if stgs.Solcast.url_sw != "":  # Two arrays are specified
            result, solcast_data_2 = get_solcast(stgs.Solcast.url_sw)
            if not result:
                logger.error("Error; Problem reading Solcast data, using previous values (if any)")
                return

        logger.info("Successful Solcast download.")

        # Combine forecast for PV arrays & align data with day boundaries
        pv_est10 = [0] * 10080
        pv_est50 = [0] * 10080
        pv_est90 = [0] * 10080

        if stgs.Solcast.url_sw != "":  # Two arrays are specified
            forecast_lines = min(len(solcast_data_1['forecasts']), len(solcast_data_2['forecasts']))
        else:
            forecast_lines = len(solcast_data_1['forecasts'])

        interval = int(solcast_data_1['forecasts'][0]['period'][2:4])
        solcast_offset = (60 * int(solcast_data_1['forecasts'][0]['period_end'][11:13]) +
            int(solcast_data_1['forecasts'][0]['period_end'][14:16]) - interval - 60)

        index = solcast_offset
        cntr = 0
        while index < forecast_lines * interval:
            if stgs.Solcast.url_sw != "":  # Two arrays are specified
                pv_est10[index] = (int(solcast_data_1['forecasts'][cntr]['pv_estimate10'] * 1000) +
                    int(solcast_data_2['forecasts'][cntr]['pv_estimate10'] * 1000))
                pv_est50[index] = (int(solcast_data_1['forecasts'][cntr]['pv_estimate'] * 1000) +
                    int(solcast_data_2['forecasts'][cntr]['pv_estimate'] * 1000))
                pv_est90[index] = (int(solcast_data_1['forecasts'][cntr]['pv_estimate90'] * 1000) +
                    int(solcast_data_2['forecasts'][cntr]['pv_estimate90'] * 1000))
            else:
                pv_est10[index] = int(solcast_data_1['forecasts'][cntr]['pv_estimate10'] * 1000)
                pv_est50[index] = int(solcast_data_1['forecasts'][cntr]['pv_estimate'] * 1000)
                pv_est90[index] = int(solcast_data_1['forecasts'][cntr]['pv_estimate90'] * 1000)

            if index > 1 and index % interval == 0:
                cntr += 1
            index += 1

        index = 0
        if solcast_offset > 720:  # Forget obout current day
            offset = 1440 - 90
        else:
            offset = 0

        while index < 7:  # Summarise daily forecasts
            start = index * 1440 + offset + 1
            end = start + 1439
            self.pv_est10_day[index] = round(sum(pv_est10[start:end]) / 60000, 3)
            self.pv_est50_day[index] = round(sum(pv_est50[start:end]) / 60000, 3)
            self.pv_est90_day[index] = round(sum(pv_est90[start:end]) / 60000, 3)
            index += 1

        index = 0
        while index < 24:  # Calculate hourly generation
            start = index * 60 + offset + 1
            end = start + 59
            self.pv_est10_hrly[index] = round(sum(pv_est10[start:end])/60000, 3)
            self.pv_est50_hrly[index] = round(sum(pv_est50[start:end])/60000, 3)
            self.pv_est90_hrly[index] = round(sum(pv_est90[start:end])/60000, 3)
            index += 1

        timestamp = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        logger.info("PV Estimate 10% (hrly, 7 days) / kWh"+ ";"+ timestamp+ ";"+
            str(self.pv_est10_hrly[0:23])+ str(self.pv_est10_day[0:6]))
        logger.info("PV Estimate 50% (hrly, 7 days) / kWh"+ ";"+ timestamp+ ";"+
            str(self.pv_est50_hrly[0:23])+ str(self.pv_est50_day[0:6]))
        logger.info("PV Estimate 90% (hrly, 7 days) / kWh"+ ";"+ timestamp+ ";"+
            str(self.pv_est90_hrly[0:23])+ str(self.pv_est90_day[0:6]))

# End of SolcastObj() class definition

def time_to_mins(time_in_hrs: str) -> int:
    """Convert times from HH:MM format to mins since midnight."""

    time_in_mins = 60 * int(time_in_hrs[0:2]) + int(time_in_hrs[3:5])
    return time_in_mins

#  End of time_to_mins()

def time_to_hrs(time_in: int) -> str:
    """Convert times from mins since midnight format to HH:MM."""

    hours = int(time_in // 60)
    mins = int(time_in - hours * 60)
    time_in_hrs = '{:02d}{}{:02d}'.format(hours, ":", mins)
    return time_in_hrs

#  End of time_to_hrs()

if __name__ == '__main__':

    # Current time definitions
    LONG_TIME_NOW_VAR: str = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
    TIME_NOW_VAR: str = LONG_TIME_NOW_VAR[11:]
    TIME_NOW_MINS_VAR: int = time_to_mins(TIME_NOW_VAR)
    MONTH_VAR = LONG_TIME_NOW_VAR[3:5]

    logger.critical("PALM... PV Automated Load Manager Version: "+ PALM_VERSION)

    # Parse any command-line arguments
    TEST_MODE: bool = False
    DEBUG_MODE: bool = False
    if len(sys.argv) > 1:
        if str(sys.argv[1]) in ["-t", "--test"]:
            TEST_MODE = True
            DEBUG_MODE = True
            logger.critical("Running in test mode")
        elif str(sys.argv[1]) in ["-d", "--debug"]:
            DEBUG_MODE = True
            logger.critical("Running in debug mode")

    # GivEnergy power object initialisation
    ge: GivEnergyObj = GivEnergyObj()
    ge.get_load_hist(TIME_NOW_MINS_VAR)

    # Solcast PV prediction object initialisation
    solcast: SolcastObj = SolcastObj()
    solcast.update()

    # Compute & set SoC target
    logger.debug("10% forecast...")
    ge.compute_tgt_soc(solcast, 1, 0, 0, MONTH_VAR, False)
    logger.debug("50% forecast...")
    ge.compute_tgt_soc(solcast, 0, 1, 0, MONTH_VAR, False)
    logger.debug("90% forecast...")
    ge.compute_tgt_soc(solcast, 0, 0, 1, MONTH_VAR, False)
    
    # Write final SoC target to GivEnergy register
    # Change weighting in command according to desired risk/reward profile
    logger.debug("1:2:0 weighted forecast...")
    ge.compute_tgt_soc(solcast, 1, 2, 0, MONTH_VAR, True)

# End