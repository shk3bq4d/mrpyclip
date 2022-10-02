#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /* ex: set filetype=python ts=4 sw=4 expandtab: */

from threading import Thread,Condition
import textwrap
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
    def test_transform(self) -> None:
        test_cases = [
                ("a", "a"),
                (" a", "a"),
                ("a ", "a"),
                (" \n  a", "a"), # in the end this a single line with only "a" as a content
                (" \n  a\n    ", "a"), # in the end this a single line with only "a" as a content
                (" \n  a\n  b", "  a\n  b"),
                (" \n  a\n  b\n  ", "  a\n  b"),
                ("a\n\nb", "a\n\nb", "empty lines at the middle of the content should be kept"),
                ]

        for case in test_cases:
            message = None
            if len(case) == 2: _input, expected = case
            elif len(case) == 3: _input, expected, message = case
            else: raise BaseException("unexpected case length {}".format(len(case)))
            actual = transform(_input)

            self.assertEqual(expected, actual, message)

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

def get_gtk_clipboard(i):
    global clip_clipboard, clip_primary
    if i == MR_CLIPBOARD: return clip_clipboard
    if i == MR_PRIMARY:   return clip_primary
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
    cb(clip_clipboard, MR_CLIPBOARD, *args)

def cb_primary(*args):
    global clip_primary
    cb(clip_primary, MR_PRIMARY, *args)

def transform_to_log_format(s):
    if s is None:
        return None
    s = s.replace("\r", "\\r")
    s = s.replace("\n", "\\n")
    if len(s) > 80:
        s = "[{}]: {}".format(len(s), s[:80])
    return s

def garbage_collector_ignoreA():
    global _ignoreA
    to_deleteA = []
    now = datetime.datetime.now()
    for k, elem in enumerate(_ignoreA):
        date = elem[0]
        if (now - elem[0]).total_seconds() > 20:
            to_deleteA.append(k)

    for k in sorted(to_deleteA, reverse=True):
        _ignoreA.pop(k)


def set_clipboard(clip, text, reason=None):
    global _ignoreA
    if reason:
        logger.info("Setting %s du to %s to %s", id_to_str(clip), reason, transform_to_log_format(text))
    else:
        logger.info("Setting %s to %s", id_to_str(clip), transform_to_log_format(text))
    gtk_clip = get_gtk_clipboard(clip)
    struct = (datetime.datetime.now(), clip, text)
    _ignoreA.append(struct)
    _bytes = text.encode("utf-8")
    Gtk.Clipboard.set_text(gtk_clip, text, len(_bytes))

def probably_set_by_me(clip, new_text):
    now = datetime.datetime.now()
    for past_date, past_clip, past_text in _ignoreA:
        if (now - past_date).total_seconds() < 10 and \
            past_clip == clip and \
            past_text == new_text:
            logger.info("now: %s, then: %s", past_date, now)
            return True
    return False

def transform(text):
    # trim left newline (+ white characters)
    text = re.sub(r'\n\s*$', '', text)

    text = re.sub(r'\A\s*\n', '', text)
    if "\n" not in text:
        text = text.strip()
    else:
        text = re.sub(r'[ \t]+$', '', text, flags=re.M) # trim right each line

    return text

_ignoreA = []
def cb(rawclip, clip, *args):
    global last_set_time, last_change_time, last_set_clipboard, last_change_clipboard, last_text, _ignoreA

    tb = Gtk.TextBuffer()
    a=rawclip.wait_is_image_available()
    b=rawclip.wait_is_rich_text_available(tb)
    #c=rawclip.wait_is_target_available(TARGET),
    d=rawclip.wait_is_text_available()
    e=rawclip.wait_is_uris_available()
    if False:
        logger.info("\n" + textwrap.dedent("""
            wait_is_image_available:     {a}
            wait_is_rich_text_available: {b}
            wait_is_text_available:      {d}
            wait_is_uris_available:      {e}
            """).format(
                a=a,
                b=b,
                #wait_is_target_available:    {c}
                #c=rawclip.wait_is_target_available(),
                d=d,
                e=e
                ))

    if not d:
        logger.info("complex event image:{a} rich:{b} e:{e}".format(a=a,b=b,e=e))
        return

    new_text = rawclip.wait_for_text()



    id_str = id_to_str(clip)

    if new_text is None:
        logger.info("id: %s new_text is None", id_str)
        new_text = ''
        if last_text.get(clip, None) is not None:
            set_clipboard(clip, last_text.get(clip), reason="restoring clipboard value as a citrix hack #0")
        return

    if probably_set_by_me(clip, new_text):
        logger.info("id: %s discarding probably my own event", id_str)
        return

    logger.info("id: %s n: %s", id_str, transform_to_log_format(new_text))

    transformed_text = transform(new_text)
    if transformed_text != new_text:
        new_text = transformed_text
        set_clipboard(clip, new_text, reason="correcting just changed clipboard with filtered value")

    last_change_time[clip] = datetime.datetime.now()
    next_last_change_clipboard = clip
    last_text[clip] = new_text

    other_clip     = get_other_clip(clip)

    if last_text.get(other_clip, None) != new_text:
        set_clipboard(other_clip, new_text, reason="mirror other clipboard")
        set_clipboard(clip, new_text, reason="citrix hack #1") # citrix work around where there is a quick "1) set to none, 2) set to actual value". If my call to revert 1) to value at T=0 happens after 2) then I would have lost 2) on the source. Consequently if I requeue an otherwrite on self, I may add another change
    last_change_clipboard = next_last_change_clipboard
    garbage_collector_ignoreA()

cv = None
stop = False
def start_background_thread(c,p):
    global cv
    cv = Condition()
    args = (cv,c,p)
    _background_thread = Thread(target=background_thread, args=args).start()

def background_thread(cv,c,p):
    global stop
    cv.acquire()
    while not stop:
        logger.debug("Going to wait mode")
        cv.wait(2)
        if stop:
            break
        background_thread_action(c,p)
        logger.debug("I have either been woken up or timeout expired")
    logger.info("End of background_thread")
    cv.release()

def background_thread_action(c,p):
    #logger.info("A")
    #logger.info("primary %s".format(p.wait_for_text()))
    #logger.info("B")
    pass

last_change_time = {}
last_text = {}
last_set_time = {}
last_set_clipboard = None
last_change_clipboard = None
clip_primary = None
clip_clipboard = None
def go(args) -> None:
    global cv, stop
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

    start_background_thread(clip_clipboard,clip_primary)

    logger.info("started")
    Gtk.main()
    stop = True
    notify()
    logger.info("ended")

def notify():
    global cv
    try:
        cv.acquire()
        cv.notify()
        logger.info("Notified")
    finally:
        try:
            cv.release()
        except:
            pass

if __name__ == '__main__':
    logging_conf()
    if 'VIMF6' in os.environ:
        unittest.main()
    else:
        try:
            go(sys.argv[1:])
        except BaseException as e:
            logging.exception('oups for %s', sys.argv)
            sys.exit(1)

