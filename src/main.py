#!/usr/bin/env python

from loranet import LoraNet
from ota import LoraOTA
from network import LoRa
import utime
from utils import random_range
import uos
import os
import pycom

LORA_FREQUENCY = 868100000
LORA_NODE_DR = 5
LORA_REGION = LoRa.EU868
LORA_DEVICE_CLASS = LoRa.CLASS_C
LORA_ACTIVATION = LoRa.OTAA
VERSION_FILE = '/flash/version.py'

# Get LoRa credentials from non-volatile storage
APP_KEY = pycom.nvs_get('app_key')
DEV_EUI = pycom.nvs_get('dev_eui')
APP_EUI = pycom.nvs_get('app_eui', '0000000000000000')
LORA_CRED = (DEV_EUI, APP_EUI, APP_KEY)

def get_current_version():
   with open(VERSION_FILE, 'r') as fh:
      version = fh.read().rstrip("\r\n\s")
   return version

# Device version changed
DEVICE_VERSION = get_current_version()

print("starting version: " + DEVICE_VERSION)

lora = LoraNet(LORA_FREQUENCY, LORA_NODE_DR, LORA_REGION, LORA_DEVICE_CLASS, LORA_ACTIVATION, LORA_CRED)
lora.connect()

ota = LoraOTA(lora, DEVICE_VERSION)

def main():
   ota.send_device_version_message()
   while True:
      if not ota.update_in_progress:
         temperature = random_range(10, 30) # Generate a random temperature between 10 and 30 degrees Celsius
         humidity = random_range(40, 70) # Generate a random humidity between 40 and 70 percent
         print("Temperature:", temperature, "Humidity:", humidity)
         data ='sensor,' + str(temperature) + ',' + str(humidity)
         lora.send(data)
      utime.sleep(5)

try:
   main()
except Exception as e:
   print("Main loop failed: " + str(e))
   ota.revert()
