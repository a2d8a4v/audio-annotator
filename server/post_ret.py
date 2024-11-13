#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2018/9/4 4:15 PM
# @Author  : vell
# @Email   : vellhe@tencent.com
import json
import logging
import os

from server.base import BaseReqHandler
from server.file_utils import get_relative_path

logger = logging.getLogger(__name__)


class PostRet(BaseReqHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.wav_dir = application.settings["settings"]["wav_dir"]
        self.save_dir = application.settings["settings"]["save_dir"]
        self.json_suffix = application.settings["settings"]["json_suffix"]

    def post(self):
        resp = {"ret": "ok",
                "msg": ""}
        try:
            ret_json = self.json_args
            uttid = ret_json["task"]["uttid"]

            # drop fields
            del ret_json["task"]

            logger.info(ret_json)
            # rel_wav_path = get_relative_path("/wavs", ret_json["task"]["url"])
            # wav_path = ret_json["task"]["url"]
            # file_name_without_extension = os.path.splitext(os.path.basename(wav_path))[0]
            # save_json_file_path = os.path.join(self.save_dir, file_name_without_extension + f".{self.json_suffix}.json")
            save_json_file_path = os.path.join(self.save_dir, uttid + f".{self.json_suffix}.json")
            with open(save_json_file_path, "w+", encoding="utf-8") as f:
                json.dump(ret_json, f, ensure_ascii=False)
            resp["msg"] = "保存成功"
        except Exception as e:
            logger.error(e)
            resp["ret"] = "error"
            resp["msg"] = e.__str__()

        self.write(json.dumps(resp))
