# coding: utf-8

import pyrebase


class Firebase_CN:
    
    def __init__(self, main_config):
        self.config = main_config.get('config', {})
        self.users = main_config.get('users', [])

        self.firebase = pyrebase.initialize_app(self.config)
        self.auth = self.firebase.auth()
        self.db = self.firebase.database()
        

if __name__ == '__main__':
    pass