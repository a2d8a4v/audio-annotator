#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2018/9/4 5:16 PM
# @Author  : vell
# @Email   : vellhe@tencent.com
import json
import asyncio
import math

import traceback

import logging
import os
import re
import copy

import random
import string

from server.base import BaseReqHandler
from server.file_utils import list_files, list_files_from_reference, find_child_path_by_re, load_audio_to_binary

from server.models.power_model import PowerCall

from asr.k2_asr_api import k2call_for_phone, k2call_for_word, fix_timestamp, convert_time_alignment_to_ctm, check_if_success_decoded
from nlp.nltk_api import call_nltk_api

logging.basicConfig(filename='handler_errors.log', level=logging.ERROR)
logger = logging.getLogger(__name__)


class GetTask(BaseReqHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.apa_dir = application.settings["settings"]["apa_dir"]
        self.wav_dir = application.settings["settings"]["wav_dir"]
        self.info_dir = application.settings["settings"]["info_dir"]
        self.save_dir = application.settings["settings"]["save_dir"]
        self.reference_dir = application.settings["settings"]["reference_dir"]
        self.json_suffix = application.settings["settings"]["json_suffix"]

        self.pattern = r'[0-9]+'

    def _get_task(self, tmp_wavs_key="all", record="record", utt2level="utt2level", wav_suffix=".wav", review=False):
        
        """
            self.application.settings remember what wav file has been loaded
        """

        if tmp_wavs_key not in self.application.settings:
            self.application.settings[tmp_wavs_key], self.application.settings[utt2level] = list_files_from_reference(self.wav_dir, self.reference_dir)
            self.application.settings.setdefault(
                record,
                []
            )
        else:
            ## fix the bug that refresh page loss the last file
            utt2audio_dir, _ = list_files_from_reference(self.wav_dir, self.reference_dir)
            for uttid in self.application.settings[record]:
                del utt2audio_dir[uttid]
            self.application.settings[tmp_wavs_key] = utt2audio_dir

        if not self.application.settings[tmp_wavs_key]:
            del self.application.settings[tmp_wavs_key]
            return None, None, None

        before_change_all = copy.deepcopy(self.application.settings[tmp_wavs_key]) # dict should not change size when iteration
        for uttid, audio_dir in before_change_all.items():
            level = self.application.settings[utt2level][uttid]
            if review:
                del self.application.settings[tmp_wavs_key][uttid]
                self.application.settings[record].append(uttid)
                return uttid, audio_dir, level
            else:
                read_json_file_path = os.path.join(self.save_dir, uttid + f".{self.json_suffix}.json")
                if os.path.exists(read_json_file_path) and os.path.getsize(read_json_file_path) > 0:
                    del self.application.settings[tmp_wavs_key][uttid]
                    self.application.settings[record].append(uttid)
                else:
                    return uttid, audio_dir, level
        return None, None, None

    def _load_phone_inventory(self, inventory_file_path):
        phone_inventory = []
        with open(inventory_file_path, 'r', encoding='utf-8') as f:
            for info_line in f.readlines():
                info_line = info_line.strip()
                phone = info_line.split()[0]
                phone_inventory.append(phone)
        return phone_inventory

    def rounding(self, number):
        # Divide the number by 10
        result = number / 10
        
        # Check the decimal part and decide whether to round up or down
        if result - int(result) >= 0.5:
            # Round up if the decimal part is 0.5 or more
            c = math.ceil(result)
            if c >= 10:
                c = 10
            return c
        else:
            # Round down otherwise
            f = math.floor(result)
            # we allow zero
            return f

    def handle_request(self, prompt, stt, k2_decoded_info_of_phone):
        try:
            # Main request handling logic
            power_alignment = PowerCall()
            aligner_collect = power_alignment.power_alignment_with_phone_sequence(
                prompt,
                stt,
                k2_decoded_info_of_phone
            )
            return aligner_collect
        except Exception as e:

            # Option 2: Log the error for later debugging
            logging.error(f"An error occurred: {e}")

    async def get(self):
        try:
            review = self.get_argument('review', default="false")
            wav_name = self.get_argument('wav_name', default=".wav")
            user_id = self.get_argument("user_id", default="all")

            tmp_wavs_key = user_id + wav_name
            uttid, audio_dir, level = self._get_task(tmp_wavs_key=tmp_wavs_key, record="record", wav_suffix=wav_name, review=(review == "true"))
            # uttid, audio_dir, level = self.handle_request(tmp_wavs_key, review, wav_name, user_id)

            inventory = self._load_phone_inventory(self.application.settings["settings"]["inventory_file_path"])

            resp = dict()
            if not audio_dir:
                # 没有wav了
                resp["ret"] = "no_tasks"
            else:
                resp["ret"] = "ok"

                apa_ret = None
                task_ret = None
                annotations = []
                utt_score_annotations = {}
                word_score_annotations = []
                phone_score_annotations = []
                tier = ['phone', 'word']

                info_json_file_path = os.path.join(audio_dir, f"{uttid}.json")
                read_json_file_path = os.path.join(self.save_dir, uttid + f".{self.json_suffix}.json")
                apa_json_file_path = os.path.join(self.apa_dir, level, uttid, f"{uttid}.azure.prompt.json")

                if os.path.exists(read_json_file_path) and os.path.getsize(read_json_file_path) > 0:
                    with open(read_json_file_path, 'r', encoding="utf-8") as f:
                        task_ret = json.load(f)
                        utt_score_annotations.update(task_ret["utt_score_annotations"])
                        num_entries = len(task_ret["word_score_annotatoins"]['s_w_acc_anno_'])
                        for i in range(num_entries):
                            word_score = {
                                'word_accuracy': task_ret["word_score_annotatoins"]['s_w_acc_anno_'].get(f's_w_acc_anno_{i}', ''),
                                'word_stress': task_ret["word_score_annotatoins"]['s_w_str_anno_'].get(f's_w_str_anno_{i}', ''),
                                'word_total': task_ret["word_score_annotatoins"]['s_w_tol_anno_'].get(f's_w_tol_anno_{i}', '')
                            }

                            word_score_annotations.append(word_score)

                        num_entries = len(task_ret['phone_score_annotations']['diag_anno_'])
                        # Loop through each entry index
                        for i in range(num_entries):
                            phoneme = task_ret['phone_score_annotations']['diag_anno_'].get(f'diag_anno_{i}', '')
                            accuracy_score = task_ret['phone_score_annotations']['s_p_acc_anno_'].get(f's_p_acc_anno_{i}', '')
                            
                            # Convert accuracy_score to integer if it's not empty, otherwise set to 1
                            accuracy_score = int(accuracy_score) if accuracy_score else 1
                            
                            # Append each dictionary to the phone_score_annotations list
                            phone_score_annotations.append({
                                'phoneme': phoneme,
                                'accuracy_score': accuracy_score
                            })

                if os.path.exists(apa_json_file_path) and os.path.getsize(apa_json_file_path) > 0:
                    with open(apa_json_file_path, 'r', encoding="utf-8") as f:
                        apa_ret = json.load(f)
                        if not utt_score_annotations:
                            utt_score_annotations = {
                                'utt_accuracy': self.rounding(apa_ret['scores']['accuracy_score']),
                                'utt_total': self.rounding(apa_ret['scores']['pronunciation_score']),
                                'utt_completeness': self.rounding(apa_ret['scores']['completeness_score']),
                                'utt_prosodic': self.rounding(apa_ret['scores']['prosody_score']),
                                'utt_fluency': self.rounding(apa_ret['scores']['fluency_score']),
                            }
                        if not word_score_annotations:
                            for word_info in apa_ret['word_scores']:
                                word_score = {
                                    'word_accuracy': self.rounding(word_info['accuracy_score']),
                                    'word_stress': 1,
                                    'word_total': 1,
                                }
                                word_score_annotations.append(word_score)

                # 1. get the preloaded alignment information (by Whisper)
                if os.path.exists(info_json_file_path) and os.path.getsize(info_json_file_path) > 0:
                    with open(info_json_file_path, encoding="utf-8") as f:
                        task_info = json.load(f)

                wav_path = task_info[uttid][uttid]['wav_path'] # permission issue

                # 2. get the alignment information by concurrent ASR systems

                # 2-1. by k2
                try:
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
                    else:
                        prompt = task_info[uttid][uttid]['prompt'].upper()
                        stt = k2_decoded_info_of_word['word']['text']
                except:
                    phone_ctm_info = task_info[uttid][uttid]['ctm']
                    word_ctm_info = task_info[uttid][uttid]['word_ctm']
                    prompt = task_info[uttid][uttid]['prompt'].upper()
                    stt = call_nltk_api(task_info[uttid][uttid]['stt'])
                    
                print(uttid)

                # 2-2. by kaldi
                # 2-3. by whisper
                # 2-4. by CTC-based SSL

                # 3. word to phone sequence aligment
                # power_alignment = PowerCall()
                # aligner_collect = power_alignment.power_alignment_with_phone_sequence(
                #     prompt,
                #     stt,
                #     k2_decoded_info_of_phone
                # )
                aligner_collect = self.handle_request(prompt, stt, k2_decoded_info_of_phone)

                if not phone_score_annotations and apa_ret is not None:
                    max_length = len(aligner_collect['ref_phones_by_word'])
                    phoneme_scores = []
                    for w_i, word_info in enumerate(apa_ret['word_scores'][:max_length]):
                        phoneme_score = word_info['phoneme_score']
                        phone_seq_of_w_i = aligner_collect['ref_phones_by_word'][w_i]

                        apa_phone_seq = [p['phoneme'].upper() for p in phoneme_score]
                        align_phone_seq = [p.upper() for p in phone_seq_of_w_i]

                        if apa_phone_seq == align_phone_seq:
                            phoneme_scores.extend(phoneme_score)
                        else:
                            phoneme_scores.extend([{"phoneme": p, "accuracy_score": 1} for p in phone_seq_of_w_i])

                    iter_phone_seq = []
                    if len(aligner_collect['segment_ref_hyp_word_count_align']['ref_phones']) > len(aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones']):
                        iter_phone_seq = aligner_collect['segment_ref_hyp_word_count_align']['ref_phones']
                    elif len(aligner_collect['segment_ref_hyp_word_count_align']['ref_phones']) < len(aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones']):
                        iter_phone_seq = aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones']
                    else:
                        iter_phone_seq = aligner_collect['segment_ref_hyp_word_count_align']['ref_phones']

                    cindex = 0
                    for t in iter_phone_seq:
                        if t not in ["|", ""] and cindex <= len(phoneme_scores) - 1:
                            item = {
                                'phoneme': phoneme_scores[cindex]['phoneme'],
                                'accuracy_score': self.rounding(phoneme_scores[cindex]['accuracy_score']),
                            }
                            cindex += 1  # Move to the next item in iter_phoneme_scores
                        else:
                            item = {"phoneme": "", "accuracy_score": 1}
                        phone_score_annotations += [item]

                # 4. get GOPT predicted results
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
                    "annotationWordScore": word_score_annotations, # regenerate from GOPT inferencing or saved json file 
                    "annotationPhoneScore": phone_score_annotations, # regenerate from GOPT inferencing or saved json file
                    "filename_without_extension": filename_without_extension,
                    "uttid": uttid,
                    "wav_binary": wav_binary,
                    "tutorialVideoURL": "",
                    "alwaysShowTags": True,
                    "annotations": annotations, # regenerate from time-aligned information or saved json file
                    "alignCollect": aligner_collect, 
                }
            self.write(json.dumps(resp))

        except Exception as e:

            # Option 2: Log the error for later debugging
            detailed_error = traceback.format_exc()
            print(f"An error occurred: {e}\n{detailed_error}")
