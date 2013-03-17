#!/usr/bin/env python

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

"""

import sys, os, mimetypes, smtplib
from scriptutils.arguments import Arguments
from unicodeutils import decode
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


def get_arguments():
    a = Arguments(description="Command line mail user agent using MIME as the message format")
    a.add_argument('attachments', metavar='FILE', nargs='*', help="a file to attach")
    a.add_argument('-s', '--subject', help='email subject')
    a.add_argument('-t', '--to', metavar='ADDRESS', action='append', help='email recipient')
    a.add_argument('-f', '--sender', metavar='ADDRESS', help='email sender')
    a.add_argument('--cc', metavar='ADDRESS', action='append', help='email CC recipient')
    a.add_argument('--bcc', metavar='ADDRESS', action='append', help='email BCC recipients')
    a.add_argument('--body-text', metavar='TEXT', help='email body (from string)')
    a.add_argument('--body-file', metavar='FILE', help='email body (from file)')
    a.add_argument('--server', default='localhost', help='SMTP server (default: localhost)')
    a.add_argument('-p', '--port', type=int, default=25, help='SMTP server port (default: 25)')
    a.add_argument('-U', '--username', help='SMTP server username')
    a.add_argument('-P', '--password', help='SMTP server password')
    a.add_argument('--tls', action='store_true', default=False, help='use TLS with SMTP server')
    return a.parse_args()


def get_username():
    if sys.platform.startswith('win'):
        return
    import pwd
    return pwd.getpwuid(os.geteuid())[0]


def smtp_session(server='localhost', port=25, tls=False, username=None, password=None):
    session = smtplib.SMTP(server, port)
    if tls:
        session.ehlo()
        session.starttls()
        session.ehlo()
    if username and password:
        session.login(username, password)
    return session


def encode_header(value):
    """Creates a string that's properly encoded for use in an email header."""
    return str(Header(unicode(value), 'iso-8859-1'))


def format_address(value):
    """Properly formats email addresses."""
    if type(value) in (tuple, list):
        return ', '.join([format_address(v) for v in value])
    name, addr = parseaddr(value)
    return formataddr((encode_header(name), addr.encode('ascii')))


def main():
    args = get_arguments()
    mail = MIMEMail()
    # Determine from what source we will be getting the message body.
    if args.body_text:
        body = args.body_text
    elif args.body_file:
        body = open(args.body_file).read()
    else:
        body = sys.stdin.read()
    mail.set_body(body)
    # Multiple addresses can be provided as a comma separated string.
    mail.recipients['to'] = args.to
    mail.recipients['cc'] = args.cc
    mail.recipients['bcc'] = args.bcc
    # Attachments are provided as command line arguments.
    mail.set_attachments(args.attachments)
    smtp = smtp_session(
            server=args.server,
            port=args.port,
            tls=args.tls,
            username=args.username,
            password=args.password,
            )
    mail.send(smtp, args.subject, args.sender)


class MIMEMail(object):

    def __init__(self):
        self.message = MIMEMultipart()
        self.recipients = {}
        self.recipient_types = ('to', 'cc', 'bcc')

    def set_body(self, body):
        body = decode(body)
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
        if not key:
            key = 'to'
        key = key.lower()
        if key not in self.recipient_types:
            raise MIMEMailError("Invalid recipient type")
        if type(recipients) not in (tuple, list):
            recipients = [recipients]
        self.recipients[key] = recipients

    def set_attachments(self, paths):
        if type(paths) not in (tuple, list):
            paths = [paths]
        for path in paths:
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            data = open(path, 'rb').read()
            try:
                attachment = {
                        'text': MIMEText,
                        'image': MIMEImage,
                        'audio': MIMEAudio,
                        'message': MIMEMessage,
                        'application': MIMEApplication,
                        }[maintype](data, subtype)
            except KeyError:
                attachment = MIMEBase(maintype, subtype)
                attachment.set_payload(data)
                encode_base64(attachment)
            attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(path))
            self.message.attach(attachment)

    def send(self, smtp=None, subject='', sender=None):
        if not smtp:
            smtp = smtp_session()
        if not sender:
            sender = get_username()
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


class MIMEMailError(Exception):
    pass

if __name__ == '__main__':
    main()
