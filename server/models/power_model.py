import re
import copy
import json
from power.aligner import PowerAligner
from power.levenshtein import ExpandedAlignment

class PowerCall:

    def __init__(self):
        # lexicon = "lex/cmudict.0.7a.json"
        # lexicon = "lex/cmudict.rep.json"
        self.lexicon = "lex/lexicon.withoutstress.json"
        self.lexicon_with_stress = self.read_lexicon("lex/lexicon.withstress.json")
        self.blank = '<blank>'
        self.filler = 'yan'
        self.pipe = '|'

    def restore_stress(self, phoneme_sequence, word_sequence, leading_zeros):
        result = []
        word_index = 0
        phoneme_index = 0

        # Add leading <blank> tokens
        result.extend([self.blank] * leading_zeros)
        phoneme_index += leading_zeros

        while phoneme_index < len(phoneme_sequence):
            if phoneme_sequence[phoneme_index] == self.pipe:  # Word boundary
                result.append(self.pipe)
                phoneme_index += 1
                if word_index < len(word_sequence):
                    word = word_sequence[word_index]
                    word_index += 1
            else:
                # Ensure the `word` variable is valid before entering the `else` section
                if word_index > 0:
                    word = word_sequence[word_index - 1]
                else:
                    raise ValueError("Mismatch between phoneme sequence and word sequence. Ensure proper word boundaries.")

                # Get the corresponding lexicon for the current word
                stress_phonemes = self.lexicon_with_stress[word.lower()]

                # Match phonemes to add stress tags
                for stress_phoneme in stress_phonemes:
                    while phoneme_index < len(phoneme_sequence) and phoneme_sequence[phoneme_index] in [self.blank, self.pipe]:
                        result.append(phoneme_sequence[phoneme_index])
                        phoneme_index += 1
                    if phoneme_index < len(phoneme_sequence) and stress_phoneme.startswith(phoneme_sequence[phoneme_index]):
                        result.append(stress_phoneme)
                        phoneme_index += 1

        return result

    def read_lexicon(self, lexicon_file_path):

        with open(lexicon_file_path, 'r') as f:
            return json.load(f)

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
            if item == self.pipe:
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

    def split_items_between_pipes(self, lst):
        # Initialize a list to store the result
        collected_phones = []
        current_group = []

        # Iterate through the phones list
        for phone in lst:
            if phone == self.pipe:
                if current_group:  # Save the collected phones if there's any
                    collected_phones.append(current_group)
                    current_group = []  # Reset for the next group
            else:
                current_group.append(phone)  # Collect phones between '|'

        # Print the result
        return collected_phones

    def merge_items_with_pipes(self, lst):
        collected_tokens = []
        collected_tokens.append(self.pipe)
        for group in lst:
            collected_tokens.extend(group)
            collected_tokens.append(self.pipe)
        return collected_tokens

    def remove_leading_blanks(self, lst):
        # Find the first non-empty element's index
        for i, item in enumerate(lst):
            if item != '':
                return lst[i:]  # Return the list starting from the first non-empty element
        return []  # Return an empty list if all elements are empty

    def select_better_word_result(self, word_seq_1, word_seq_2):
        word_seq_1 = [w for w in word_seq_1 if w]
        word_seq_2 = [w for w in word_seq_2 if w]
        if len(word_seq_1) > len(word_seq_2):
            return word_seq_1
        elif len(word_seq_1) < len(word_seq_2):
            return word_seq_2
        else:
            return word_seq_1

    def power_alignment_with_phone_sequence(self, ref, hyp, phone_object, addback_stress=False):

        aligner = PowerAligner(ref, hyp, lowercase=True, lexicon=self.lexicon)
        aligner_collect = aligner.align()

        new_aligner_collect = {}

        collect_split_regions = aligner.split_regions_before_merge

        for overall_i, info in aligner_collect.items():

            """
            {
                'word_ref': word_ref,
                'word_hyp': word_hyp,
                'ref_phones': ref_phones,
                'hyp_phones': hyp_phones,
                'word_align': None,
                'phone_align': None,
            }
            """
            # word level
            word_ref = self.select_better_word_result(self.align_pair(collect_split_regions[overall_i], 'ref'), collect_split_regions[overall_i].s1_tokens())
            word_hyp = self.select_better_word_result(self.align_pair(collect_split_regions[overall_i], 'hyp'), collect_split_regions[overall_i].s2_tokens())
            # word_s1_map = collect_split_regions[overall_i].s1_map
            # word_s2_map = collect_split_regions[overall_i].s2_map
            word_eval = collect_split_regions[overall_i].align

            word_ref = [w if w else self.filler for w in word_ref]
            word_hyp = [w if w else self.filler for w in word_hyp]

            fixed_word_ref = []
            fixed_word_hyp = []
            iter_word_ref = iter(word_ref)
            iter_word_hyp = iter(word_hyp)
            for e in word_eval:
                if e == 'C':
                    fixed_word_ref.append(next(iter_word_ref))
                    fixed_word_hyp.append(next(iter_word_hyp))
                elif e == 'S':
                    fixed_word_ref.append(next(iter_word_ref))
                    fixed_word_hyp.append(next(iter_word_hyp))
                elif e == 'I':
                    # fixed_word_ref.append(self.blank)
                    fixed_word_ref.append(self.filler)
                    fixed_word_hyp.append(next(iter_word_hyp))
                elif e == 'D':
                    fixed_word_ref.append(next(iter_word_ref))
                    # fixed_word_hyp.append(self.blank)
                    fixed_word_hyp.append(self.filler)

            word_ref = fixed_word_ref
            word_hyp = fixed_word_hyp

            info['word_ref'] = word_ref
            info['word_hyp'] = word_hyp
            info['word_align'] = {
                # 'word_s1_map': word_s1_map,
                # 'word_s2_map': word_s2_map,
                'word_eval': word_eval,
            }

            print('word_ref: ', word_ref)
            print('word_hyp: ', word_hyp)

            # phone level
            if info['phone_align'] is not None:
                print('if info[phone_align] is not None:')
                phone_ref = aligner.phonetic_alignments[overall_i].s1_tokens()
                phone_s1_map = aligner.phonetic_alignments[overall_i].s1_map
                phone_hyp = aligner.phonetic_alignments[overall_i].s2_tokens()
                phone_s2_map = aligner.phonetic_alignments[overall_i].s2_map
                phone_eval = aligner.phonetic_alignments[overall_i].align

                # fix the empty phone_s1_map
                if not phone_s1_map:
                    # the first token of phone_ref and phone_hyp should be '|', that is, 'C' as the eval result
                    s1_map_start_index = [i for i , t in enumerate(phone_eval) if t == 'C'][0]
                    phone_s1_map = [i + s1_map_start_index for i , t in enumerate(phone_eval[s1_map_start_index:]) if t != 'I']
                    phone_s1_map.append(phone_s1_map[-1]+1)

                fixed_phone_ref = []
                fixed_phone_hyp = []
                iter_phone_ref = iter(phone_ref)
                iter_phone_hyp = iter(phone_hyp)
                for e in phone_eval:
                    if e == 'C':
                        fixed_phone_ref.append(next(iter_phone_ref))
                        fixed_phone_hyp.append(next(iter_phone_hyp))
                    elif e == 'S':
                        fixed_phone_ref.append(next(iter_phone_ref))
                        fixed_phone_hyp.append(next(iter_phone_hyp))
                    elif e == 'I':
                        fixed_phone_ref.append(self.blank)
                        fixed_phone_hyp.append(next(iter_phone_hyp))
                    elif e == 'D':
                        fixed_phone_ref.append(next(iter_phone_ref))
                        fixed_phone_hyp.append(self.blank)
                phone_ref = fixed_phone_ref
                phone_hyp = fixed_phone_hyp

                # fix the last missing '|'
                add_eval = False

                # if phone_s1_map or phone_s2_map is empty
                def append_next(lst):
                    if lst:
                        lst.append(phone_s1_map[-1]+1)
                    else:
                        lst = [0]
                    return lst

                if len(phone_ref) > len(phone_hyp):
                    if self.pipe != phone_ref[-1] and self.pipe == phone_hyp[-1]:
                        phone_ref.append(self.pipe)
                        phone_s1_map = append_next(phone_s1_map)
                        add_eval = True
                    elif self.pipe != phone_ref[-1] and self.pipe != phone_hyp[-1]:
                        phone_ref.append(self.pipe)
                        phone_hyp.append(self.pipe)
                        phone_s1_map = append_next(phone_s1_map)
                        phone_s2_map = append_next(phone_s2_map)
                        add_eval = True
                elif len(phone_ref) < len(phone_hyp):
                    if self.pipe != phone_hyp[-1] and self.pipe == phone_ref[-1]:
                        phone_hyp.append(self.pipe)
                        phone_s2_map = append_next(phone_s2_map)
                        add_eval = True
                    if self.pipe != phone_hyp[-1] and self.pipe != phone_ref[-1]:
                        phone_ref.append(self.pipe)
                        phone_hyp.append(self.pipe)
                        phone_s1_map = append_next(phone_s1_map)
                        phone_s2_map = append_next(phone_s2_map)
                        add_eval = True
                else:
                    if self.pipe != phone_ref[-1]:
                        phone_ref.append(self.pipe)
                        phone_hyp.append(self.pipe)
                        phone_s1_map = append_next(phone_s1_map)
                        phone_s2_map = append_next(phone_s2_map)
                    add_eval = True

                if add_eval:
                    phone_eval.append('C')

                assert ((len(phone_eval) == len(phone_ref)) | (len(phone_eval) == len(phone_hyp)))

                # post-process
                new_phone_ref = []
                new_phone_hyp = []
                for i, (t1, t2) in enumerate(zip(phone_ref, phone_hyp)):
                    if i == 0:
                        if (t1 == self.pipe and t2 == self.blank):
                            new_phone_ref.append(t1)
                            new_phone_hyp.append(self.pipe)
                        elif (t2 == self.pipe and t1 == self.blank):
                            new_phone_ref.append(self.pipe)
                            new_phone_hyp.append(t2)
                        else:
                            new_phone_ref.append(t1)
                            new_phone_hyp.append(t2)
                    else:
                        new_phone_ref.append(t1)
                        new_phone_hyp.append(t2)

                # update words
                for i, (t1, t2) in enumerate(zip(new_phone_ref, new_phone_hyp)):
                    if i > 0:
                        # validate for index != 0, using word count comparison
                        test_aa = len(' '.join(word_ref).split())
                        test_bb = len(' '.join(word_hyp).split())
                        test_a = len(self.count_items_between_pipes(new_phone_ref))
                        test_b = len(self.count_items_between_pipes(new_phone_hyp))
                        if test_aa != test_a:
                            if self.filler in word_ref:
                                filler_indexes = [wi for wi, w in enumerate(word_ref) if w == self.filler]
                                filler_indexes.reverse()
                                for i_filler_index_idx in range(0, abs(test_aa-test_a)):
                                    word_ref.pop(filler_indexes[i_filler_index_idx])
                                info['word_ref'] = word_ref
                        if test_bb != test_b:
                            if self.filler in word_hyp:
                                filler_indexes = [wi for wi, w in enumerate(word_hyp) if w == self.filler]
                                filler_indexes.reverse()
                                for i_filler_index_idx in range(0, abs(test_bb-test_b)):
                                    word_hyp.pop(filler_indexes[i_filler_index_idx])
                                info['word_hyp'] = word_hyp

                print('A')
                print(phone_ref, len(phone_ref))
                print(phone_hyp, len(phone_hyp))
                print(new_phone_ref)
                print(new_phone_hyp)

                info['phone_align'] = {
                    'phone_ref': new_phone_ref,
                    # 'phone_ref': phone_ref,
                    'phone_s1_map': phone_s1_map,
                    'phone_hyp': new_phone_hyp,
                    # 'phone_hyp': phone_hyp,
                    'phone_s2_map': phone_s2_map,
                    'phone_eval': phone_eval,
                }
            else:
                print('if info[phone_align] is None:')
                # they are almost the same two sequence
                # they should be the same length of sequences

                ref_phones = aligner.pronouncer.pronounce(word_ref)
                hyp_phones = aligner.pronouncer.pronounce(word_hyp)
                phone_s1_map = []
                phone_s2_map = []
                phone_eval = []
                str_ref_phones = ' '.join(ref_phones)
                str_hyp_phones = ' '.join(hyp_phones)

                new_phone_ref = []
                new_phone_hyp = []

                phone_pa = PowerAligner(str_ref_phones, str_hyp_phones, lowercase=True, lexicon=self.lexicon)
                phone_pa.align()
                phone_pa_region = phone_pa.split_regions_before_merge
                
                seg_phone_index = 0
                for ii in range(len(phone_pa_region)):
                    phone_seg_ref = self.align_pair(phone_pa_region[ii], 'ref')
                    phone_seg_hyp = self.align_pair(phone_pa_region[ii], 'hyp')
                    phone_seg_ref = [p if p else self.blank for p in phone_seg_ref]
                    phone_seg_hyp = [p if p else self.blank for p in phone_seg_hyp]
                    # Split each item in the lists by spaces
                    """
                        phone_seg_ref:  ['hh ae', 'v']                                                                                                                                                          
                        phone_seg_hyp:  ['t', 'uw']
                    """
                    phone_seg_ref = [seg for item in phone_seg_ref for seg in item.split()]
                    phone_seg_hyp = [seg for item in phone_seg_hyp for seg in item.split()]

                    phone_seg_s1_map = phone_pa_region[ii].s1_map
                    phone_seg_s2_map = phone_pa_region[ii].s2_map
                    phone_seg_eval = phone_pa_region[ii].align

                    # print('phone_seg_ref.b: ', phone_seg_ref)
                    # print('phone_seg_hyp.b: ', phone_seg_hyp)
                    # print('phone_seg_eval.b: ', phone_seg_eval)

                    # Adjust the length of phone_seg_hyp to match phone_seg_ref by inserting empty strings
                    tmp_append_num = 0
                    if len(phone_seg_ref) > len(phone_seg_hyp):
                        phone_seg_hyp = [self.blank] * (len(phone_seg_ref) - len(phone_seg_hyp)) + phone_seg_hyp
                        phone_seg_eval = ['D'] * (len(phone_seg_ref) - len(phone_seg_hyp)) + phone_seg_eval
                        tmp_append_num = len(phone_seg_ref) - len(phone_seg_hyp)
                        phone_seg_s1_map = [i + tmp_append_num for i in phone_seg_s1_map]
                        phone_seg_s1_map = list(range(min(phone_seg_s1_map) - tmp_append_num, min(phone_seg_s1_map), 1)) + phone_seg_s1_map
                    if len(phone_seg_ref) < len(phone_seg_hyp):
                        phone_seg_ref = [self.blank] * (len(phone_seg_hyp) - len(phone_seg_ref)) + phone_seg_ref
                        phone_seg_eval = ['I'] * (len(phone_seg_hyp) - len(phone_seg_ref)) + phone_seg_eval
                        tmp_append_num = len(phone_seg_ref) - len(phone_seg_hyp)
                        phone_seg_s1_map = [i + tmp_append_num for i in phone_seg_s1_map]
                        phone_seg_s1_map = list(range(min(phone_seg_s1_map) - tmp_append_num, min(phone_seg_s1_map), 1)) + phone_seg_s1_map

                    # print('phone_seg_ref.a: ', phone_seg_ref)
                    # print('phone_seg_hyp.a: ', phone_seg_hyp)
                    # print('phone_seg_eval.a: ', phone_seg_eval)

                    phone_seg_s1_map = [i + seg_phone_index for i in phone_seg_s1_map]
                    phone_seg_s2_map = [i + seg_phone_index for i in phone_seg_s2_map]
                    phone_s1_map.extend(phone_seg_s1_map)
                    phone_s2_map.extend(phone_seg_s2_map)
                    phone_eval.extend(phone_seg_eval)
                    new_phone_ref.extend(phone_seg_ref)
                    new_phone_hyp.extend(phone_seg_hyp)

                    seg_phone_index += len(phone_seg_eval)

                # post-process
                new_new_phone_ref = []
                new_new_phone_hyp = []
                for i, (t1, t2) in enumerate(zip(new_phone_ref, new_phone_hyp)):
                    if i == 0:
                        if (t1 == self.pipe and t2 == self.blank):
                            new_new_phone_ref.append(t1)
                            new_new_phone_hyp.append(self.pipe)
                        elif (t2 == self.pipe and t1 == self.blank):
                            new_new_phone_ref.append(self.pipe)
                            new_new_phone_hyp.append(t2)
                        else:
                            new_new_phone_ref.append(t1)
                            new_new_phone_hyp.append(t2)
                    else:
                        new_new_phone_ref.append(t1)
                        new_new_phone_hyp.append(t2)

                print('B')
                print(phone_ref, len(phone_ref))
                print(phone_hyp, len(phone_hyp))
                print(new_new_phone_ref)
                print(new_new_phone_hyp)

                info['phone_align'] = {
                    'phone_ref': new_new_phone_ref,
                    'phone_s1_map': phone_s1_map,
                    'phone_hyp': new_new_phone_hyp,
                    'phone_s2_map': phone_s2_map,
                    'phone_eval': phone_eval,
                }

            new_aligner_collect[overall_i] = info

        # merge
        del aligner_collect
        # assert len(new_aligner_collect) < 1
        if len(new_aligner_collect) == 1:
            aligner_collect = new_aligner_collect[0]
            print('if len(new_aligner_collect) == 1:')
            # print(aligner_collect['word_ref'])
            # print(aligner_collect['ref_phones'])
            # print(aligner_collect['word_hyp'])
            # print(aligner_collect['hyp_phones'])
            # print(self.count_items_between_pipes(aligner_collect['ref_phones']))
            # print(self.count_items_between_pipes(aligner_collect['hyp_phones']))

            # # post-process
            # new_phone_ref = []
            # new_phone_hyp = []
            # for i, (t1, t2) in enumerate(zip(aligner_collect['phone_align']['phone_ref'], aligner_collect['phone_align']['phone_hyp'])):
            #     if i == 0:
            #         if (t1 == self.pipe and t2 == self.blank):
            #             new_phone_ref.append(t1)
            #             new_phone_hyp.append(self.pipe)
            #         elif (t2 == self.pipe and t1 == self.blank):
            #             new_phone_ref.append(self.pipe)
            #             new_phone_hyp.append(t2)
            #         else:
            #             new_phone_ref.append(t1)
            #             new_phone_hyp.append(t2)
            #     else:
            #         new_phone_ref.append(t1)
            #         new_phone_hyp.append(t2)
            #     # else:
            #     #     if (t1 == self.pipe and t2 == self.blank):
            #     #         new_phone_ref.append(t1)
            #     #         new_phone_hyp.append(self.pipe)
            #     #     elif (t2 == self.pipe and t1 == self.blank):
            #     #         new_phone_ref.append(self.pipe)
            #     #         new_phone_hyp.append(t2)
            #     #     else:
            #     #         new_phone_ref.append(t1)
            #     #         new_phone_hyp.append(t2)

            new_aligner_collect = {
                'ref_phones_by_word': self.split_items_between_pipes(new_phone_ref),
                'hyp_phones_by_word': self.split_items_between_pipes(new_phone_hyp),
                'segment_ref_hyp_word_count_align': {
                    'ref_phones': new_phone_ref,
                    'hyp_phones': new_phone_hyp,
                    's1_leading_blank_count': 0,
                    's2_leading_blank_count': 0,
                    's1_leading_blank_count_word': 0,
                    's2_leading_blank_count_word': 0,
                    'phone_ref_position': self.count_items_between_pipes(new_phone_ref),
                    'phone_hyp_position': self.count_items_between_pipes(new_phone_hyp),
                    'word_ref': ' '.join(aligner_collect['word_ref']).split(),
                    'word_hyp': ' '.join(aligner_collect['word_hyp']).split(),
                },
                'word_align': {
                    # 'word_s1_map': aligner_collect['word_align']['word_s1_map'],
                    # 'word_s2_map': aligner_collect['word_align']['word_s2_map'],
                    'word_eval': aligner_collect['word_align']['word_eval'],
                },
                'phone_align': {
                    'phone_s1_map': aligner_collect['phone_align']['phone_s1_map'],
                    'phone_s2_map': aligner_collect['phone_align']['phone_s2_map'],
                    'phone_eval': aligner_collect['phone_align']['phone_eval']
                }
            }

        else:
            print('if len(new_aligner_collect) > 1:')
            new_aligner_collect = dict(sorted(new_aligner_collect.items())) # key ascending sort

            # Combine the segments
            combined = {
                'ref_phones_by_word': [],
                'hyp_phones_by_word': [],
                'segment_ref_hyp_word_count_align': {},
                'word_align': {
                    # 'word_s1_map': [],
                    # 'word_s2_map': [],
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
            new_phone_ref = []
            new_phone_hyp = []
            collect_word_ref = []
            collect_word_hyp = []

            # Process each segment in order
            for key, segment in new_aligner_collect.items():
                # Concatenate word_hyp
                collect_word_ref.extend(segment['word_ref'])
                collect_word_hyp.extend(segment['word_hyp'])
                
                # Update word_align
                # combined['word_align']['word_s1_map'].extend([i + word_index for i in segment['word_align']['word_s1_map']])
                # combined['word_align']['word_s2_map'].extend([i + word_index for i in segment['word_align']['word_s2_map']])
                combined['word_align']['word_eval'].extend(segment['word_align']['word_eval'])
                
                # Concatenate hyp_phones and skip leading '|'
                hyp_phones = segment['phone_align']['phone_hyp']
                ref_phones = segment['phone_align']['phone_ref']

                phone_s1_map = segment['phone_align']['phone_s1_map']
                phone_s2_map = segment['phone_align']['phone_s2_map']
                phone_eval = segment['phone_align']['phone_eval']

                # print(hyp_phones)
                # print(ref_phones)
                # print(phone_s1_map)
                # print(phone_s2_map)
                # print(phone_eval)

                # under multiple segment, not the first one segemnt needs to be remove the '|'
                if hyp_phones[0] == '|' and key != 0:
                    hyp_phones = hyp_phones[1:] # Remove initial '|'
                    ref_phones = ref_phones[1:]
                    phone_s1_map = phone_s1_map[1:]
                    phone_s2_map = phone_s2_map[1:]
                    phone_eval = phone_eval[1:]
                    phone_s1_map = [i - 1 for i in phone_s1_map] # because we remove the leading character, we need to eliminate 1 to each of index
                    phone_s2_map = [i - 1 for i in phone_s2_map]

                # # TODO
                # for i, (t1, t2) in enumerate(zip(ref_phones, hyp_phones)):
                #     if i == 0:
                #         if (t1 == self.pipe and t2 == self.blank):
                #             new_phone_ref.append(t1)
                #             new_phone_hyp.append(self.pipe)
                #         elif (t2 == self.pipe and t1 == self.blank):
                #             new_phone_ref.append(self.pipe)
                #             new_phone_hyp.append(t2)
                #         else:
                #             new_phone_ref.append(t1)
                #             new_phone_hyp.append(t2)
                #     else:
                #         new_phone_ref.append(t1)
                #         new_phone_hyp.append(t2)

                # print('new_phone_ref:::: ', new_phone_ref)
                # print('new_phone_hyp:::: ', new_phone_hyp)

                    # if (t1 == self.pipe and t2 == self.blank):
                    #     new_phone_ref.append(t1)
                    #     new_phone_hyp.append(self.pipe)
                    # elif (t2 == self.pipe and t1 == self.blank):
                    #     new_phone_ref.append(self.pipe)
                    #     new_phone_hyp.append(t2)
                    # else:
                    #     new_phone_ref.append(t1)
                    #     new_phone_hyp.append(t2)
                new_phone_ref.extend(ref_phones)
                new_phone_hyp.extend(hyp_phones)

                combined['phone_align']['phone_s1_map'].extend([i + phone_index for i in phone_s1_map])
                combined['phone_align']['phone_s2_map'].extend([i + phone_index for i in phone_s2_map])
                combined['phone_align']['phone_eval'].extend(phone_eval)

                # Update indices
                word_index += len(segment['word_hyp'])
                phone_index += len(segment['hyp_phones']) - 1 if key > 0 else len(segment['hyp_phones']) # Subtracting one for skipped '|'

            # a = copy.deepcopy(new_phone_ref)
            # b = copy.deepcopy(new_phone_hyp)
            # print('debug.new_phone_ref: ', new_phone_ref)
            # print('debug.new_phone_hyp: ', new_phone_hyp)
            c = combined['phone_align']['phone_s1_map']
            d = combined['phone_align']['phone_s2_map']
            e = combined['phone_align']['phone_eval']
            # del new_phone_ref
            # del new_phone_hyp

            # new_phone_ref = []
            # new_phone_hyp = []
            # iter_a, iter_b = iter(a), iter(b)
            # print('a: ', a, len(a))
            # print('b: ', b, len(b))
            # print('c: ', c, len(c))
            # print('d: ', d)
            # print('e: ', e, len(e))

            # for i in range(0, len(e)):
            #     # print(i)
            #     new_phone_ref.append(next(iter_a, '') if i in c else '')
            #     new_phone_hyp.append(next(iter_b, '') if i in d else '')

            # print('debug.A.new_phone_ref: ', new_phone_ref)
            # print('debug.A.new_phone_hyp: ', new_phone_hyp)

            # leading blanks
            s1_leading_blank_count = c[0]
            s2_leading_blank_count = d[0]
            s1_leading_blank_count_word = 0
            s2_leading_blank_count_word = 0
            if any(i > 0 for i in [s1_leading_blank_count, s2_leading_blank_count]):
                if self.blank in new_phone_ref[0]:
                    number_word_space = new_phone_hyp[:s1_leading_blank_count].count('|')
                    s1_leading_blank_count_word = number_word_space
                    s2_leading_blank_count_word = 0
                elif self.blank in new_phone_hyp[0]:
                    number_word_space = new_phone_ref[:s2_leading_blank_count].count('|')
                    s1_leading_blank_count_word = 0
                    s2_leading_blank_count_word = number_word_space

            # print('new_phone_ref: ', new_phone_ref)
            phone_ref_position = self.count_items_between_pipes(new_phone_ref)
            phone_hyp_position = self.count_items_between_pipes(new_phone_hyp)

            # # fix interval count differ between phone_ref_position and phone_hyp_position
            # if any(i == 1 for i in [s1_leading_blank_count_word, s2_leading_blank_count_word]):
            #     tmp_p_c_ref = len(phone_ref_position)
            #     tmp_p_c_hyp = len(phone_hyp_position)
            #     if tmp_p_c_ref != tmp_p_c_hyp:
            #         if tmp_p_c_ref > tmp_p_c_hyp:
            #             tmp_p_c = tmp_p_c_ref - tmp_p_c_hyp
            #             tmp_first = phone_hyp_position[0] - tmp_p_c
            #             phone_hyp_position[0] = tmp_first
            #             phone_hyp_position.insert(0, s2_leading_blank_count_word)
            #         elif tmp_p_c_ref < tmp_p_c_hyp:
            #             tmp_p_c = tmp_p_c_hyp - tmp_p_c_ref
            #             tmp_first = phone_ref_position[0] - tmp_p_c
            #             phone_ref_position[0] = tmp_first
            #             phone_ref_position.insert(0, s1_leading_blank_count_word)

            # print('debug.B.new_phone_ref: ', new_phone_ref)
            # print('debug.B.new_phone_hyp: ', new_phone_hyp)

            a = copy.deepcopy(collect_word_ref)
            b = copy.deepcopy(collect_word_hyp)
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

            combined['ref_phones_by_word'] = self.split_items_between_pipes(new_phone_ref)
            combined['hyp_phones_by_word'] = self.split_items_between_pipes(new_phone_hyp)

            # print("ref_phones:", new_phone_ref)
            # print("hyp_phones:", new_phone_hyp)
            # print("s1_leading_blank_count:", s1_leading_blank_count)
            # print("s2_leading_blank_count:", s2_leading_blank_count)
            # print("phone_ref_position:", phone_ref_position)
            # print("phone_hyp_position:", phone_hyp_position)
            # print("word_ref:", new_word_ref)
            # print("word_hyp:", new_word_hyp)

            combined['segment_ref_hyp_word_count_align'] = {
                'ref_phones': new_phone_ref,
                'hyp_phones': new_phone_hyp,
                # 's1_leading_blank_count': s1_leading_blank_count,
                # 's2_leading_blank_count': s2_leading_blank_count,
                # 's1_leading_blank_count_word': s1_leading_blank_count_word,
                # 's2_leading_blank_count_word': s2_leading_blank_count_word,
                's1_leading_blank_count': 0,
                's2_leading_blank_count': 0,
                's1_leading_blank_count_word': 0,
                's2_leading_blank_count_word': 0,
                'phone_ref_position': phone_ref_position,
                'phone_hyp_position': phone_hyp_position,
                'word_ref': new_word_ref,
                'word_hyp': new_word_hyp,
            }

            new_aligner_collect = combined

        print("new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones']:", new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones']:", new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['s1_leading_blank_count']:", new_aligner_collect['segment_ref_hyp_word_count_align']['s1_leading_blank_count'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['s2_leading_blank_count']:", new_aligner_collect['segment_ref_hyp_word_count_align']['s2_leading_blank_count'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['s1_leading_blank_count_word']:", new_aligner_collect['segment_ref_hyp_word_count_align']['s1_leading_blank_count_word'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['s2_leading_blank_count_word']:", new_aligner_collect['segment_ref_hyp_word_count_align']['s2_leading_blank_count_word'])

        print("new_aligner_collect['segment_ref_hyp_word_count_align']['phone_ref_position']:", new_aligner_collect['segment_ref_hyp_word_count_align']['phone_ref_position'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['phone_hyp_position']:", new_aligner_collect['segment_ref_hyp_word_count_align']['phone_hyp_position'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['word_ref']:", new_aligner_collect['segment_ref_hyp_word_count_align']['word_ref'])
        print("new_aligner_collect['segment_ref_hyp_word_count_align']['word_hyp']:", new_aligner_collect['segment_ref_hyp_word_count_align']['word_hyp'])

        if addback_stress:

            # using word to find their phone sequence by the lexicon with stress
            # self.lexicon_with_stress
            
            # collect_before_stress_phone_seq = []
            # before_stress_phone_seq = new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones']

            # 1. word from reference
            phone_seq_aggregated_by_word = self.split_items_between_pipes(new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones'])
            new_ref_phones = []
            # Process each word and its corresponding phoneme sequence
            for word_i, word in enumerate(
                ' '.join(new_aligner_collect['segment_ref_hyp_word_count_align']['word_ref']).split()
            ):
                # Get the stress-tagged phoneme sequence for the word
                phone_seq_with_stress = self.lexicon_with_stress[word.lower()].split()
                new_word_p = []  # Store the new phoneme sequence with stress
                wos_p_i = 0  # Index for the stress-tagged phoneme sequence

                print(f'Processing word: {word}')
                print('phone_seq_aggregated_by_word[word_i]:', phone_seq_aggregated_by_word[word_i])
                print('phone_seq_with_stress:', phone_seq_with_stress)

                # Match each phoneme in the word's phoneme sequence
                for p in phone_seq_aggregated_by_word[word_i]:
                    print('Current phoneme:', p, '| Stress sequence index:', wos_p_i)

                    # Match phoneme with or without stress
                    if (
                        wos_p_i < len(phone_seq_with_stress) and
                        re.sub(r'[0-9]+', '', phone_seq_with_stress[wos_p_i]).lower() == p
                    ):
                        new_word_p.append(phone_seq_with_stress[wos_p_i])  # Add stress phoneme
                        wos_p_i += 1  # Move to the next stress phoneme
                    else:
                        new_word_p.append(p)  # Add as-is

                # Append the processed phoneme sequence for the word
                print('Processed phoneme sequence for the word:', new_word_p)
                new_ref_phones.append(new_word_p)

            print('Final processed phoneme sequence:', new_ref_phones)
            new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones'] = self.merge_items_with_pipes(new_ref_phones)

            # new_ref_phones = self.restore_stress(
            #     new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones'],
            #     new_aligner_collect['segment_ref_hyp_word_count_align']['word_ref'],
            #     new_aligner_collect['segment_ref_hyp_word_count_align']['s1_leading_blank_count'])
            # new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones'] = new_ref_phones # self.merge_items_with_pipes(new_ref_phones)

            # 2. word from hypothesis
            phone_seq_aggregated_by_word = self.split_items_between_pipes(
                    new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones']
                )
            
            # Initialize the result for hypothesis phonemes
            new_hyp_phones = []

            # Process each word and its corresponding phoneme sequence
            for word_i, word in enumerate(
                ' '.join(new_aligner_collect['segment_ref_hyp_word_count_align']['word_hyp']).split()
            ):
                # Get the stress-tagged phoneme sequence for the word
                phone_seq_with_stress = self.lexicon_with_stress[word.lower()].split()
                new_word_p = []  # Store the new phoneme sequence with stress
                wos_p_i = 0  # Index for the stress-tagged phoneme sequence

                print(f'Processing word: {word}')
                print('phone_seq_aggregated_by_word[word_i]:', phone_seq_aggregated_by_word[word_i])
                print('phone_seq_with_stress:', phone_seq_with_stress)

                # Match each phoneme in the word's phoneme sequence
                for p in phone_seq_aggregated_by_word[word_i]:
                    print('Current phoneme:', p, '| Stress sequence index:', wos_p_i)

                    # Match phoneme with or without stress
                    if (
                        wos_p_i < len(phone_seq_with_stress) and
                        re.sub(r'[0-9]+', '', phone_seq_with_stress[wos_p_i]).lower() == p
                    ):
                        new_word_p.append(phone_seq_with_stress[wos_p_i])  # Add stress phoneme
                        wos_p_i += 1  # Move to the next stress phoneme
                    else:
                        new_word_p.append(p)  # Add as-is

                # Append the processed phoneme sequence for the word
                print('Processed phoneme sequence for the word:', new_word_p)
                new_hyp_phones.append(new_word_p)

            print('Final processed hypothesis phoneme sequence:', new_hyp_phones)

            # Merge processed phoneme sequences with pipes
            new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones'] = self.merge_items_with_pipes(new_hyp_phones)
    
            # new_hyp_phones = self.restore_stress(
            #     new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones'],
            #     new_aligner_collect['segment_ref_hyp_word_count_align']['word_hyp'],
            #     new_aligner_collect['segment_ref_hyp_word_count_align']['s2_leading_blank_count'])
            # new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones'] = new_hyp_phones # self.split_items_between_pipes(new_hyp_phones)

            new_aligner_collect['ref_phones_by_word'] = self.split_items_between_pipes(new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones'])
            new_aligner_collect['hyp_phones_by_word'] = self.split_items_between_pipes(new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones'])
            # new_aligner_collect['ref_phones_by_word'] = self.split_items_between_pipes(new_aligner_collect['segment_ref_hyp_word_count_align']['ref_phones'])
            # new_aligner_collect['hyp_phones_by_word'] = self.split_items_between_pipes(new_aligner_collect['segment_ref_hyp_word_count_align']['hyp_phones'])

            # print("new_aligner_collect['hyp_phones_by_word']: ", new_aligner_collect['hyp_phones_by_word'])

        # decide to replace the asr decoded phone sequence or remain the original one
        # (recognized by word level then conversion to phone by lexicon)
        # phone_object

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
            #     ref_phones = aligner.pronouncer.pronounce(word_ref)
            #     hyp_phones = aligner.pronouncer.pronounce(word_hyp)

            #     power_seg_alignment, phonetic_alignments[error_index] = PowerAligner.phoneAlignToWordAlign(word_ref, word_hyp, 
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
