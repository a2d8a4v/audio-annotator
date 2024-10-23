#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2018/9/4 5:16 PM
# @Author  : vell
# @Email   : vellhe@tencent.com
import json
import asyncio

import logging
import os
import re

import random
import string

from server.base import BaseReqHandler
from server.file_utils import list_files, list_files_from_reference, find_child_path_by_re, load_audio_to_binary

from server.models.power_model import PowerCall

from asr.k2_asr_api import k2call_for_phone, k2call_for_word, fix_timestamp, convert_time_alignment_to_ctm, check_if_success_decoded
from nltk.nltk_api import call_nltk_api


logger = logging.getLogger(__name__)


class GetTask(BaseReqHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.wav_dir = application.settings["settings"]["wav_dir"]
        self.info_dir = application.settings["settings"]["info_dir"]
        self.save_dir = application.settings["settings"]["save_dir"]
        self.reference_dir = application.settings["settings"]["reference_dir"]
        self.json_suffix = application.settings["settings"]["json_suffix"]

        self.pattern = r'[0-9]+'

    def _get_task(self, tmp_wavs_key="all", record="record", wav_suffix=".wav", review=False):
        
        """
            self.application.settings remember what wav file has been loaded
        """

        # self.application.settings[tmp_wavs_key] = list_files(self.wav_dir, wav_suffix)
        self.application.settings[tmp_wavs_key] = list_files_from_reference(self.wav_dir, self.reference_dir)

        # if tmp_wavs_key not in self.application.settings:
        #     self.application.settings[tmp_wavs_key] = list_files(self.wav_dir, wav_suffix)
        #     self.application.settings[tmp_wavs_key] = list_files_from_reference(self.wav_dir, self.reference_dir)
        #     self.application.settings.setdefault(
        #         record,
        #         []
        #     )
        # else:
        #     ## fix the bug that refresh page loss the last file
        #     all_audio_dir = list_files(self.wav_dir, wav_suffix)
        #     for audio_dir in self.application.settings[record]:
        #         all_audio_dir.remove(audio_dir)
        #     self.application.settings[tmp_wavs_key] = all_audio_dir

        if not self.application.settings[tmp_wavs_key]:
            del self.application.settings[tmp_wavs_key]
            return None

        for uttid, audio_dir in self.application.settings[tmp_wavs_key].items():
            if review:
                # self.application.settings[tmp_wavs_key].remove(audio_dir)
                # self.application.settings[record].append(audio_dir)
                return uttid, audio_dir
            else:
                read_json_file_path = os.path.join(self.save_dir, uttid + f".{self.json_suffix}.json")

                if os.path.exists(read_json_file_path) and os.path.getsize(read_json_file_path) > 0:
                    self.application.settings[tmp_wavs_key].remove(audio_dir)
                    self.application.settings[record].append(audio_dir)
                else:
                    return uttid, audio_dir
        return None

    def _load_phone_inventory(self, inventory_file_path):
        phone_inventory = []
        with open(inventory_file_path, 'r', encoding='utf-8') as f:
            for info_line in f.readlines():
                info_line = info_line.strip()
                phone = info_line.split()[0]
                phone_inventory.append(phone)
        return phone_inventory

    async def get(self):
        review = self.get_argument('review', default="false")
        wav_name = self.get_argument('wav_name', default=".wav")
        user_id = self.get_argument("user_id", default="all")

        tmp_wavs_key = user_id + wav_name
        uttid, audio_dir = self._get_task(tmp_wavs_key=tmp_wavs_key, record="record", wav_suffix=wav_name, review=True)
        # uttid, audio_dir = self._get_task(tmp_wavs_key=tmp_wavs_key, record="record", wav_suffix=wav_name, review=(review == "true"))

        inventory = self._load_phone_inventory(self.application.settings["settings"]["inventory_file_path"])

        resp = dict()
        if not audio_dir:
            # 没有wav了
            resp["ret"] = "no_tasks"
        else:
            resp["ret"] = "ok"

            annotations = []
            utt_score_annotations = {
                'utt_accuracy': 0,
                'utt_total': 0,
                'utt_completeness': 0,
                'utt_prosodic': 0,
                'utt_fluency': 0,
            }
            word_score_annotations = {}
            phone_score_annotations = {}
            tier = ['phone', 'word']

            info_json_file_path = os.path.join(audio_dir, f"{uttid}.json")
            read_json_file_path = os.path.join(self.save_dir, uttid + f".{self.json_suffix}.json")

            if os.path.exists(read_json_file_path) and os.path.getsize(read_json_file_path) > 0:
                with open(read_json_file_path, 'r', encoding="utf-8") as f:
                    task_ret = json.load(f)
                    utt_score_annotations.update(task_ret["score_annotations"])

            # 1. get the preloaded alignment information (by Whisper)
            if os.path.exists(info_json_file_path) and os.path.getsize(info_json_file_path) > 0:
                with open(info_json_file_path, encoding="utf-8") as f:
                    task_info = json.load(f)

            wav_path = task_info[uttid][uttid]['wav_path'] # permission issue

            # 2. get the alignment information by concurrent ASR systems

            # 2-1. by k2
            k2_decoded_info_of_phone = await k2call_for_phone(wav_path)
            k2_decoded_info_of_word = await k2call_for_word(wav_path)
            k2_decoded_info_of_word, k2_decoded_info_of_phone = fix_timestamp(k2_decoded_info_of_word, k2_decoded_info_of_phone)
            phone_ctm_info = convert_time_alignment_to_ctm(uttid, k2_decoded_info_of_phone['phone']['time_alignment'])
            word_ctm_info = convert_time_alignment_to_ctm(uttid, k2_decoded_info_of_word['word']['time_alignment'])

            if not check_if_success_decoded(word_ctm_info, phone_ctm_info):
                phone_ctm_info = task_info[uttid][uttid]['ctm']
                word_ctm_info = task_info[uttid][uttid]['word_ctm']
                prompt = task_info[uttid][uttid]['prompt'].upper()
                stt = call_nltk_api(task_info[uttid][uttid]['stt'])

            # 2-2. by kaldi
            # 2-3. by whisper
            # 2-4. by CTC-based SSL

            # 3. word to phone sequence aligment
            power_alignment = PowerCall()
            # task_info[uttid][uttid]['prompt'],
            aligner_collect = power_alignment.power_alignment_with_phone_sequence(
                prompt,
                stt,
                k2_decoded_info_of_phone
            )

            # 4. get GOPT predicted results
            # word_score_annotations
            # phone_score_annotations

            for _, conf, start_time, duration, phone in phone_ctm_info:
                pure_phone = re.sub(self.pattern, '', phone).split('_')[0]
                suffix_random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=11))
                annotations.append(
                    {
                        "id": f"wavesurfer_{suffix_random_string}",
                        "start": start_time,
                        "end": start_time+duration,
                        "annotation": [
                            "phone",
                            pure_phone
                        ]
                    }
                )

            for _, conf, start_time, duration, word in word_ctm_info:
                suffix_random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=11))
                annotations.append(
                    {
                        "id": f"wavesurfer_{suffix_random_string}",
                        "start": start_time,
                        "end": start_time+duration,
                        "annotation": [
                            "word",
                            word
                        ]
                    }
                )

            wav_binary = load_audio_to_binary(wav_path)
            filename_without_extension = os.path.splitext(os.path.basename(wav_path))[0]
            filename_without_extension = os.path.splitext(os.path.basename(wav_path))[0]

            resp["task"] = {
                "feedback": "none",
                "visualization": "waveform",
                "proximityTag": [],
                "annotationTag": inventory,
                "annotationTier": tier,
                "annotationUtteranceScore": utt_score_annotations, # regenerate from GOPT inferencing or saved json file
                # "annotationWordScore": word_score_annotations, # regenerate from GOPT inferencing or saved json file 
                # "annotationPhoneScore": phone_score_annotations, # regenerate from GOPT inferencing or saved json file
                "filename_without_extension": filename_without_extension,
                "uttid": uttid,
                "wav_binary": wav_binary,
                "tutorialVideoURL": "",
                "alwaysShowTags": True,
                "annotations": annotations, # regenerate from time-aligned information or saved json file
                "alignCollect": aligner_collect, 
            }
        self.write(json.dumps(resp))
