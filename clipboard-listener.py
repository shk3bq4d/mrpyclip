#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /* ex: set filetype=python ts=4 sw=4 expandtab: */
#
# 2023.07.27 disabling citrix hack 0
# /bin/sh -c ~/bin/clipboard-listener.py  2>&1 | ts > ~/.tmp/log/clipboard-listener.log
# /bin/sh -c ~/bin/clipboard-listener.py  2>&1 | ts | tee -a ~/.tmp/log/clipboard-listener.log

# pkill -f 'python3.*clipboard-listener.py'
# nohup bash -c '~/bin/clipboard-listener.py  2>&1 | ts > ~/.tmp/log/clipboard-listener.log' &>/dev/null </dev/null &
# tail -f $(ls -1tr ~/.tmp/log/clipboard-listener.log* | grep -vE gz$ | tail -n 1)
# gitrumo log --patch ~/bin/clipboard-listener.py

from threading import Thread,Condition
import textwrap
import datetime
import os
import sys
import re
import unittest
import argparse
import logging
import base64
import gzip
from typing import Sequence, Union, Iterator, List, Tuple, no_type_check, Any, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from pprint import pprint, pformat

logger = logging.getLogger(__name__)

call_number = 0

# for i in $(seq 3 200);   do c=${#i}; g="$(openssl rand -base64 $i | tr -d ' \n' | sed -r -e 's/^(.{'$(( i - c - 1 ))'}).*/\1/' )"; echo "${i}-${g}"; done
# for i in $(seq 3 200);   do c=${#i}; g="$(openssl rand -base64 $i | tr -d ' \n' | sed -r -e 's/^(.{'$(( i - c - 1 ))'}).*/\1/' )"; echo "${i}-${g}"; done | while read line; do echo -n "$(tr -d '\n' <<< $line | wc -c)"; echo " $line"; done
compress_prefix64 = "mr64"
compress_prefix85 = "mr85"

class ClipboardListenerTest(unittest.TestCase):
    def test_compression(self) -> None:
        if False:
            adobe_start = '<~'
            adobe_end = '~>'
            a = adobe_start + "9jqo^BlbD-BleB1DJ+*+F(f,q/0JhKF<GL>Cj@.4Gp$d7F!,L7@<6@)/0JDEF<G%<+EV:2F!,O<DJ+*.@<*K0@<6L(Df-\\0Ec5e;DffZ(EZee.Bl.9pF\"AGXBPCsi+DGm>@3BB/F*&OCAfu2/AKYi(DIb:@FD,*)+C]U=@3BN#EcYf8ATD3s@q?d$AftVqCh[NqF<G:8+EV:.+Cf>-FD5W8ARlolDIal(DId<j@<?3r@:F%a+D58'ATD4$Bl@l3De:,-DJs`8ARoFb/0JMK@qB4^F!,R<AKZ&-DfTqBG%G>uD.RTpAKYo'+CT/5+Cei#DII?(E,9)oF*2M7/c" + adobe_end
            b =  "Man is distinguished, not only by his reason, but by this singular passion from other animals, which is a lust of the mind, that by a perseverance of delight in the continued and indefatigable generation of knowledge, exceeds the short vehemence of any carnal pleasure."
            # stopping here as I need to zip content
            print(base64.a85encode(b.encode('us-ascii')).decode())
            print(a)
            print(base64.a85encode("Random String".encode('us-ascii')).decode())
        test_cases = [
                (f"{compress_prefix64}H4sIAAAAAAAEAEtMHAWjYBSMYAAAaA+JHwMEAAA=", "a" * 1027, True),
                (f"{compress_prefix64}H4sIAAAAAAAEAEtMHAWjYBSMWJAEAC4n78UCBAAA", ("a" * 1025) + "b", True),
#               (f"{compress_prefix85}{a}", b),
                (f"{compress_prefix85}<~+,^C)z\"9;(g*!N*F'T?8s!0hZh>QP$.!!~>", "a" * 1026, True),
                (f"{compress_prefix85}<~+,^C)z\"9;(g*!N*F'T?.U\"9:&%n&5>2!!!~>", ("a" * 1025) + "b", True),
                ]

        for _in, expected, adobe in test_cases:
            actual =  uncompress(_in, adobe=adobe)
            self.assertEqual(expected, actual, msg=f"for in {_in}")


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

