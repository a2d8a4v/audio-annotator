
import os
import re
import argparse
import asyncio
# import logging
import wave
import json
from typing import Tuple

import websockets
import numpy as np

from tqdm import tqdm

# from g2p_en import G2p

def read_wave_buff(wave_filename: str) -> Tuple[np.ndarray, int]:
    """
    Args:
      wave_filename:
        Path to a wave file. It should be single channel and each sample should
        be 16-bit. Its sample rate does not need to be 16kHz.
    Returns:
      Return a tuple containing:
       - A 1-D array of dtype np.float32 containing the samples, which are
       normalized to the range [-1, 1].
       - sample rate of the wave file
    """

    with wave.open(wave_filename) as f:
        assert f.getnchannels() == 1, f.getnchannels()
        assert f.getsampwidth() == 2, f.getsampwidth()  # it is in bytes
        num_samples = f.getnframes()
        samples = f.readframes(num_samples)
        samples_int16 = np.frombuffer(samples, dtype=np.int16)
        samples_float32 = samples_int16.astype(np.float32)

        samples_float32 = samples_float32 / 32768
        return samples_float32, f.getframerate()

def read_wave_chunk(wave_filename: str) -> np.ndarray:
    """
    Args:
      wave_filename:
        Path to a wave file. Its sampling rate has to be 16000.
        It should be single channel and each sample should be 16-bit.
    Returns:
      Return a 1-D float32 tensor.
    """

    with wave.open(wave_filename) as f:
        assert f.getframerate() == 16000, f.getframerate()
        assert f.getnchannels() == 1, f.getnchannels()
        assert f.getsampwidth() == 2, f.getsampwidth()  # it is in bytes
        num_samples = f.getnframes()
        samples = f.readframes(num_samples)
        samples_int16 = np.frombuffer(samples, dtype=np.int16)
        samples_float32 = samples_int16.astype(np.float32)

        samples_float32 = samples_float32 / 32768
        return samples_float32

async def k2_buff_run(
    server_addr: str,
    server_port: int,
    wave_filename: str,
):
    async with websockets.connect(
        f"ws://{server_addr}:{server_port}"
    ) as websocket:  # noqa
        # logging.info(f"Sending {wave_filename}")
        samples, sample_rate = read_wave_buff(wave_filename)
        assert isinstance(sample_rate, int)
        assert samples.dtype == np.float32, samples.dtype
        assert samples.ndim == 1, samples.dim
        buf = sample_rate.to_bytes(4, byteorder="little")  # 4 bytes
        buf += (samples.size * 4).to_bytes(4, byteorder="little")
        buf += samples.tobytes()

        payload_len = 10240
        while len(buf) > payload_len:
            await websocket.send(buf[:payload_len])
            buf = buf[payload_len:]

        if buf:
            await websocket.send(buf)

        decoding_results = await websocket.recv()
        # logging.info(f"{wave_filename}\n{decoding_results}")

        # to signal that the client has sent all the data
        await websocket.send("Done")
        return decoding_results

async def receive_results(socket: websockets.WebSocketServerProtocol):
    last_message = ""
    async for message in socket:
        if message != "Done!":
            last_message = message
        else:
            break
    return last_message

async def k2_chunk_run(
    server_addr: str,
    server_port: int,
    wave_filename: str,
    samples_per_message: int,
    seconds_per_message: float,
):
    data = read_wave_chunk(wave_filename)

    async with websockets.connect(
        f"ws://{server_addr}:{server_port}"
    ) as websocket:  # noqa

        receive_task = asyncio.create_task(receive_results(websocket))

        start = 0
        while start < data.shape[0]:
            end = start + samples_per_message
            end = min(end, data.shape[0])
            d = data.data[start:end].tobytes()

            await websocket.send(d)

            # Simulate streaming. You can remove the sleep if you want
            await asyncio.sleep(seconds_per_message)  # in seconds

            start += samples_per_message

        # to signal that the client has sent all the data
        await websocket.send("Done")

        decoding_results = await receive_task
        return decoding_results


async def k2_buff_call():

    all_tasks = []
    task = asyncio.create_task(
        k2_buff_run(
            server_addr=server_addr,
            server_port=port,
            wave_filename=wave_filename,
        )
    )
    all_tasks.append(task)

    # Capture the results of all tasks
    results = await asyncio.gather(*all_tasks)
    results = [json.loads(result) for result in results]
    return results  # Return the results

async def k2_chunk_call():

    results = await k2_chunk_run(
        server_addr=server_addr,
        server_port=port,
        wave_filename=wave_filename,
        samples_per_message=samples_per_message,
        seconds_per_message=seconds_per_message,
    )
    results = json.loads(results)

    return results  # Return the results

def remove_stress(phn_sequence):
    return re.sub(r'[0-9]+', '', phn_sequence)

def get_phoneme_durations(timestamps, tokens, text):
    phoneme_durations = []
    current_text_idx = 0
    current_phoneme = text[current_text_idx]
    start_time = None

    for i, token in enumerate(tokens):
        # If token matches the current phoneme or is part of it
        if token.strip() and current_phoneme.startswith(token.strip()):
            # Set start time if it's the first matching token for this phoneme
            if start_time is None:
                start_time = timestamps[i]
            # Remove matched part from current phoneme
            current_phoneme = current_phoneme[len(token.strip()):]
            # If phoneme is fully matched, set end time and record it
            if not current_phoneme:
                end_time = (timestamps[i] + timestamps[i + 1]) / 2 if i + 1 < len(timestamps) else timestamps[i]
                phoneme_durations.append((text[current_text_idx], start_time, end_time))
                # Move to the next phoneme in text
                current_text_idx += 1
                if current_text_idx < len(text):
                    current_phoneme = text[current_text_idx]
                start_time = None  # Reset for the next phoneme

    return phoneme_durations

