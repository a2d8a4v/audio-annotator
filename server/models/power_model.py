from power.aligner import PowerAligner
from power.levenshtein import ExpandedAlignment

class PowerCall:

    def __init__(self):
        # lexicon = "lex/cmudict.0.7a.json"
        # lexicon = "lex/cmudict.rep.json"
        self.lexicon = "lex/lexicon.json"

    def _collapse_list(self, seq):
        return list(dict.fromkeys(seq))

    def align_pair(self, expanded_align: ExpandedAlignment, align_type='ref'):
        """
        `align_type` are either `ref` or `hyp`
        """
        type_id = 1 if align_type == 'ref' else 2

        smap = getattr(expanded_align, f"s{type_id}_map")
        # Be careful of the parentheses at the end, you need to run this `tokens` function
        s_tokens = list(getattr(expanded_align, f"s{type_id}_tokens")())
        align_result = [""] * (smap[-1]+1)
        for pos, tk in zip(self._collapse_list(smap), s_tokens):
            align_result[pos] = tk
        return align_result

    def count_fs(self, arr):
        return [
            len(group)
            for group in ''.join(arr).split('t')  # Join array into a single string and split by 't'
            if len(group) > 0                     # Filter out empty groups
        ]

    def count_items_between_pipes(self, lst):
        counts = []
        counting = False
        count = 0

        for item in lst:
            if item == '|':
                if counting:
                    # If we are already counting, end this count and start a new one
                    counts.append(count)
                # Reset count and start counting
                counting = True
                count = 0
            elif counting:
                # Count non-empty items between pipes
                count += 1

        return counts

    def remove_leading_blanks(self, lst):
        # Find the first non-empty element's index
        for i, item in enumerate(lst):
            if item != '':
                return lst[i:]  # Return the list starting from the first non-empty element
        return []  # Return an empty list if all elements are empty

    def power_alignment_with_phone_sequence(self, ref, hyp, phone_object):

        aligner = PowerAligner(ref, hyp, lowercase=True, lexicon=self.lexicon)
        aligner_collect = aligner.align()

        new_aligner_collect = {}

        collect_split_regions = aligner.split_regions_before_merge

        for i, info in aligner_collect.items():

            """
            {
                'ref_words': ref_words,
                'hyp_words': hyp_words,
                'ref_phones': ref_phones,
                'hyp_phones': hyp_phones,
                'word_align': None,
                'phone_align': None,
            }
            """
            # word level
            ref_words = self.align_pair(collect_split_regions[i], 'ref')
            hyp_words = self.align_pair(collect_split_regions[i], 'hyp')
            word_ref = collect_split_regions[i].s1_tokens()
            word_s1_map = collect_split_regions[i].s1_map
            word_hyp = collect_split_regions[i].s2_tokens()
            word_s2_map = collect_split_regions[i].s2_map
            word_eval = collect_split_regions[i].align

            info['ref_words'] = ref_words
            info['hyp_words'] = hyp_words
            info['word_align'] = {
                'word_ref': word_ref,
                'word_s1_map': word_s1_map,
                'word_hyp': word_hyp, 
                'word_s2_map': word_s2_map,
                'word_eval': word_eval,
            }

            # print(i)
            # print(ref_words)
            # print(hyp_words)
            # print(word_ref)
            # print(word_s1_map)
            # print(word_hyp)
            # print(word_s2_map)
            # print(word_eval)

            # phone level
            if info['phone_align'] is not None:
                phone_ref = aligner.phonetic_alignments[i].s1_tokens()
                phone_s1_map = aligner.phonetic_alignments[i].s1_map
                phone_hyp = aligner.phonetic_alignments[i].s2_tokens()
                phone_s2_map = aligner.phonetic_alignments[i].s2_map
                phone_eval = aligner.phonetic_alignments[i].align

                # fix the empty phone_s1_map
                if not phone_s1_map:
                    # the first token of phone_ref and phone_hyp should be '|', that is, 'C' as the eval result
                    s1_map_start_index = [i for i , t in enumerate(phone_eval) if t == 'C'][0]
                    phone_s1_map = [i + s1_map_start_index for i , t in enumerate(phone_eval[s1_map_start_index:]) if t != 'I']
                    phone_s1_map.append(phone_s1_map[-1]+1)

                # fix the last missing '|'
                if '|' != phone_ref[-1]:
                    phone_ref.append('|')
                    phone_hyp.append('|')
                    phone_eval.append('C') # because they are '|'
                    assert phone_s2_map, 'phone_s2_map is empty'
                    phone_s1_map.append(phone_s2_map[-1]+1)
                    phone_s2_map.append(phone_s2_map[-1]+1)

                # print('A')
                # print(phone_ref)
                # print(phone_hyp)
                # print(phone_s1_map)
                # print(phone_s2_map)
                # print(phone_eval)

                info['phone_align'] = {
                    'phone_ref': phone_ref,
                    'phone_s1_map': phone_s1_map,
                    'phone_hyp': phone_hyp,
                    'phone_s2_map': phone_s2_map,
                    'phone_eval': phone_eval,
                }
            else:
                # they should be the same length of sequences
                ref_phones = aligner.pronouncer.pronounce(ref_words)
                hyp_phones = aligner.pronouncer.pronounce(hyp_words)
                # phone_s1_map = list(range(0, len(ref_phones)))
                # phone_s2_map = list(range(0, len(ref_phones)))
                # phone_eval = ['C' if r == h else 'S' for r, h in zip(ref_phones, hyp_phones)]
                phone_s1_map = []
                phone_s2_map = []
                phone_eval = []
                str_ref_phones = ' '.join(ref_phones)
                str_hyp_phones = ' '.join(hyp_phones)

                new_phone_ref = []
                new_phone_hyp = []

                # print('B')
                # print(ref_phones)
                # print(hyp_phones)
                # print(phone_s1_map)
                # print(phone_s2_map)
                # print(phone_eval)

                phone_pa = PowerAligner(str_ref_phones, str_hyp_phones, lowercase=True, lexicon=self.lexicon)
                phone_pa.align()
                phone_pa_region = phone_pa.split_regions_before_merge
                
                seg_phone_index = 0
                for ii in range(len(phone_pa_region)):
                    phone_seg_ref = self.align_pair(phone_pa_region[ii], 'ref')
                    phone_seg_hyp = self.align_pair(phone_pa_region[ii], 'hyp')
                    phone_seg_s1_map = phone_pa_region[ii].s1_map
                    phone_seg_s2_map = phone_pa_region[ii].s2_map
                    phone_seg_eval = phone_pa_region[ii].align
                    phone_seg_s1_map = [i + seg_phone_index for i in phone_seg_s1_map]
                    phone_seg_s2_map = [i + seg_phone_index for i in phone_seg_s2_map]
                    phone_s1_map.extend(phone_seg_s1_map)
                    phone_s2_map.extend(phone_seg_s2_map)
                    phone_eval.extend(phone_seg_eval)
                    new_phone_ref.extend(phone_seg_ref)
                    new_phone_hyp.extend(phone_seg_hyp)

                    # print(phone_seg_ref)
                    # print(phone_seg_hyp)
                    # print(phone_seg_s1_map)
                    # print(phone_seg_s2_map)
                    # print(phone_seg_eval)
                    seg_phone_index += len(phone_seg_eval)

                ref_phones = ' '.join(new_phone_ref)
                hyp_phones = ' '.join(new_phone_hyp)

                info['phone_align'] = {
                    'phone_ref': ref_phones,
                    'phone_s1_map': phone_s1_map,
                    'phone_hyp': hyp_phones,
                    'phone_s2_map': phone_s2_map,
                    'phone_eval': phone_eval,
                }

            new_aligner_collect[i] = info

        # merge
        del aligner_collect
        # assert len(new_aligner_collect) < 1
        if len(new_aligner_collect) == 1:
            aligner_collect = new_aligner_collect[0]
        else:
            new_aligner_collect = dict(sorted(new_aligner_collect.items())) # key ascending sort

            # Combine the segments
            combined = {
                'ref_words': [],
                'ref_phones': [],
                'hyp_words': [],
                'hyp_phones': [],
                'segment_ref_hyp_word_count_align': {},
                'word_align': {
                    'word_s1_map': [],
                    'word_s2_map': [],
                    'word_eval': []
                },
                'phone_align': {
                    'phone_s1_map': [],
                    'phone_s2_map': [],
                    'phone_eval': []
                }
            }

            # Initialize index counters
            word_index = 0
            phone_index = 0

            # Process each segment in order
            for key, segment in new_aligner_collect.items():
                # Concatenate hyp_words
                combined['ref_words'].extend(segment['ref_words'])
                combined['hyp_words'].extend(segment['hyp_words'])
                
                # Update word_align
                combined['word_align']['word_s1_map'].extend([i + word_index for i in segment['word_align']['word_s1_map']])
                combined['word_align']['word_s2_map'].extend([i + word_index for i in segment['word_align']['word_s2_map']])
                combined['word_align']['word_eval'].extend(segment['word_align']['word_eval'])
                
                # Concatenate hyp_phones and skip leading '|'
                hyp_phones = segment['hyp_phones']
                ref_phones = segment['ref_phones']
                phone_s1_map = segment['phone_align']['phone_s1_map']
                phone_s2_map = segment['phone_align']['phone_s2_map']
                phone_eval = segment['phone_align']['phone_eval']

                # print(hyp_phones)
                # print(ref_phones)
                # print(phone_s1_map)
                # print(phone_s2_map)
                # print(phone_eval)

                if hyp_phones[0] == '|' and key != 0:
                    hyp_phones = hyp_phones[1:] # Remove initial '|'
                    ref_phones = ref_phones[1:]
                    phone_s1_map = phone_s1_map[1:]
                    phone_s2_map = phone_s2_map[1:]
                    phone_eval = phone_eval[1:]
                    phone_s1_map = [i - 1 for i in phone_s1_map] # because we remove the leading character, we need to eliminate 1 to each of index
                    phone_s2_map = [i - 1 for i in phone_s2_map]
                combined['hyp_phones'].extend(hyp_phones)
                combined['ref_phones'].extend(ref_phones)
                combined['phone_align']['phone_s1_map'].extend([i + phone_index for i in phone_s1_map])
                combined['phone_align']['phone_s2_map'].extend([i + phone_index for i in phone_s2_map])
                combined['phone_align']['phone_eval'].extend(phone_eval)
                
                # Align
                # combined['segment_ref_hyp_phone_count_align'][key] = [len(ref_phones), len(hyp_phones)]

                # Update indices
                word_index += len(segment['hyp_words'])
                phone_index += len(segment['hyp_phones']) - 1 if key > 0 else len(segment['hyp_phones']) # Subtracting one for skipped '|'

            # post-process
            a = combined['ref_phones']
            b = combined['hyp_phones']
            c = combined['phone_align']['phone_s1_map']
            d = combined['phone_align']['phone_s2_map']
            e = combined['phone_align']['phone_eval']

            new_phone_ref = []
            new_phone_hyp = []
            iter_a, iter_b = iter(a), iter(b)
            # print('a: ', a, len(a))
            # print('b: ', b, len(b))
            # print('c: ', c)
            # print('d: ', d)
            # print('e: ', e, len(e))

            for i in range(0, len(e)):
                # print(i)
                new_phone_ref.append(next(iter_a, '') if i in c else '')
                new_phone_hyp.append(next(iter_b, '') if i in d else '')

            s1_leading_blank_count = c[0]
            s2_leading_blank_count = d[0]
            # print('new_phone_ref: ', new_phone_ref)
            phone_ref_position = self.count_items_between_pipes(new_phone_ref)
            phone_hyp_position = self.count_items_between_pipes(new_phone_hyp)

            a = combined['ref_words']
            b = combined['hyp_words']
            new_word_ref = []
            new_word_hyp = []
            for word in a:
                # If the word contains a space, split it and extend the result list with the split words
                if ' ' in word:
                    new_word_ref.extend(word.split())
                else:
                    # Otherwise, just append the word as it is
                    new_word_ref.append(word)
            new_word_ref = self.remove_leading_blanks(new_word_ref)
            for word in b:
                # If the word contains a space, split it and extend the result list with the split words
                if ' ' in word:
                    new_word_hyp.extend(word.split())
                else:
                    # Otherwise, just append the word as it is
                    new_word_hyp.append(word)
            new_word_hyp = self.remove_leading_blanks(new_word_hyp)

            combined['segment_ref_hyp_word_count_align'] = {
                'ref_phones': new_phone_ref,
                'hyp_phones': new_phone_hyp,
                's1_leading_blank_count': s1_leading_blank_count,
                's2_leading_blank_count': s2_leading_blank_count,
                'phone_ref_position': phone_ref_position,
                'phone_hyp_position': phone_hyp_position,
                'ref_words': new_word_ref,
                'hyp_words': new_word_hyp,
            }

            new_aligner_collect = combined

        # decide to replace the asr decoded phone sequence or remain the original one
        # (recognized by word level then conversion to phone by lexicon)
        # phone_object

        # print('------------')
        # print(new_aligner_collect['ref_words'])
        # print(new_aligner_collect['hyp_words'])

        # print(new_aligner_collect['ref_phones'])
        # print(new_aligner_collect['hyp_phones'])

        # print(new_aligner_collect['phone_align']['phone_s1_map'])
        # print(new_aligner_collect['phone_align']['phone_s2_map'])
        # print(new_aligner_collect['phone_align']['phone_eval'])
        # print(combined['segment_ref_hyp_word_count_align'])
        # print('------------')

        return new_aligner_collect

    def power_alignment_with_only_lexicon(self, ref, hyp):
        
        collect_word_error_type_sequence = []
        collect_phone_error_type_sequence = []

        aligner = PowerAligner(ref, hyp, lowercase=True, lexicon=self.lexicon)
        aligner.align()

        collect_split_regions = aligner.split_regions_before_merge

        for i in range(len(collect_split_regions)):
            word_ref = self.align_pair(collect_split_regions[i], 'ref')
            word_hyp = self.align_pair(collect_split_regions[i], 'hyp')
            word_error_type_sequence = collect_split_regions[i].align
            collect_word_error_type_sequence.append(
                {
                    'word_ref': word_ref,
                    'word_hyp': word_hyp,
                    'eval': word_error_type_sequence,
                }
            )
            print('word_ref: ', word_ref)
            print('word_hyp: ', word_hyp)
            print('eval: ', word_error_type_sequence)

            # if aligner.phonetic_alignments[i]:
            #     phone_ref = aligner.phonetic_alignments[i].s1_tokens()
            #     phone_s1_map = aligner.phonetic_alignments[i].s1_map
            #     phone_hyp = aligner.phonetic_alignments[i].s2_tokens()
            #     phone_s2_map = aligner.phonetic_alignments[i].s2_map
            #     phone_align = aligner.phonetic_alignments[i].align
            #     collect_phone_error_type_sequence.append(
            #         {
            #             'phone_ref': phone_ref,
            #             'phone_s1_map': phone_s1_map,
            #             'phone_hyp': phone_hyp,
            #             'phone_s2_map': phone_s2_map,
            #             'phone_align': phone_align,
            #         }
            #     )
            # else:
            #     ref_phones = aligner.pronouncer.pronounce(ref_words)
            #     hyp_phones = aligner.pronouncer.pronounce(hyp_words)

            #     power_seg_alignment, phonetic_alignments[error_index] = PowerAligner.phoneAlignToWordAlign(ref_words, hyp_words, 
            #         ref_phones, hyp_phones)
            #     collect_phone_error_type_sequence.append(
            #         {
            #             'phone_ref': phone_ref,
            #             'phone_s1_map': phone_s1_map,
            #             'phone_hyp': phone_hyp,
            #             'phone_s2_map': phone_s2_map,
            #             'phone_align': phone_align,
            #         }
            #     )

if __name__ == '__main__':
    ref = 'HOWEVER SOME WRITE INTERESTING STORIES THAT APPEAL TO CHILDREN'
    hyp = 'HOWEVER SOME WRITE INTERESTING STORIES THAT APPEAL TO CHILDREN'

    # Create an instance of PowerCall
    power_call_instance = PowerCall()
    
    # Call the method on the instance
    power_call_instance.power_alignment_with_only_lexicon(ref, hyp)