def decode_base64_gzip(encoded_string):
    # Decode base64
    decoded_data = base64.b64decode(encoded_string)

    # Decompress gzip
    original_string = gzip.decompress(decoded_data).decode('utf-8')

    return original_string

def decode_base85_gzip(encoded_string, adobe=False):
    # Decode base64
    decoded_data = base64.a85decode(encoded_string, adobe=adobe)

    # Decompress gzip
    original_string = gzip.decompress(decoded_data).decode('utf-8')

    return original_string

def matches_ud_powershell_compression(s):
    return s.startswith(compress_prefix64) or s.startswith(compress_prefix85)

def uncompress(s: str, adobe: bool=False) -> str:
    if not s.startswith(compress_prefix64) and not s.startswith(compress_prefix85): raise BaseException("Shouldn't be there")
    if s.startswith(compress_prefix64):
        s = s[len(compress_prefix64):]
        s = decode_base64_gzip(s)
    elif s.startswith(compress_prefix85):
        s = s[len(compress_prefix85):]
        s = decode_base85_gzip(s, adobe=adobe)
    else:
        raise BaseException("unimplemented64-85")
    return s

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
    global clip_clipboard, call_number
    call_number = call_number + 1
    logger.info(f"{call_number} cb_clipboard")
    cb(clip_clipboard, MR_CLIPBOARD, *args)

def cb_primary(*args):
    global clip_primary, call_number
    logger.info(f"{call_number} cb_primary")
    cb(clip_primary, MR_PRIMARY, *args)

def transform_to_log_format(s):
    if s is None:
        return None
    length = len(s)
    s = s.replace("\r", "\\r")
    s = s.replace("\n", "\\n")
    if length >= 8 and length < 48:
        s = "{}{}{}".format(s[:2], "*" * (len(s) - 4), s[-2:])
    elif len(s) > 80:
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
    if text is None: raise BaseException("calling set_clipboard with None")
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
    if True:
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
        next_text = None
#       help(rawclip)
#       next_text = rawclip.wait_for_rich_text()
        if not next_text:
            logger.info(f"<- {call_number} A")
            return
        logger.info("gtk_clipboard_wait_for_rich_text youpi")
        logger.info(next_text)
        next_text = str(next_text)



    new_text = rawclip.wait_for_text()
    id_str = id_to_str(clip)

    if new_text is None:
        logger.info("id: %s new_text is None", id_str)
        new_text = ''
        if last_text.get(clip, None) is not None and False:
            # this block got twice removed on different PC
            # I'm disabling citrix hack #0 on 2023.07.27
            # 2023.12.04 I am deactivating this block as the freaking ~500 char limitation they put in place frequently sends back None to my clipboard, even if I never quitted the citrix window. So if I'm then restoring the clipboard content with a past value, I am erasing the citrix clipboard which is not what I wanted
            set_clipboard(clip, last_text.get(clip), reason="restoring clipboard value as a citrix hack #0")
            logger.info(f"<- {call_number} A")
        return

    other_clip     = get_other_clip(clip)
    if matches_ud_powershell_compression(new_text):
        new_text = uncompress(new_text)
        set_clipboard(clip, new_text, reason="Citrix uncompress")
        set_clipboard(other_clip, new_text, reason="Citrix uncompress")
        logger.info(f"<- {call_number} Citrix uncompress")
        return


    if probably_set_by_me(clip, new_text):
        logger.info("id: %s discarding probably my own event", id_str)
        logger.info(f"<- {call_number} B")
        return

    logger.info("id: %s n: %s", id_str, transform_to_log_format(new_text))

    transformed_text = transform(new_text)
    if transformed_text != new_text:
        new_text = transformed_text
        set_clipboard(clip, new_text, reason="correcting just changed clipboard with filtered value")

    last_change_time[clip] = datetime.datetime.now()
    next_last_change_clipboard = clip
    last_text[clip] = new_text


    if last_text.get(other_clip, None) != new_text:
        set_clipboard(other_clip, new_text, reason="mirror other clipboard")
        set_clipboard(clip, new_text, reason="citrix hack #1") # citrix work around where there is a quick "1) set to none, 2) set to actual value". If my call to revert 1) to value at T=0 happens after 2) then I would have lost 2) on the source. Consequently if I requeue an otherwrite on self, I may add another change
    last_change_clipboard = next_last_change_clipboard
    garbage_collector_ignoreA()
    logger.info(f"<- {call_number} end of function")

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

