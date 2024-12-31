#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2018/9/4 4:43 PM
# @Author  : vell
# @Email   : vellhe@tencent.com
import argparse
import codecs
import json
import logging.config
import logging.handlers
import os

import tornado.gen
import tornado.ioloop
import tornado.web
from tornado.web import Application

from server.base import BaseReqHandler
from server.get_task import GetTask
from server.post_ret import PostRet

current_dir = os.path.abspath('.')
log_file = os.path.join(current_dir, 'audio-annotator.log')
log_dir = os.path.join(current_dir, 'log_conf.json')


def load_log_config(path):
    config = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'verbose': {
                'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
                'datefmt': "%Y-%m-%d %H:%M:%S"
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            },
        },
        'handlers': {
            'null': {
                'level': 'DEBUG',
                'class': 'logging.NullHandler',
            },
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose'
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.TimedRotatingFileHandler',
                # 当达到10MB时分割日志
                # 'maxBytes': 1024 * 1024 * 100,
                # 最多保留50份文件
                'when': 'midnight',
                'backupCount': 50,
                # If delay is true,
                # then file opening is deferred until the first call to emit().
                'delay': True,
                'filename': log_file,
                'formatter': 'verbose'
            }
        },
        'loggers': {
            '': {
                'handlers': ['file', 'console'],
                'level': 'INFO',  # Set to DEBUG to show all logs, or INFO
                'propagate': True,
            },
        }
    }
    if path and os.path.exists(path):
        with codecs.open(path, "r", encoding="utf-8") as f:
            config = json.loads(f.read())

    logging.config.dictConfig(config)


class Hello(BaseReqHandler):
    def get(self):
        self.write('Hello World!')


class IndexHandler(BaseReqHandler):
    def get(self):
        self.render("index.html")


def run(host='127.0.0.1', port=8282, debug=True, apa_dir=None, audio_dir=None, wav_dir=os.path.join(os.path.dirname(__file__), "wavs"), reference_dir=None, inventory_file_path=None, save_dir=None, info_dir=None, json_suffix=None):
    settings = {
        "apa_dir": apa_dir,
        "wav_dir": wav_dir,
        "audio_dir": audio_dir,
        "info_dir": info_dir,
        "reference_dir": reference_dir,
        "inventory_file_path": inventory_file_path,
        "save_dir": save_dir,
        "json_suffix": json_suffix,
    }

    _app = Application([
        (r'/hello', Hello),
        (r'/', IndexHandler),
        (r'/post_ret', PostRet),
        (r'/get_task', GetTask),
        (r"/wavs/(.*.wav)", tornado.web.StaticFileHandler, {"path": settings["wav_dir"]}),
    ],
        # 项目配置信息
        # 网页模板
        template_path=os.path.join(os.path.dirname(__file__), "html/templates"),
        # 静态文件
        static_path=os.path.join(os.path.dirname(__file__), "html/static"),
        settings=settings,
        debug=debug)

    _app.listen(port, address=host)
    tornado.ioloop.IOLoop.current().start()


def main():
    parser = argparse.ArgumentParser(description=__name__)
    parser.add_argument("--host", default="0.0.0.0",
                        help='host, 0.0.0.0 代表外网可以访问')
    parser.add_argument('-p', "--port", default=8282, type=int,
                        help='port')
    parser.add_argument("-d", "--debug", default=True, type=bool,
                        help='debug')
    parser.add_argument("-l", "--log_config_file", default=log_dir,
                        help='log config file, json')
    parser.add_argument("-w", "--wav_dir", default=os.path.join(os.path.dirname(__file__), "wavs"),
                        help='audio files with kaldi format info: utt2spk, spk2utt, wav.scp, text')
    parser.add_argument("-u", "--audio_dir", default=os.path.join(os.path.dirname(__file__), "wavs"),
                        help='audio files with kaldi format info: utt2spk, spk2utt, wav.scp, text')
    parser.add_argument("-r", "--reference_dir", default='',
                        help='the reference list for the audio file list want to label')
    parser.add_argument("-s", "--save_dir", default=os.path.join(os.path.dirname(__file__), "save_json"))
    parser.add_argument("-f", "--info_dir", default=os.path.join(os.path.dirname(__file__), "info"))
    parser.add_argument("-a", "--apa_dir", default='')

    parser.add_argument("-t", "--json_suffix", default="label")
    
    parser.add_argument("-i", "--inventory_file_path", default=os.path.join(os.path.dirname(__file__), "/home/jtlee/projects/MDD/Peppanet/data/lang_39phn/phn_42_units.txt"))

    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)
    if not os.path.exists(args.save_dir):
        os.makedirs(args.save_dir)

    load_log_config(args.log_config_file)
    logger = logging.getLogger("root")
    logger.info("ADDRESS http://%s:%d, DEBUG %s", args.host, args.port, args.debug)

    run(host=args.host, port=args.port, debug=args.debug, apa_dir=args.apa_dir, audio_dir=args.audio_dir, wav_dir=args.wav_dir, reference_dir=args.reference_dir, inventory_file_path=args.inventory_file_path, save_dir=args.save_dir, info_dir=args.info_dir, json_suffix=args.json_suffix)


if __name__ == "__main__":
    main()
