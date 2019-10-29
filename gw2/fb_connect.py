# coding: utf-8

import pyrebase
from datetime import date, datetime
import json


def default_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


class FirebaseCN:
    def __init__(self, main_config):
        self.config = main_config.get("config", {})
        self.users = main_config.get("users", [])
        self.firebase = pyrebase.initialize_app(self.config)
        self.auth = self.firebase.auth()
        self.db = self.firebase.database()
        self.auth_user = None

    def check(self):
        if self.users:
            self.auth_user = self.auth.sign_in_with_email_and_password(
                self.users[0]["user_id"], self.users[0]["passkey"]
            )
            return True
        else:
            self.auth_user = None
            return False

    def send(self, store_path, dataset):
        """
        """
        js_data = json.dumps(dataset, default=default_serializer)
        params = {}
        if self.check():
            params["token"] = self.auth_user["idToken"]
        self.db.child(store_path).push(dataset, **params)



if __name__ == '__main__':
    pass