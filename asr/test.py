timestamps = [0.0, 0.08, 0.12, 0.4, 0.56, 0.64, 0.8, 0.96, 1.08, 1.16, 1.32, 1.52, 1.68, 1.8, 1.96, 2.04, 2.08, 2.16, 2.32, 2.44, 2.56, 2.68, 2.76, 2.88, 2.96, 3.08, 3.2, 3.24, 3.36, 3.44, 3.6, 3.64, 3.68, 3.72, 3.84, 4.0, 4.08, 4.16, 4.32, 4.44, 4.64, 4.8, 4.84, 4.92, 5.04, 5.2, 5.32, 5.36, 5.4, 5.48, 5.52, 5.56, 5.6, 5.72, 5.84, 5.96, 6.04, 6.24]
tokens = [' ', 'h', 'h', ' ', 'a', 'w', ' eh', ' ', 'v', ' er', ' s', ' ah', ' m', ' r', ' ', 'a', 'y', ' t', ' ih', ' n', ' t', ' r', ' ah', ' s', ' t', ' ih', 'n', 'g', ' s', ' t', ' ', 'a', 'o', ' r', ' iy', ' ', 'z', ' l', ' eh', ' t', ' ah', ' ', 'p', ' eh', ' l', ' t', ' ', 'u', 'w', ' ', 'c', 'h', ' ih', ' l', ' d', ' r', ' ah', ' n']
text = ['hh', 'aw', 'eh', 'v', 'er', 's', 'ah', 'm', 'r', 'ay', 't', 'ih', 'n', 't', 'r', 'ah', 's', 't', 'ih', 'ng', 's', 't', 'ao', 'r', 'iy', 'z', 'l', 'eh', 't', 'ah', 'p', 'eh', 'l', 't', 'uw', 'ch', 'ih', 'l', 'd', 'r', 'ah', 'n']

print(len(timestamps))
print(len(tokens))
print(len(text))

# Function to map tokens and timestamps to phonemes with start and end times
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

# Generate phoneme start and end times
phoneme_durations = get_phoneme_durations(timestamps, tokens, text)

collect = []
# Print the phoneme durations
for phoneme, start, end in phoneme_durations:
    print([phoneme, start, end])
    collect.append([phoneme, start, end])
    # print(f"Phoneme: {phoneme}, Start time: {start:.2f}, End time: {end:.2f}")

print(len(collect))