async def get_phone_result(server_port):
    global port
    port = server_port
    try:
        return await k2_buff_call()
    except Exception as e1:
        print(f"Error in server port call: {e1}")
        return None

async def get_word_result(server_port):
    global port
    port = server_port
    try:
        return await k2_chunk_call()
    except Exception as e1:
        print(f"Error in server port call: {e1}")
        return None

async def phone_process_call():
    global server_addr, port, wave_filename, samples_per_message, seconds_per_message
    server_addr = '127.0.0.1'
    server_port = 6006
    streaming_server_port = 6007
    samples_per_message = 8000
    seconds_per_message = 0.1

    phone_result = await get_phone_result(server_port)
    if not phone_result:
        print("Retrying with streaming server port...")
        phone_result = await get_phone_result(streaming_server_port)
    
    if phone_result:
        timestamps = phone_result[0]['timestamps']
        tokens = phone_result[0]['tokens']
        text = phone_result[0]['text'].strip().split()

        return {
            'phone': {
                'text': phone_result[0]['text'].strip(),
                'time_alignment': get_phoneme_durations(timestamps, tokens, text)
            }
        }
    else:
        print("Failed to get phone result.")
        return None

async def word_process_call():
    global server_addr, port, wave_filename, samples_per_message, seconds_per_message
    server_addr = '127.0.0.1'
    word_server_port = 6008
    samples_per_message = 8000
    seconds_per_message = 0.1

    word_result = await get_word_result(word_server_port)

    if word_result:
        timestamps = word_result['timestamps']
        tokens = word_result['tokens']
        text = word_result['text'].strip().split()

        return {
            'word': {
                'text': word_result['text'].strip(),
                'time_alignment': get_phoneme_durations(timestamps, tokens, text)
            }
        }
    else:
        print("Failed to get word_result result.")
        return None

def k2call_for_phone_concurrent(wavefilename):
    global wave_filename
    wave_filename = wavefilename

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If an event loop is running, ensure we await the task and return the final result
        return asyncio.ensure_future(phone_process_call())
    else:
        # If no event loop is running, start one and get the result directly
        return asyncio.run(phone_process_call())


def k2call_for_word_concurrent(wavefilename):
    global wave_filename
    wave_filename = wavefilename

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If an event loop is running, ensure we await the task and return the final result
        return asyncio.ensure_future(word_process_call())
    else:
        # If no event loop is running, start one and get the result directly
        return asyncio.run(word_process_call())


def k2call_for_phone(wavefilename):
    global wave_filename
    wave_filename = wavefilename
    return phone_process_call()  # Return the coroutine directly without awaiting or running


def k2call_for_word(wavefilename):
    global wave_filename
    wave_filename = wavefilename
    return word_process_call()  # Return the coroutine directly without awaiting or running

def fix_timestamp(word_align_info, phone_align_info):
    phone_time_alignment_info = phone_align_info['phone']['time_alignment']
    word_time_alignment_info = word_align_info['word']['time_alignment']
    # Check if the last element's end time is equal to its start time in phone_time_alignment_info
    if phone_time_alignment_info[-1][-1] == phone_time_alignment_info[-1][1]:
        # Convert the last tuple to a list so it can be modified
        last_phone_entry = list(phone_time_alignment_info[-1])
        # Update the end time to match the end time of the last word in word_time_alignment_info
        last_phone_entry[-1] = word_time_alignment_info[-1][-1]
        # Reassign the modified tuple back to the list
        phone_time_alignment_info[-1] = tuple(last_phone_entry)
        phone_align_info['phone']['time_alignment'] = phone_time_alignment_info

    return word_align_info, phone_align_info

def convert_time_alignment_to_ctm(uttid, align_info, default_conf=1.0):
    # Initialize an empty list to store the CTM formatted output
    ctm_info = []
    
    # Loop through each phone alignment entry
    for (token, start_time, end_time) in align_info:
        # Calculate the duration of the phone
        duration = end_time - start_time
        
        # Append the CTM entry for each phone to the list
        ctm_info.append([uttid, default_conf, start_time, duration, token])
    
    return ctm_info

def check_if_success_decoded(word_aligned_info, phone_aligned_info):
    if len(phone_aligned_info) > 10 * len(word_aligned_info):
        return False
    return True

if __name__ == "__main__":

    # result = k2call_for_phone_concurrent('/home/jtlee/projects/data_process/EZAI_Championship2023/audio-annotator/wavs/test/35413_chapters_sentence_1081411_1683725734.wav')
    result = k2call_for_word_concurrent('/home/jtlee/projects/data_process/EZAI_Championship2023/audio-annotator/wavs/test/35413_chapters_sentence_1081411_1683725734.wav')
    if isinstance(result, asyncio.Task):
        # Await the task if it's an asyncio Task
        print('YES')
        result = asyncio.run(result)
    print(result)
