# version 2022.01.31
from influxdb_client import InfluxDBClient, WriteApi, WriteOptions
import logging
from logging.handlers import TimedRotatingFileHandler
from settings import GiV_Settings
import datetime
import os

logger = logging.getLogger("GivTCP_Influx_"+str(GiV_Settings.givtcp_instance))
logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
if GiV_Settings.Debug_File_Location!="":
    fh = TimedRotatingFileHandler(GiV_Settings.Debug_File_Location, when='D', interval=1, backupCount=7)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
print("=xx==========================" + str(GiV_Settings.Log_Level.lower()) +" ========================= ")
if GiV_Settings.Log_Level.lower()=="debug":
    logger.setLevel(logging.DEBUG)
elif GiV_Settings.Log_Level.lower()=="info":
    logger.setLevel(logging.INFO)
elif GiV_Settings.Log_Level.lower()=="critical":
    logger.setLevel(logging.CRITICAL)
elif GiV_Settings.Log_Level.lower()=="warning":
    logger.setLevel(logging.WARNING)
else:
    logger.setLevel(logging.ERROR)
if os.getenv("LOG_LEVEL").lower() == "debug":
    lvl = logging.DEBUG
elif os.getenv("LOG_LEVEL").lower() == "info":
    lvl = logging.INFO
elif os.getenv("LOG_LEVEL").lower() == "critical":
    lvl = logging.CRITICAL
elif os.getenv("LOG_LEVEL").lower() == "warning":
    lvl = logging.WARNING
else:
    lvl = logging.ERROR

logging.getLogger().setLevel(lvl)
lastInfluxBatteryUpdate = datetime.datetime.now()

class GivInflux():

    def line_protocol(SN,readings):
        return '{},tagKey={} {}'.format(SN,'GivReal', readings) 

    def line_protocol_battery(SN,tag, readings):
        return '{},tagKey={} {}'.format(SN,tag, readings)

    def make_influx_string(datastr):
        new_str=datastr.replace(" ","_")
        new_str=new_str.lower()
        return new_str

    def publish(SN,data):
        output_str=""
        power_output = data['Power']['Power']
        for key in power_output:
            logging.debug("Creating Power string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+str(power_output[key])+','
        flow_output = data['Power']['Flows']
        for key in flow_output:
            logging.debug("Creating Power Flow string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+str(flow_output[key])+','
        energy_today = data['Energy']['Today']
        for key in energy_today:
            logging.debug("Creating Energy/Today string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+str(energy_today[key])+','

        energy_total = data['Energy']['Total']
        for key in energy_total:
            logging.debug("Creating Energy/Total string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+str(energy_total[key])+','

        logging.debug("Data sending to Influx is: "+ output_str[:-1])
        data1=GivInflux.line_protocol(SN,output_str[:-1])
        #logging.info("Data sending to Influx is: "+ data1)

        _db_client = InfluxDBClient(url=GiV_Settings.influxURL, token=GiV_Settings.influxToken, org=GiV_Settings.influxOrg, debug=False)
        _write_api = _db_client.write_api(write_options=WriteOptions(batch_size=1))
        _write_api.write(bucket=GiV_Settings.influxBucket, record=data1)
        logging.info("Written to InfluxDB")

        _write_api.close()
        _db_client.close()
        #if morethan 5 mins since last update...
        global lastInfluxBatteryUpdate
        since = datetime.datetime.now() - lastInfluxBatteryUpdate
        if since > datetime.timedelta(seconds=60):
            GivInflux.publish_batts(SN, data)
            lastInfluxBatteryUpdate = datetime.datetime.now()

    def publish_batts(SN,data):
        logging.info("logging battery")
        _db_client = InfluxDBClient(url=GiV_Settings.influxURL, token=GiV_Settings.influxToken,
                                    org=GiV_Settings.influxOrg, debug=False)

        for battery_sn in data['Battery_Details']:
            output_str = ""
            battery = data['Battery_Details'][battery_sn]
            for key in battery:
                if str(key).lower() == "battery_usb_present":
                    continue
                if str(key).lower() == "battery_serial_number":
                    continue
                #logging.info(str(key))
                output_str=output_str+str(GivInflux.make_influx_string(key))+'='+str(battery[key])+','

            logging.debug("Data battery sending to Influx is: "+ output_str[:-1])
            data1=GivInflux.line_protocol_battery(SN, battery_sn ,output_str[:-1])
            #logging.info("Data sending to Influx is: "+ data1)

            _write_api = _db_client.write_api(write_options=WriteOptions(batch_size=1))
            _write_api.write(bucket=GiV_Settings.influxBucket, record=data1)
            logging.info("Written to InfluxDB")

        _write_api.close()
        _db_client.close()
