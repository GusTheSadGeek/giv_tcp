# set base image (host OS)
FROM python:rc-alpine

RUN apk --no-cache add mosquitto
RUN apk add curl
RUN apk add --update npm
RUN npm install -g serve
RUN apk add git
RUN apk add tzdata
RUN apk add musl-utils
RUN apk add xsel
RUN apk add redis

# set the working directory in the container
WORKDIR /app

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN pip install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY GivTCP/ ./GivTCP
COPY GivEnergy-Smart-Home-Display-givtcp/ ./GivEnergy-Smart-Home-Display-givtcp
COPY givenergy_modbus/ /usr/local/lib/python3.10/site-packages/givenergy_modbus

COPY startup.py startup.py
COPY startup_2.py startup_2.py
COPY redis.conf redis.conf

ENV NUMINVERTORS=1
ENV INVERTOR_IP_1=""
ENV NUMBATTERIES_1=1
ENV MQTT_OUTPUT=True
ENV MQTT_ADDRESS="127.0.0.1"
ENV MQTT_USERNAME=""
ENV MQTT_PASSWORD=""
ENV MQTT_TOPIC=""
ENV MQTT_PORT=1883
ENV LOG_LEVEL="Info"
ENV PRINT_RAW=True
ENV SELF_RUN=True
ENV SELF_RUN_LOOP_TIMER=5
ENV INFLUX_OUTPUT=False
ENV INFLUX_URL=""
ENV INFLUX_TOKEN=""
ENV INFLUX_BUCKET=""
ENV INFLUX_ORG=""
ENV HA_AUTO_D=True
ENV HADEVICEPREFIX="GivTCP"
ENV PYTHONPATH="/app"
ENV DAYRATE=0.395
ENV NIGHTRATE=0.155
ENV EXPORTRATE=0.04
ENV HOSTIP="192.168.2.10"
ENV DYNAMICTARIFF=False
ENV DAYRATESTART="04:30"
ENV NIGHTRATESTART="00:30"
ENV TZ="Europe/London"
ENV WEB_DASH=False
ENV WEB_DASH_PORT=3000
ENV CACHELOCATION="/config/GivTCP"
ENV DATASMOOTHER="medium"

ENV SMARTTARGET=False
ENV GEAPI=""
ENV SOLCASTAPI=""
ENV SOLCASTSITEID=""
ENV SOLCASTSITEID2=""


EXPOSE 6345 1883 3000 6379 9181

CMD ["python3", "/app/startup.py"]
