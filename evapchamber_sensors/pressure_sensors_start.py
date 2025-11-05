# -*- coding: utf-8 -*-
# TPG362 pressure logging to InfluxDB (Python 2.7)
# - Handles "OR"/"UR" gracefully: OR -> 1000 mbar, UR -> -1 mbar
# - Keeps original device setup and behavior
# - Posts to InfluxDB using requests (no Py3 client dependency)

from class_def import TPG362
import time
import os
import requests

# ---- Configuration ----
offset_p1 = 0.0
offset_p2 = 0.0

bucket = "ArCLight_QA_QC"
org = "lhep"
token = os.getenv("INFLUXDB_TOKEN")  # set in ~/.bashrc: export INFLUXDB_TOKEN=<token>
base_url = "http://argoncube02.aec.unibe.ch:8086"
url = "{}/api/v2/write?org={}&bucket={}&precision=s".format(base_url, org, bucket)

# ---- Helpers ----
def parse_pressure_field(s, offset):
    """
    Convert a string pressure field to a float with offset.
    Handles special range strings ('OR'/'UR', case-insensitive).
      - 'OR' (overrange)  -> 1000.0 mbar
      - 'UR' (underrange) -> -1.0 mbar
    Returns a float.
    Raises ValueError only if truly unparseable (e.g., empty/--- etc.).
    """
    if s is None:
        raise ValueError("empty field")
    ss = s.strip().lower()
    if ss == 'or':   # overrange / upper limit reached
        return 1000.0
    if ss == 'ur':   # underrange / lower limit reached
        return -1.0
    # Some devices may emit '---' or '' briefly; treat as unparseable
    if ss == '---' or ss == '':
        raise ValueError("invalid numeric field: {}".format(s))
    return float(s) + offset

def post_influx(line):
    try:
        # 204 = success; we intentionally ignore the response body
        requests.post(url, headers={"Authorization": "Token {}".format(token)}, data=line)
    except requests.RequestException:
        # Ignore transient network errors; keep the loop alive
        pass

# ---- Gauge setup ----
gauge = TPG362(port='/dev/ttyUSB0')

# Device info
gauge._send_command('AYT')
answer = gauge._get_data()
print("----------------------------------------")
print("Device Type:", answer.split(',')[0])
print("Model No.:  ", answer.split(',')[1])
print("Serial No.: ", answer.split(',')[2])
print("----------------------------------------")
print("Firmware version:", answer.split(',')[3])
print("Hardware version:", answer.split(',')[4])
print("----------------------------------------")
gauge._send_command('RHR')
print("Operating hours:  ", gauge._get_data())
gauge._send_command('TMP')
print("Inner temperature:", gauge._get_data(), "degrees")
print("----------------------------------------")
gauge._send_command('ETH')
answer = gauge._get_data()
if int(answer.split(',')[0]) == 0:
    print("IP address:     ", answer.split(',')[1], "(statically)")
else:
    print("IP address:     ", answer.split(',')[1], "(dynamically)")
print("Subnet address: ", answer.split(',')[2])
print("Gateway address:", answer.split(',')[3])
print("----------------------------------------")
gauge._send_command('TID')
answer = gauge._get_data()
print("Gauge 1:", answer.split(',')[0])
print("Gauge 2:", answer.split(',')[1])
print("----------------------------------------")

# Device settings (same as before)
gauge._send_command('BAL,0')    # backlight 0%
gauge._send_command('UNI,0')    # unit mbar/bar
gauge._send_command('FMT,0')    # floating point format
gauge._send_command('GAS,0,0')  # gas type (air/nitrogen)
gauge._send_command('FSR,6,5')  # linear gauge ranges
gauge._send_command('FIL,2,2')  # filter normal
gauge._send_command('SAV,1')    # save parameters

# ---- Main acquisition loop ----
while True:
    try:
        # Request pressures
        gauge._send_command('PRX')
        answer = gauge._get_data()  # expected: status1,p1,status2,p2

        fields = answer.split(',')
        # Guard against malformed frames
        if len(fields) < 4:
            raise ValueError("incomplete frame: '{}'".format(answer))

        # Status codes
        statusCode_p1 = int(fields[0])
        statusCode_p2 = int(fields[2])

        # Parse pressures with special handling for 'OR'/'UR'
        try:
            p1 = parse_pressure_field(fields[1], offset_p1)
        except ValueError:
            # If not parseable, mark as None; we won't post it
            p1 = None

        try:
            p2 = parse_pressure_field(fields[3], offset_p2)
        except ValueError:
            p2 = None

        # Console output with timestamp
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        msg_parts = ["[{}]".format(ts)]
        if p1 is None:
            msg_parts.append("p1=INVALID")
        else:
            msg_parts.append("p1={:.6f} mbar".format(p1))
        msg_parts.append("statusCode_p1={}".format(statusCode_p1))
        if p2 is None:
            msg_parts.append("p2=INVALID")
        else:
            msg_parts.append("p2={:.6f} mbar".format(p2))
        msg_parts.append("statusCode_p2={}".format(statusCode_p2))
        print("  ".join(msg_parts))

        now_sec = int(time.time())

        # Post to InfluxDB
        # We will post even the sentinel values (1000, -1) as requested.
        if p1 is not None and statusCode_p1 == 0:
            line1 = "pressure,sens=sens-1 value={} {}".format(p1, now_sec)
            post_influx(line1)

        if p2 is not None and statusCode_p2 == 0:
            line2 = "pressure,sens=sens-2 value={} {}".format(p2, now_sec)
            post_influx(line2)

    except IOError:
        # Silently ignore transient serial/communication errors (as in your original code)
        pass
    except (ValueError, IndexError) as e:
        # Keep running even if a frame is malformed
        print("Error parsing gauge data: {}".format(e))

    # Prevent flooding gauge/console
    time.sleep(5)

