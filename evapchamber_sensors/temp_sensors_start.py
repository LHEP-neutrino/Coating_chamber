#!/usr/bin/python
# -*- coding: utf-8 -*-
# Evaporation chamber temperature logger (Python 2.7)
# - Reads ONLY sensor 0 for now (others left commented for future use)
# - Writes to local rolling files and pushes to InfluxDB v2 via HTTP (requests)
# - Safe Ctrl-C handling; robust to file/Influx transient errors

import time, math, os, signal, shutil, sys
import subprocess
import requests
import RPi.GPIO as GPIO

import max31865  # your local driver (prints Sensor/Temp lines)

# ---------------- Ctrl-C helper ----------------
class DelayedKeyboardInterrupt(object):
    def __enter__(self):
        self.signal_received = False
        self.old_handler = signal.signal(signal.SIGINT, self.handler)
    def handler(self, sig, frame):
        self.signal_received = (sig, frame)
    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, self.old_handler)
        if self.signal_received:
            self.old_handler(*self.signal_received)

# ---------------- InfluxDB v2 config ----------------
BUCKET = "ArCLight_QA_QC"
ORG = "lhep"
TOKEN = os.getenv("INFLUXDB_TOKEN")  # set in ~/.bashrc
BASE_URL = "http://argoncube02.aec.unibe.ch:8086"
INFLUX_WRITE_URL = "{}/api/v2/write?org={}&bucket={}&precision=s".format(BASE_URL, ORG, BUCKET)

def post_influx(measurement, tags_dict, fields_dict, ts=None):
    """
    Minimal line-protocol writer using HTTP (no client lib, Python 2.7 friendly).
    Example line:
      temperature,sens=0 value=23.67 1739110800
    """
    tags = ",".join(["{}={}".format(k, v) for k, v in (tags_dict or {}).items()])
    fields = ",".join(["{}={}".format(k, v) for k, v in (fields_dict or {}).items()])
    timestamp = ts if ts is not None else int(time.time())
    line = "{}{} {} {}".format(measurement, ("," + tags) if tags else "", fields, timestamp)
    try:
        requests.post(INFLUX_WRITE_URL,
                      headers={"Authorization": "Token {}".format(TOKEN)},
                      data=line)
    except requests.RequestException:
        # Keep running if Influx/network is unavailable
        pass

# ---------------- Logger config ----------------
datalength = int(3600 * 1)   # seconds per file (1 hour)
outdir = './data/'
sleeptime = 2                # seconds between samples

if __name__ == "__main__":
    # --- GPIO pin mapping ---
    cs0Pin = 21
    cs1Pin = 20
    cs2Pin = 16
    cs3Pin = 12
    cs4Pin = 7
    cs5Pin = 8
    cs6Pin = 25
    cs7Pin = 24
    cs8Pin = 23
    cs9Pin = 18

    misoPin = 9
    mosiPin = 10
    clkPin  = 11

    # Per-sensor offset corrections (as in your original)
    offset_corr = [0, 0, 0, 0, 0, 0, -0.2, +0.2, -0.5, +0.4]

    # --- ENABLED: only sensor 0 ---
    sens0 = max31865.max31865(offset_corr, cs0Pin, misoPin, mosiPin, clkPin, 0)

    # --- DISABLED for now (uncomment to enable later) ---
    # sens1 = max31865.max31865(offset_corr, cs1Pin, misoPin, mosiPin, clkPin, 1)
    # sens2 = max31865.max31865(offset_corr, cs2Pin, misoPin, mosiPin, clkPin, 2)
    # sens3 = max31865.max31865(offset_corr, cs3Pin, misoPin, mosiPin, clkPin, 3)
    # sens4 = max31865.max31865(offset_corr, cs4Pin, misoPin, mosiPin, clkPin, 4)
    # sens5 = max31865.max31865(offset_corr, cs5Pin, misoPin, mosiPin, clkPin, 5)
    # sens6 = max31865.max31865(offset_corr, cs6Pin, misoPin, mosiPin, clkPin, 6)
    # sens7 = max31865.max31865(offset_corr, cs7Pin, misoPin, mosiPin, clkPin, 7)
    # sens8 = max31865.max31865(offset_corr, cs8Pin, misoPin, mosiPin, clkPin, 8)
    # sens9 = max31865.max31865(offset_corr, cs9Pin, misoPin, mosiPin, clkPin, 9)

    # --- ensure output dir exists ---
    if outdir[-1] != '/':
        outdir += '/'
    if not os.path.exists(outdir):
        os.system('mkdir -p ' + outdir)

    while True:
        lastEpoch = int(time.time())
        unixtime = lastEpoch

        # temp staging dir
        tmp_dir = '/tmp/scdata/temperatures'
        if not os.path.exists(tmp_dir):
            os.system('mkdir -p ' + tmp_dir)

        tmp_path = os.path.join(tmp_dir, str(lastEpoch) + '.txt')

        try:
            outfile = open(tmp_path, 'w')

            try:
                with outfile:
                    while unixtime < (lastEpoch + datalength):
                        print "\n"
                        unixtime = int(time.time())

                        # ---- SAMPLE: only sensor 0 ----
                        temp0 = sens0.readTemp()

                        # ---- LOCAL FILE LOG ----
                        with DelayedKeyboardInterrupt():
                            # file format: <timestamp>\t<temp0>
                            outfile.write(str(unixtime) + '\t' + str(temp0) + '\n')

                        # ---- INFLUX PUSH ----
                        post_influx("temperature", {"sens": "0"}, {"value": temp0}, ts=unixtime)

                        time.sleep(sleeptime)

                # move finished file to final output dir (no stray space!)
                shutil.move(tmp_path, outdir)

            except KeyboardInterrupt:
                print('\n\nTermination of the program from user...')
                if outfile and (not outfile.closed):
                    outfile.close()
                if os.path.exists(tmp_path):
                    print('Transfer the file to the output directory')
                    shutil.move(tmp_path, outdir)
                GPIO.cleanup()
                print('done\n')
                sys.exit(0)

        except IOError as err:
            # If we cannot open the output file, still measure & push to Influx
            print('Error: Could not open file ' + tmp_path + '\n-> Error({0}): {1}'.format(err.errno, err.strerror))
            print('The data will be read without saving it to a file')

            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            try:
                while True:
                    print('\n')
                    temp0 = sens0.readTemp()
                    post_influx("temperature", {"sens": "0"}, {"value": temp0}, ts=int(time.time()))
                    time.sleep(sleeptime)
            except KeyboardInterrupt:
                print('\n\nTermination of the program from user...')
                GPIO.cleanup()
                print('done\n')
                sys.exit(0)

    GPIO.cleanup()

