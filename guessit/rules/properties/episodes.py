#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
episode, season, episode_count, season_count and episode_details properties
"""
import copy
from collections import defaultdict

from rebulk import Rebulk, RemoveMatch, Rule, AppendMatch, RenameMatch
from rebulk.match import Matches
from rebulk.remodule import re
from rebulk.utils import is_iterable

from .title import TitleFromPosition
from ..common import dash, alt_dash, seps
from ..common.numeral import numeral, parse_numeral
from ..common.validators import seps_surround
from ...reutils import build_or_pattern


def episodes():
    """
    Builder for rebulk object.
    :return: Created Rebulk object
    :rtype: Rebulk
    """
    # pylint: disable=too-many-branches,too-many-statements
    rebulk = Rebulk()
    rebulk.regex_defaults(flags=re.IGNORECASE).string_defaults(ignore_case=True)
    rebulk.defaults(private_names=['episodeSeparator', 'seasonSeparator'])

    def season_episode_conflict_solver(match, other):
        """
        Conflict solver for episode/season patterns

        :param match:
        :param other:
        :return:
        """
        if match.name in ['season', 'episode'] and other.name in ['screen_size', 'video_codec',
                                                                  'audio_codec', 'audio_channels',
                                                                  'container', 'date']:
            return match
        elif match.name in ['season', 'episode'] and other.name in ['season', 'episode'] \
                and match.initiator != other.initiator:
            if 'weak-episode' in match.tags:
                return match
            if 'weak-episode' in other.tags:
                return other
            if 'x' in match.initiator.raw.lower():
                return match
            if 'x' in other.initiator.raw.lower():
                return other
        return '__default__'

    season_episode_seps = []
    season_episode_seps.extend(seps)
    season_episode_seps.extend(['x', 'X', 'e', 'E'])

    def season_episode_validator(match):
        """
        Validator for season/episode matches
        """
        if match.name in ['season', 'episode'] and match.initiator.start:
            return match.initiator.input_string[match.initiator.start] in season_episode_seps \
                   or match.initiator.input_string[match.initiator.start - 1] in season_episode_seps
        return True

    # 01x02, 01x02x03x04
    rebulk.chain(formatter={'season': int, 'episode': int},
                 tags=['SxxExx'],
                 abbreviations=[alt_dash],
                 children=True,
                 private_parent=True,
                 conflict_solver=season_episode_conflict_solver) \
        .defaults(validator=season_episode_validator) \
        .regex(r'S(?P<season>\d+)@?(?:xE|Ex|EP|E|x)@?(?P<episode>\d+)') \
        .regex(r'(?:(?P<episodeSeparator>xE|Ex|EP|E|x|-|\+|&)(?P<episode>\d+))').repeater('*') \
        .chain() \
        .regex(r'(?P<season>\d+)@?x@?(?P<episode>\d+)') \
        .regex(r'(?:(?P<episodeSeparator>x|-|\+|&)(?P<episode>\d+))').repeater('*') \
        .chain() \
        .regex(r'S(?P<season>\d+)') \
        .regex(r'(?:(?P<seasonSeparator>S|-|\+|&)(?P<season>\d+))').repeater('*')

    # episode_details property
    for episode_detail in ('Special', 'Bonus', 'Omake', 'Ova', 'Oav', 'Pilot', 'Unaired'):
        rebulk.string(episode_detail, value=episode_detail, name='episode_details')
    rebulk.regex(r'Extras?', name='episode_details', value='Extras')

    rebulk.defaults(private_names=['episodeSeparator', 'seasonSeparator'],
                    validate_all=True, validator={'__parent__': seps_surround}, children=True, private_parent=True)

    season_words = ['season', 'saison', 'serie', 'seasons', 'saisons', 'series']
    episode_words = ['episode', 'episodes', 'ep']
    of_words = ['of', 'sur']
    all_words = ['All']
    range_separators = ['-', 'to', 'a']
    discrete_separators = [r'\+', '&', '@', 'and', 'et']

    def seasons_ordering_validator(match):
        """
        Validator for season list. They should be in natural order to be validated.
        """
        if not seps_surround(match):
            return False
        values = Matches(match.children).to_dict(implicit=True)
        if 'season' in values and is_iterable(values['season']):
            # Season numbers must be in natural order to be validated.
            return list(sorted(values['season'])) == values['season']
        return True

    rebulk.chain(abbreviations=[alt_dash], formatter={'season': parse_numeral, 'count': parse_numeral},
                 validator={'__parent__': seasons_ordering_validator}) \
        .defaults(validator=None) \
        .regex(build_or_pattern(season_words) + '@?(?P<season>' + numeral + ')') \
        .regex(r'' + build_or_pattern(of_words) + '@?(?P<count>' + numeral + ')').repeater('?') \
        .regex(r'@?(?P<seasonSeparator>' + build_or_pattern(range_separators + discrete_separators) +
               r')@?(?P<season>\d+)').repeater('*')

    rebulk.regex(build_or_pattern(episode_words) + r'-?(?P<episode>\d+)' +
                 r'(?:v(?P<version>\d+))?' +
                 r'(?:-?' + build_or_pattern(of_words) + r'?-?(?P<count>\d+))?',  # Episode 4
                 abbreviations=[dash], formatter=int,
                 disabled=lambda context: context.get('type') == 'episode')

    rebulk.regex(build_or_pattern(episode_words) + r'-?(?P<episode>' + numeral + ')' +
                 r'(?:v(?P<version>\d+))?' +
                 r'(?:-?' + build_or_pattern(of_words) + r'?-?(?P<count>\d+))?',  # Episode 4
                 abbreviations=[dash], formatter={'episode': parse_numeral, 'version': int, 'count': int},
                 disabled=lambda context: context.get('type') != 'episode')

    rebulk.regex(r'S?(?P<season>\d+)-?(?:xE|Ex|E|x)-?(?P<other>' + build_or_pattern(all_words) + ')',
                 tags=['SxxExx'],
                 abbreviations=[dash],
                 validator=None,
                 formatter={'season': int, 'other': lambda match: 'Complete'})

    rebulk.defaults(private_names=['episodeSeparator', 'seasonSeparator'], validate_all=True,
                    validator={'__parent__': seps_surround}, children=True, private_parent=True)

    # 12, 13
    rebulk.chain(tags=['bonus-conflict', 'weak-movie', 'weak-episode'], formatter={'episode': int, 'version': int}) \
        .defaults(validator=None) \
        .regex(r'(?P<episode>\d{2})') \
        .regex(r'v(?P<version>\d+)').repeater('?') \
        .regex(r'(?P<episodeSeparator>[x-])(?P<episode>\d{2})').repeater('*')

    # 012, 013
    rebulk.chain(tags=['bonus-conflict', 'weak-movie', 'weak-episode'], formatter={'episode': int, 'version': int}) \
        .defaults(validator=None) \
        .regex(r'0(?P<episode>\d{1,2})') \
        .regex(r'v(?P<version>\d+)').repeater('?') \
        .regex(r'(?P<episodeSeparator>[x-])0(?P<episode>\d{1,2})').repeater('*')

    # 112, 113
    rebulk.chain(tags=['bonus-conflict', 'weak-movie', 'weak-episode'], formatter={'episode': int, 'version': int},
                 disabled=lambda context: not context.get('episode_prefer_number', False)) \
        .defaults(validator=None) \
        .regex(r'(?P<episode>\d{3,4})') \
        .regex(r'v(?P<version>\d+)').repeater('?') \
        .regex(r'(?P<episodeSeparator>[x-])(?P<episode>\d{3,4})').repeater('*')

    # 1, 2, 3
    rebulk.chain(tags=['bonus-conflict', 'weak-movie', 'weak-episode'], formatter={'episode': int, 'version': int},
                 disabled=lambda context: context.get('type') != 'episode') \
        .defaults(validator=None) \
        .regex(r'(?P<episode>\d)') \
        .regex(r'v(?P<version>\d+)').repeater('?') \
        .regex(r'(?P<episodeSeparator>[x-])(?P<episode>\d{1,2})').repeater('*')

    # e112, e113
    # TODO: Enhance rebulk for validator to be used globally (season_episode_validator)
    rebulk.chain(formatter={'episode': int, 'version': int}) \
        .defaults(validator=None) \
        .regex(r'e(?P<episode>\d{1,4})') \
        .regex(r'v(?P<version>\d+)').repeater('?') \
        .regex(r'(?P<episodeSeparator>e|x|-)(?P<episode>\d{1,4})').repeater('*')

    # ep 112, ep113, ep112, ep113
    rebulk.chain(abbreviations=[dash], formatter={'episode': int, 'version': int}) \
        .defaults(validator=None) \
        .regex(r'ep-?(?P<episode>\d{1,4})') \
        .regex(r'v(?P<version>\d+)').repeater('?') \
        .regex(r'(?P<episodeSeparator>ep|e|x|-)(?P<episode>\d{1,4})').repeater('*')

    # 102, 0102
    rebulk.chain(tags=['bonus-conflict', 'weak-movie', 'weak-episode', 'weak-duplicate'],
                 formatter={'season': int, 'episode': int, 'version': int},
                 conflict_solver=lambda match, other: match if other.name == 'year' else '__default__',
                 disabled=lambda context: context.get('episode_prefer_number', False)) \
        .defaults(validator=None) \
        .regex(r'(?P<season>\d{1,2})(?P<episode>\d{2})') \
        .regex(r'v(?P<version>\d+)').repeater('?') \
        .regex(r'(?P<episodeSeparator>x|-)(?P<episode>\d{2})').repeater('*')

    rebulk.regex(r'v(?P<version>\d+)', children=True, private_parent=True, formatter=int)

    rebulk.defaults(private_names=['episodeSeparator', 'seasonSeparator'])

    # TODO: List of words
    # detached of X count (season/episode)
    rebulk.regex(r'(?P<episode>\d+)?-?' + build_or_pattern(of_words) +
                 r'-?(?P<count>\d+)-?' + build_or_pattern(episode_words) + '?',
                 abbreviations=[dash], children=True, private_parent=True, formatter=int)

    rebulk.regex(r'Minisodes?', name='episode_format', value="Minisode")

    # Harcoded movie to disable weak season/episodes
    rebulk.regex('OSS-?117',
                 abbreviations=[dash], name="hardcoded-movies", marker=True,
                 conflict_solver=lambda match, other: None)

    rebulk.rules(EpisodeNumberSeparatorRange(range_separators),
                 SeasonSeparatorRange(range_separators), RemoveWeakIfMovie, RemoveWeakIfSxxExx,
                 RemoveWeakDuplicate, EpisodeDetailValidator, RemoveDetachedEpisodeNumber, VersionValidator,
                 CountValidator, EpisodeSingleDigitValidator)

    return rebulk


class CountValidator(Rule):
    """
    Validate count property and rename it
    """
    priority = 64
    consequence = [RemoveMatch, RenameMatch('episode_count'), RenameMatch('season_count')]

    properties = {'episode_count': [None], 'season_count': [None]}

    def when(self, matches, context):
        to_remove = []
        episode_count = []
        season_count = []

        for count in matches.named('count'):
            previous = matches.previous(count, lambda match: match.name in ['episode', 'season'], 0)
            if previous:
                if previous.name == 'episode':
                    episode_count.append(count)
                elif previous.name == 'season':
                    season_count.append(count)
            else:
                to_remove.append(count)
        return to_remove, episode_count, season_count


class EpisodeNumberSeparatorRange(Rule):
    """
    Remove separator matches and create matches for episoderNumber range.
    """
    priority = 128
    consequence = [RemoveMatch, AppendMatch]

    def __init__(self, season_from_to_separators):
        super(EpisodeNumberSeparatorRange, self).__init__()
        self.season_from_to_separators = season_from_to_separators

    def when(self, matches, context):
        to_remove = []
        to_append = []
        for separator in matches.named('episodeSeparator'):
            previous_match = matches.previous(separator, lambda match: match.name == 'episode', 0)
            next_match = matches.next(separator, lambda match: match.name == 'episode', 0)

            if previous_match and next_match and separator.value in self.season_from_to_separators:
                for episode_number in range(previous_match.value + 1, next_match.value):
                    match = copy.copy(separator)
                    match.private = False
                    match.name = 'episode'
                    match.value = episode_number
                    to_append.append(match)
            to_remove.append(separator)
        return to_remove, to_append


class SeasonSeparatorRange(Rule):
    """
    Remove separator matches and create matches for season range.
    """
    priority = 128
    consequence = [RemoveMatch, AppendMatch]

    def __init__(self, season_from_to_separators):
        super(SeasonSeparatorRange, self).__init__()
        self.season_from_to_separators = season_from_to_separators

    def when(self, matches, context):
        to_remove = []
        to_append = []
        for separator in matches.named('seasonSeparator'):
            previous_match = matches.previous(separator, lambda match: match.name == 'season', 0)
            next_match = matches.next(separator, lambda match: match.name == 'season', 0)

            if previous_match and next_match and separator.value in self.season_from_to_separators:
                for episode_number in range(previous_match.value + 1, next_match.value):
                    match = copy.copy(separator)
                    match.private = False
                    match.name = 'season'
                    match.value = episode_number
                    to_append.append(match)
            to_remove.append(separator)
        return to_remove, to_append


class RemoveWeakIfMovie(Rule):
    """
    Remove weak-movie tagged matches if it seems to be a movie.
    """
    priority = 64
    consequence = RemoveMatch

    def when(self, matches, context):
        if matches.named('year') or matches.markers.named('hardcoded-movies'):
            return matches.tagged('weak-movie')


class RemoveWeakIfSxxExx(Rule):
    """
    Remove weak-movie tagged matches if SxxExx pattern is matched.
    """
    priority = 64
    consequence = RemoveMatch

    def when(self, matches, context):
        if matches.tagged('SxxExx', lambda match: not match.private):
            return matches.tagged('weak-movie')


class RemoveWeakDuplicate(Rule):
    """
    Remove weak-duplicate tagged matches if duplicate patterns, for example The 100.109
    """
    priority = 64
    consequence = RemoveMatch

    def when(self, matches, context):
        to_remove = []
        for filepart in matches.markers.named('path'):
            patterns = defaultdict(list)
            for match in reversed(matches.range(filepart.start, filepart.end,
                                                predicate=lambda match: 'weak-duplicate' in match.tags)):
                if match.pattern in patterns[match.name]:
                    to_remove.append(match)
                else:
                    patterns[match.name].append(match.pattern)
        return to_remove


class EpisodeDetailValidator(Rule):
    """
    Validate episode_details if they are detached or next to season or episode.
    """
    priority = 64
    consequence = RemoveMatch

    def when(self, matches, context):
        ret = []
        for detail in matches.named('episode_details'):
            if not seps_surround(detail) \
                    and not matches.previous(detail, lambda match: match.name in ['season', 'episode']) \
                    and not matches.next(detail, lambda match: match.name in ['season', 'episode']):
                ret.append(detail)
        return ret


class RemoveDetachedEpisodeNumber(Rule):
    """
    If multiple episode are found, remove those that are not detached from a range and less than 10.

    Fairy Tail 2 - 16-20, 2 should be removed.
    """
    priority = 64
    consequence = RemoveMatch
    dependency = [RemoveWeakIfSxxExx, RemoveWeakDuplicate]

    def when(self, matches, context):
        ret = []

        episode_numbers = []
        episode_values = set()
        for match in matches.named('episode', lambda match: not match.private and 'weak-movie' in match.tags):
            if match.value not in episode_values:
                episode_numbers.append(match)
                episode_values.add(match.value)

        episode_numbers = list(sorted(episode_numbers, key=lambda match: match.value))
        if len(episode_numbers) > 1 and \
                        episode_numbers[0].value < 10 and \
                                episode_numbers[1].value - episode_numbers[0].value != 1:
            parent = episode_numbers[0]
            while parent:  # TODO: Add a feature in rebulk to avoid this ...
                ret.append(parent)
                parent = parent.parent
        return ret


class VersionValidator(Rule):
    """
    Validate version if previous match is episode or if surrounded by separators.
    """
    priority = 64
    dependency = [RemoveWeakIfMovie, RemoveWeakIfSxxExx]
    consequence = RemoveMatch

    def when(self, matches, context):
        ret = []
        for version in matches.named('version'):
            episode_number = matches.previous(version, lambda match: match.name == 'episode', 0)
            if not episode_number and not seps_surround(version.initiator):
                ret.append(version)
        return ret


class EpisodeSingleDigitValidator(Rule):
    """
    Remove single digit episode when inside a group that doesn't own title.
    """
    dependency = [TitleFromPosition]

    consequence = RemoveMatch

    def when(self, matches, context):
        ret = []
        for episode in matches.named('episode', lambda match: len(match.initiator) == 1):
            group = matches.markers.at_match(episode, lambda marker: marker.name == 'group', index=0)
            if group:
                if not matches.range(*group.span, predicate=lambda match: match.name == 'title'):
                    ret.append(episode)
        return ret
