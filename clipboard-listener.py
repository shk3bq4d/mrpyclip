#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /* ex: set filetype=python ts=4 sw=4 expandtab: */

import datetime
import os
import sys
import re
import unittest
import argparse
import logging
from typing import Sequence, Union, Iterator, List, Tuple, no_type_check, Any, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from pprint import pprint, pformat

logger = logging.getLogger(__name__)

class ClipboardListenerTest(unittest.TestCase):
    #def __init__(self, methodName='runTest'): pass
    def tearDown(self) -> None: pass
    def setUp(self) -> None: pass

    @classmethod
    def setUpClass(cls) -> None: pass

    @classmethod
    def tearDownClass(cls) -> None: pass

    def test_queue_summary_alter(self) -> None:
        self.assertIn(   'a', 'abcde', msg='a is supposed to be in abcde')
        self.assertNotIn('z', 'abcde', msg='z is not supposed to be in abcde')
        self.assertNotEqual('expected', 'actual', msg='expected is first argument')
        # assertAlmostEqual assertAlmostEquals assertDictContainsSubset assertDictEqual
        # assertEqual assertEquals assertFalse assertGreater assertGreaterEqual
        # assertIn assertIs assertIsInstance assertIsNone assertIsNot assertIsNotNone
        # assertItemsEqual assertLess assertLessEqual assertListEqual assertMultiLineEqual
        # assertNotAlmostEqual assertNotAlmostEquals assertNotEqual assertNotEquals
        # assertNotIn assertNotIsInstance assertNotRegexpMatches assertRaises
        # assertRaisesRegexp assertRegexpMatches assertSequenceEqual assertSetEqual
        # assertTrue assertTupleEqual assert_ countTestCases debug defaultTestResult
        # doCleanups fail failIf failIfAlmostEqual failIfEqual failUnless failUnlessAlmostEqual
        # failUnlessEqual failUnlessRaises failureException id longMessage maxDiff
        # run setUp setUpClass shortDescription skipTest tearDown tearDownClass

def logging_conf(
        level='INFO', # DEBUG
        use='stdout', # "stdout syslog" "stdout syslog file"
        filepath=None,
        ) -> None:
    import logging.config
    script_directory, script_name = os.path.split(__file__)
    # logging.getLogger('sh.command').setLevel(logging.WARN)
    if filepath is None:
        filepath = os.path.expanduser('~/.tmp/log/{}.log'.format(os.path.splitext(script_name)[0]))
    logging.config.dictConfig({'version':1,'disable_existing_loggers':False,
       'formatters':{
           'standard':{'format':'%(asctime)s %(levelname)-5s %(filename)s-%(funcName)s(): %(message)s'},
           'syslogf': {'format':'%(filename)s[%(process)d]: %(levelname)-5s %(funcName)s(): %(message)s'},
           #'graylogf':{"format":"%(asctime)s %(levelname)-5s %(filename)s-%(funcName)s(): %(message)s"},
           },
       'handlers':{
           'stdout':   {'level':level,'formatter': 'standard','class':'logging.StreamHandler',         'stream': 'ext://sys.stdout'},
           'file':     {'level':level,'formatter': 'standard','class':'logging.FileHandler',           'filename': filepath}, #
           'syslog':   {'level':level,'formatter': 'syslogf', 'class':'logging.handlers.SysLogHandler','address': '/dev/log', 'facility': 'user'}, # (localhost, 514), local5, ...
           #'graylog': {'level':level,'formatter': 'graylogf','class':'pygelf.GelfTcpHandler',         'host': 'log.mydomain.local', 'port': 12201, 'include_extra_fields': True, 'debug': True, '_ide_script_name':script_name},
       }, 'loggers':{'':{'handlers': use.split(),'level': level,'propagate':True}}})
    try: logging.getLogger('sh.command').setLevel(logging.WARN)
    except: pass

MR_CLIPBOARD = 1
MR_PRIMARY = 2

def id_to_str(i):
    if i == MR_CLIPBOARD: return "clipboard"
    if i == MR_PRIMARY:   return "primary"
    raise BaseException(str(i))

def get_other_gtk_clipboard(i):
    global clip_clipboard, clip_primary
    if i == MR_CLIPBOARD: return clip_primary
    if i == MR_PRIMARY:   return clip_clipboard
    raise BaseException(str(i))

def get_other_clip(i):
    if i == MR_CLIPBOARD: return MR_PRIMARY
    if i == MR_PRIMARY:   return MR_CLIPBOARD
    raise BaseException(str(i))

def last_set_time_old_enough(i):
    global last_set_time, last_change_time
    raise BaseException("unimplemented")

    if last_set_time is None:
        return True

    return None

def cb_clipboard(*args):
    global clip_clipboard
    cb(clip_clipboard.wait_for_text(), MR_CLIPBOARD, *args)

def cb_primary(*args):
    global clip_primary
    cb(clip_primary.wait_for_text(), MR_PRIMARY, *args)

def transform_to_log_format(s):
    s = s.replace("\r", "\\r")
    s = s.replace("\n", "\\n")
    if len(s) > 80:
        s = "[{}]: {}".format
    s = s[:

def cb(new_text, clip, *args):
    global last_set_time, last_change_time, last_set_clipboard, last_change_clipboard, last_text
    logger.info("id: %s n: %s", id_to_str(clip), new_text)

    if new_text is None:
        return

    last_change_time[clip] = datetime.datetime.now()
    next_last_change_clipboard = clip
    last_text[clip] = new_text

    other_clip     = get_other_clip(clip)
    other_gtk_clip = get_other_gtk_clipboard(clip)

    if last_text.get(other_clip, None) != new_text:
        Gtk.Clipboard.set_text(other_gtk_clip, new_text, len(new_text))
    last_change_clipboard = next_last_change_clipboard

last_change_time = {}
last_text = {}
last_set_time = {}
last_set_clipboard = None
last_change_clipboard = None
clip_primary = None
clip_clipboard = None
def go(args) -> None:
    global clip_primary
    global clip_clipboard

    event_name = 'owner-change'
    if 0:
        help(Gtk.Clipboard.set_text)
        help(Gtk.Clipboard)
        return

    clip_clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clip_clipboard.connect(event_name, cb_clipboard)

    clip_primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
    clip_primary.connect(event_name, cb_primary)

    logger.info("started")
    Gtk.main()
    logger.info("ended")

if __name__ == '__main__':
    logging_conf()
    if 'VIMF6' in os.environ and False:
        unittest.main()
    else:
        try:
            go(sys.argv[1:])
        except BaseException as e:
            logging.exception('oups for %s', sys.argv)
            sys.exit(1)

