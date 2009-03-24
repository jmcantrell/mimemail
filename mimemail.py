#!/usr/bin/env python

# DESCRIPTION {{{
"""Command line mail user agent using MIME as the message format.

The message body is given over stdin, as a string (--body-text), or as a
filename (--body-file). All other information is given through options. To see
available options, run the following command at the command line:

    mimemail --help

Some examples of typical usage:

    Send the output of a command:

        cmd | mimemail -t spam@eggs.com

    Do the same, but with attachments:

        cmd | mimemail -t spam@eggs.com stuff.zip document.pdf

MIMEMail can also be used in other python scripts:

    from mimemail import MIMEMail

    mail = MIMEMail()
    mail.set_recipients(['spam@eggs.com', 'Michael Spam Palin <michael@spam.org>'])
    mail.set_body(open('body.txt').read())
    mail.set_attachments(['stuff.zip', 'image.png'])
    mail.send(subject="Here's Your Stuff")

""" #}}}

__author__  = 'Jeremy Cantrell <jmcantrell@gmail.com>'
__url__     = 'http://jeremycantrell.com'
__date__    = 'Tue 2008-02-05 14:55:05 (-0500)'
__license__ = 'GPL'

import sys, os, mimetypes, smtplib
from os.path import basename
from scriptutils.options import Options
from email.encoders import encode_base64
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage
from email.header import Header
from email.utils import parseaddr, formataddr

# FUNCTIONS {{{1

def get_options(): #{{{2
    opts = Options('Usage: %prog [options] [file...]', width=40)
    opts.add_option('-h', '--help', help='Show this help message and exit.', action='help')
    opts.add_option('-s', '--subject', help='Email subject')
    opts.add_option('-t', '--to', default='', help='Email recipients (comma-separated)')
    opts.add_option('-f', '--sender', help='Email sender')
    opts.add_option('--cc', default='', help='Email CC recipients (comma-separated)')
    opts.add_option('--bcc', default='', help='Email BCC recipients (comma-separated)')
    opts.add_option('--body-text', help='Email body (from string)')
    opts.add_option('--body-file', help='Email body (from file)')
    opts.add_option('--server', help='SMTP server (default: localhost)')
    opts.add_option('-p', '--port', type='int', help='SMTP server port (default: 25)')
    opts.add_option('-U', '--username', help='SMTP server username')
    opts.add_option('-P', '--password', help='SMTP server password')
    opts.add_option('--tls', action='store_true', default=False, help='Use TLS with SMTP server')
    return opts.parse_args()

def get_username(): #{{{2
    if sys.platform.startswith('win'): return
    import pwd
    return pwd.getpwuid(os.geteuid())[0]

def smtp_session(server=None, port=None, username=None, password=None, tls=False): #{{{2
    """Creates an SMTP session that defaults to localhost:25 with no authentication or encryption."""
    session = smtplib.SMTP(server or 'localhost', port or 25)
    if tls:
        session.ehlo()
        session.starttls()
        session.ehlo()
    if username and password: session.login(username, password)
    return session

def encode_header(value): #{{{2
    """Creates a string that's properly encoded for use in an email header."""
    return str(Header(unicode(value), 'iso-8859-1'))

def format_address(value): #{{{2
    """Properly formats email addresses."""
    if type(value) in (tuple, list): return ', '.join([format_address(v) for v in value])
    name, addr = parseaddr(value)
    return formataddr((encode_header(name), addr.encode('ascii')))

def main(): #{{{2
    opts, args = get_options()
    mail = MIMEMail()
    # Determine from what source we will be getting the message body.
    if opts.body_text:   body = opts.body_text
    elif opts.body_file: body = open(opts.body_file).read()
    else:                body = sys.stdin.read()
    mail.set_body(unicode(body, encoding='utf-8'))
    # Multiple addresses can be provided as a comma separated string.
    if opts.to:  mail.recipients['to']  = [a.strip() for a in opts.to.split(',')]
    if opts.cc:  mail.recipients['cc']  = [a.strip() for a in opts.cc.split(',')]
    if opts.bcc: mail.recipients['bcc'] = [a.strip() for a in opts.bcc.split(',')]
    # Attachments are provided as command line arguments.
    if args: mail.set_attachments(args)
    smtp = smtp_session(opts.server, opts.port, opts.username, opts.password, opts.tls)
    mail.send(smtp, opts.subject, opts.sender)


# CLASSES {{{1

class MIMEMail(object): #{{{2

    def __init__(self):
        self.message = MIMEMultipart()
        self.recipients = {}
        self.recipient_types = ('to', 'cc', 'bcc')

    def set_body(self, body):
        for body_charset in 'ascii', 'iso-8859-1', 'utf-8':
            try:
                body = MIMEText(body.encode(body_charset), 'plain', body_charset)
            except UnicodeError:
                pass
            else:
                break
        self.message.attach(body)

    def set_recipients(self, recipients, key=None):
        if not key: key = 'to'
        key = key.lower()
        if key not in self.recipient_types: raise MIMEMailError("Invalid recipient type")
        if type(recipients) not in (tuple, list): recipients = [recipients]
        self.recipients[key] = recipients

    def set_attachments(self, paths):
        if type(paths) not in (tuple, list): paths = [paths]
        for path in paths:
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            data = open(path, 'rb').read()
            if   maintype == 'text':        attachment = MIMEText(data, subtype)
            elif maintype == 'image':       attachment = MIMEImage(data, subtype)
            elif maintype == 'audio':       attachment = MIMEAudio(data, subtype)
            elif maintype == 'message':     attachment = MIMEMessage(data, subtype)
            elif maintype == 'application': attachment = MIMEApplication(data, subtype)
            else:
                attachment = MIMEBase(maintype, subtype)
                attachment.set_payload(data)
                encode_base64(attachment)
            attachment.add_header('Content-Disposition', 'attachment', filename=basename(path))
            self.message.attach(attachment)

    def send(self, smtp=None, subject='', sender=None):
        if not smtp: smtp = smtp_session()
        if not sender: sender = get_username()
        if 'to' in self.recipients: self.message['To'] = format_address(self.recipients['to'])
        if 'cc' in self.recipients: self.message['CC'] = format_address(self.recipients['cc'])
        self.message['From'] = format_address(sender)
        self.message['Subject'] = self.message.preamble = encode_header(subject)
        self.message.epilogue = ''
        smtp.sendmail(sender, sum(self.recipients.values(), []), self.message.as_string())



class MIMEMailError(Exception): pass #{{{2

#}}}

if __name__ == '__main__': main()
