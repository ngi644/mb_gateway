# coding: utf-8

import pyrebase
import json

f = open('config.json', 'r')
main_config = json.load(f)
f.close()

cn_timing = int(main_config.get('timing', 10))
max_threads = int(main_config.get('max_threads', 1))
store_path = main_config.get('store_path', 'test')

config = main_config.get('config', {})
users = main_config.get('users', [])

firebase = pyrebase.initialize_app(config)

auth = firebase.auth()

db = firebase.database()


if __name__ == '__main__':
    pass