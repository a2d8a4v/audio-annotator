#!/usr/bin/env bash
python run.py --host 0.0.0.0 \
              --port 8282 \
              --wav_dir /home/jtlee/projects/data_process/EZAI_Championship2023/exp_rocling2024/asr-based/whisper \
              --reference_dir /home/jtlee/projects/data_process/EZAI_Championship2023/exp_apa_20241021 \
              --save_dir save_json \
              --json_suffix label \
              --inventory_file_path conf/phn_42_units.txt
