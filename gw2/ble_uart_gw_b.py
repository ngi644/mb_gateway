# coding: utf-8

import atexit
import time
import re
import struct
import binascii
import uuid
import threading
import queue
import logging
import requests
from datetime import date, datetime
import json
from argparse import ArgumentParser
from fb_connect import Firebase_CN
import Adafruit_BluefruitLE

SERVICE_UUID = uuid.UUID("0000A000-0000-1000-8000-00805F9B34FB")
READ_UUID = uuid.UUID("0000A001-0000-1000-8000-00805F9B34FB")
WRITE_UUID = uuid.UUID("0000A002-0000-1000-8000-00805F9B34FB")

microbits = set()
mb_dict = {}
known_devices = set()
cn_timing = store_path = max_threads = None

logging.basicConfig(filename="receive.log", level=logging.INFO)
ble = Adafruit_BluefruitLE.get_provider()
_queue = queue.Queue()


def default_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def _rx_received(data):
    value = dict(value=data, date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    _queue.put(value)
    print(_queue.qsize())


def main():
    ble.clear_cached_data()
    ble.list_adapters()
    ble.list_devices()

    adapter = ble.get_default_adapter()
    adapter.power_on()
    ble.disconnect_devices([SERVICE_UUID])
    time.sleep(1.0)

    adapter.start_scan()
    atexit.register(adapter.stop_scan)

    txs = set()
    rxs = set()

    while True:
        for mb in microbits.copy():
            if not mb.is_connected:
                for tx in txs.copy():
                    if not tx._device:
                        txs.remove(tx)
                for rx in rxs.copy():
                    if not rx._device:
                        rxs.remove(rx)
                print("Disconnect to microbit")
                microbits.remove(mb)
                known_devices.clear()

        found = set(ble.find_devices())
        new = found - known_devices - microbits
        # print(found)
        for device in new:
            if device.name is not None and "stem" in device.name:
                print(u"Found devices: {0} [{1}]".format(device.name, device.id))
                re_text = re.findall("\[.*?\]", device.name)
                if re_text:
                    device_name = re_text[0].replace("[", "").replace("]", "")
                    mb_dict[device_name] = device.id
                print("Connect to microbit")
                device.connect()
                device.discover([SERVICE_UUID], [READ_UUID, WRITE_UUID])
                uart = device.find_service(SERVICE_UUID)
                if uart:
                    microbits.add(device)
                    txs.add(uart.find_characteristic(WRITE_UUID))
                    rx = uart.find_characteristic(READ_UUID)
                    rx.start_notify(_rx_received)
                    rxs.add(rx)
                else:
                    device.disconnect()
                    known_devices.add(device)
            else:
                known_devices.add(device)

        if len(txs) > 0:
            for idx, tx in enumerate(txs, start=1):
                if tx._device and tx._device.is_connected:
                    tx.write_value("{0:03d}".format(cn_timing))
                else:
                    logging.warning("no tx device")
        time.sleep(1.0)


def check_connection():
    try:
        r = requests.get("https://firebase.google.com/")
        return True
    except:
        return False


def cloud_worker(fb_cn):
    while True:
        if check_connection():
            try:
                dataset = {}
                item = _queue.get(timeout=1)
                logging.info(item)
                mb_data = item.get("value").strip()
                dvice_name = mb_data[0:5]
                status = 0
                # clock = int(mb_data[6:9])
                data_type = mb_data[5:6]
                raw_data = mb_data[6:14]
                if data_type == "B":
                    bme_data = int(raw_data)
                    r_temp = bme_data >> 20 & 0xFFF
                    if r_temp > 2048:
                        temp = (r_temp - 4096) / 10.0
                    else:
                        temp = r_temp / 10.0
                    press = (bme_data >> 10 & 0x3FF) + 400
                    humid = (bme_data >> 0 & 0x3FF) / 10.0
                    dataset = dict(
                        dvice_name=dvice_name,
                        status=status,
                        Timestamp=item.get("date"),
                        temp=temp,
                        humid=humid,
                        press=press,
                    )
                if data_type == "T":
                    dataset = dict(
                        dvice_name=dvice_name,
                        status=status,
                        Timestamp=item.get("date"),
                        temp=int(raw_data),
                    )
                if data_type == "D":
                    f_temp = struct.unpack("<f", binascii.unhexlify(raw_data))
                    ### f_temp = float(raw_data) / 100
                    dataset = dict(
                        dvice_name=dvice_name,
                        status=status,
                        Timestamp=item.get("date"),
                        temp=f_temp[0],
                    )
                fb_cn.send("{}/{}".format(store_path, mb_dict[dvice_name]), dataset)
            except queue.Empty:
                logging.warning("no data")

        else:
            logging.warning("no network")
        time.sleep(0.5)


if __name__ == "__main__":

    desc = u"{0} [Args] [Options]\nDetailed options -h or --help".format(__file__)
    parser = ArgumentParser(description=desc)
    parser.add_argument(
        "-c",
        "--config-json-path",
        type=str,
        dest="config_path",
        required=True,
        help="config file path",
    )
    args = parser.parse_args()

    f = open(args.config_path, "r")
    main_config = json.load(f)
    f.close()

    cn_timing = int(main_config.get("timing", 10))
    max_threads = int(main_config.get("max_threads", 1))
    store_path = main_config.get("store_path", "test")

    fb_cn = Firebase_CN(main_config)

    ble.initialize()

    for i in range(max_threads):
        t = threading.Thread(target=cloud_worker, args=(fb_cn,))
        t.daemon = True
        t.start()

    ble.run_mainloop_with(main)
