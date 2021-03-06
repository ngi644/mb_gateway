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

# Define service and characteristic UUIDs used by the UART service.
UART_SERVICE_UUID = uuid.UUID('6E400001-B5A3-F393-E0A9-E50E24DCCA9E')
TX_CHAR_UUID = uuid.UUID('6E400002-B5A3-F393-E0A9-E50E24DCCA9E')
RX_CHAR_UUID = uuid.UUID('6E400003-B5A3-F393-E0A9-E50E24DCCA9E')

microbits = set()
mb_dict = {}
known_devices = set()
cn_timing = store_path = max_threads = None

logging.basicConfig(filename='receive.log', level=logging.INFO)
ble = Adafruit_BluefruitLE.get_provider()
_queue = queue.Queue()



def default_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def _rx_received(data):
    value = dict(value=data, date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    _queue.put(value)
    print(_queue.qsize())


def main():
    ble.clear_cached_data()
    ble.list_adapters()
    ble.list_devices()

    adapter = ble.get_default_adapter()
    adapter.power_on()
    ble.disconnect_devices([UART_SERVICE_UUID])
    time.sleep(1.0)

    adapter.start_scan()
    atexit.register(adapter.stop_scan)

    txs = set()
    rxs = set()

    ct0 = 0

    while True:
        for mb in microbits.copy():
            if not mb.is_connected:
                for tx in txs.copy():
                    if not tx._device:
                        txs.remove(tx)
                for rx in rxs.copy():
                    if not rx._device:
                        rxs.remove(rx)
                print('Disconnect to microbit')
                microbits.remove(mb)
                known_devices.clear()

        if not ct0 % 100:
            known_devices.clear()
            logging.info('clear dv')
            ct0 = 1


        found = set(ble.find_devices())
        new = found - known_devices - microbits
        #print(new)
        for device in new:
            if device.name is not None and "micro:bit" in device.name: 
                print(u'Found devices: {0} [{1}]'.format(device.name, device.id))
                re_text = re.findall("\[.*?\]", device.name)
                if re_text:
                    device_name = re_text[0].replace('[', '').replace(']', '')
                    mb_dict[device_name] = device.id
                print('Connect to microbit')
                device.connect()
                device.discover([UART_SERVICE_UUID], [TX_CHAR_UUID, RX_CHAR_UUID])
                uart = device.find_service(UART_SERVICE_UUID)
                if uart:
                    print(device_name)
                    microbits.add(device)
                    txs.add(uart.find_characteristic(RX_CHAR_UUID))
                    rx = uart.find_characteristic(TX_CHAR_UUID)
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
                    logging.warning('no tx device')
        logging.info('now connected: {}'.format(len(microbits)))
        time.sleep(0.1)
        ct0 += 1

def check_connection():
    try:
        r = requests.get('https://firebase.google.com/')
        print(r)
        return True
    except:
        print('False')
        return False


def cloud_worker(fb_cn):
    ct = 0
    user = None
    while True:
        if True:#check_connection():
            if not ct % 900:
                if fb_cn.users:
                    user = fb_cn.auth.sign_in_with_email_and_password(fb_cn.users[0]['user_id'], fb_cn.users[0]['passkey'])
            ct += 1
            try:
                dataset = {}
                item = _queue.get(timeout=1)
                logging.info(item)
                mb_data = item.get('value').strip()
                dvice_name = mb_data[0:5]
                status = int(mb_data[5:6])
                clock = int(mb_data[6:9])
                data_type = mb_data[9:10]
                raw_data = mb_data[10:]
                if data_type == 'B':
                    bme_data = int(raw_data)
                    r_temp = bme_data >> 20 & 0xFFF
                    if r_temp > 2048:
                        temp = (r_temp - 4096) / 10.0
                    else:
                        temp = r_temp / 10.0
                    press = (bme_data >> 10 & 0x3FF) + 400
                    humid = (bme_data >> 0 & 0x3FF) / 10.0
                    dataset = dict(dvice_name=dvice_name,
                                status=status,
                                Timestamp=item.get('date'),
                                temp=temp,
                                humid=humid,
                                press=press
                                )
                if data_type == 'T':
                    dataset = dict(dvice_name=dvice_name,
                                status=status,
                                Timestamp=item.get('date'),
                                temp=int(raw_data)
                                )
                if data_type == 'D':
                    f_temp = struct.unpack('<f', binascii.unhexlify(raw_data))
                    ### f_temp = float(raw_data) / 100
                    dataset = dict(dvice_name=dvice_name,
                                status=status,
                                Timestamp=item.get('date'),
                                temp=f_temp[0]
                                )
                js_data = json.dumps(dataset, default=default_serializer)
                params = {}
                if user:
                    params['token'] = user['idToken']
                fb_cn.db.child('{}/{}'.format(store_path, mb_dict[dvice_name])).push(dataset, **params)
            except queue.Empty:
                logging.warning('no data')
                
        else:
            logging.warning('no network')
        time.sleep(0.1)


if __name__ == '__main__':

    desc = u'{0} [Args] [Options]\nDetailed options -h or --help'.format(__file__)
    parser = ArgumentParser(description=desc)
    parser.add_argument(
        '-c', '--config-json-path',
        type = str,         
        dest = 'config_path',     
        required = True,   
        help = 'config file path'
    )
    args = parser.parse_args()

    f = open(args.config_path, 'r')
    main_config = json.load(f)
    f.close()

    cn_timing = int(main_config.get('timing', 10))
    max_threads = int(main_config.get('max_threads', 1))
    store_path = main_config.get('store_path', 'test')

    fb_cn = Firebase_CN(main_config)

    ble.initialize()

    for i in range(max_threads):
        t = threading.Thread(target=cloud_worker, args=(fb_cn,))
        t.daemon = True
        t.start()

    ble.run_mainloop_with(main)
