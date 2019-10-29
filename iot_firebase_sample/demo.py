# coding: utf-8

import time
import random
from datetime import datetime
import json
from argparse import ArgumentParser
from fb_connect import FirebaseCN


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

    # Firebaseの接続情報を読み込む
    f = open(args.config_path, "r")
    main_config = json.load(f)
    f.close()

    # コンフィグデータから保存先パスを取得
    store_path = main_config.get("store_path", "test")

    # Firebase接続クラスオブジェクトのインスタンス
    fb_cn = FirebaseCN(main_config)

    # 10秒ごとに10回データを送信する
    for i in range(10):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dataset = dict(Timestamp=now, temp=random.uniform(25.0, 30.0))
        fb_cn.send(store_path, dataset)
        print(i, dataset)
        time.sleep(10)
