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
    mail.set_recipients(['spam@eggs.com', 'Jim Generic <jim@email.org>'])
    mail.set_body(open('body.txt').read())
    mail.set_attachments(['stuff.zip', 'image.png'])
    mail.send(subject="Here's Your Stuff")

""" #}}}

import sys, os, mimetypes, smtplib
from os.path import basename
from scriptutils.options import Options
from email.encoders import encode_base64
from email.header import Header
from email.utils import parseaddr, formataddr

from email.mime.audio       import MIMEAudio
from email.mime.base        import MIMEBase
from email.mime.image       import MIMEImage
from email.mime.application import MIMEApplication
from email.mime.multipart   import MIMEMultipart
from email.mime.text        import MIMEText
from email.mime.message     import MIMEMessage

def get_options(): #{{{1
    opts = Options(args='[file...]', width=40)
    opts.add_option('-s', '--subject', help='Email subject.')
    opts.add_option('-t', '--to', action='append', help='Email recipient.')
    opts.add_option('-f', '--sender', help='Email sender')
    opts.add_option('--cc', action='append', help='Email CC recipient.')
    opts.add_option('--bcc', action='append', help='Email BCC recipients.')
    opts.add_option('--body-text', help='Email body (from string).')
    opts.add_option('--body-file', help='Email body (from file).')
    opts.add_option('--server', default='localhost', help='SMTP server (default: localhost).')
    opts.add_option('-p', '--port', type='int', default=25, help='SMTP server port (default: 25).')
    opts.add_option('-U', '--username', help='SMTP server username.')
    opts.add_option('-P', '--password', help='SMTP server password.')
    opts.add_option('--tls', action='store_true', default=False, help='Use TLS with SMTP server')
    return opts.parse_args()

def get_username(): #{{{1
    if sys.platform.startswith('win'): return
    import pwd
    return pwd.getpwuid(os.geteuid())[0]

def smtp_session(server='localhost', port=25, tls=False, username=None, password=None): #{{{1
    session = smtplib.SMTP(server, port)
    if tls:
        session.ehlo()
        session.starttls()
        session.ehlo()
    if username and password:
        session.login(username, password)
    return session

def encode_header(value): #{{{1
    """Creates a string that's properly encoded for use in an email header."""
    return str(Header(unicode(value), 'iso-8859-1'))

def format_address(value): #{{{1
    """Properly formats email addresses."""
    if type(value) in (tuple, list):
        return ', '.join([format_address(v) for v in value])
    name, addr = parseaddr(value)
    return formataddr((encode_header(name), addr.encode('ascii')))

def main(): #{{{1
    opts, args = get_options()
    mail = MIMEMail()
    # Determine from what source we will be getting the message body.
    if    opts.body_text: body = opts.body_text
    elif  opts.body_file: body = open(opts.body_file).read()
    else:                 body = sys.stdin.read()
    mail.set_body(unicode(body, encoding='utf-8'))
    # Multiple addresses can be provided as a comma separated string.
    mail.recipients['to']  = opts.to
    mail.recipients['cc']  = opts.cc
    mail.recipients['bcc'] = opts.bcc
    # Attachments are provided as command line arguments.
    if args: mail.set_attachments(args)
    smtp = smtp_session(
            server=opts.server,
            port=opts.port,
            tls=opts.tls,
            username=opts.username,
            password=opts.password,
            )
    mail.send(smtp, opts.subject, opts.sender)

#}}}1

class MIMEMail(object): #{{{1

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

    def set_to(self, recipients):
        self.set_recipients(recipients, 'to')

    def set_cc(self, recipients):
        self.set_recipients(recipients, 'cc')

    def set_bcc(self, recipients):
        self.set_recipients(recipients, 'bcc')

    def set_recipients(self, recipients, key=None):
        if not key: key = 'to'
        key = key.lower()
        if key not in self.recipient_types:
            raise MIMEMailError("Invalid recipient type")
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
            try:
                attachment = {
                        'text':        MIMEText,
                        'image':       MIMEImage,
                        'audio':       MIMEAudio,
                        'message':     MIMEMessage,
                        'application': MIMEApplication,
                        }[maintype](data, subtype)
            except KeyError:
                attachment = MIMEBase(maintype, subtype)
                attachment.set_payload(data)
                encode_base64(attachment)
            attachment.add_header('Content-Disposition', 'attachment', filename=basename(path))
            self.message.attach(attachment)

    def send(self, smtp=None, subject='', sender=None):
        if not smtp: smtp = smtp_session()
        if not sender: sender = get_username()
        if 'to' in self.recipients:
            self.message['To'] = format_address(self.recipients['to'])
        if 'cc' in self.recipients:
            self.message['CC'] = format_address(self.recipients['cc'])
        self.message['From'] = format_address(sender)
        s = encode_header(subject)
        self.message['Subject'] = s
        self.message.preamble = s
        self.message.epilogue = ''
        recipients = sum((r for r in self.recipients.values() if r), [])
        smtp.sendmail(sender, recipients, self.message.as_string())



class MIMEMailError(Exception): pass #{{{1

#}}}1

if __name__ == '__main__': main()
