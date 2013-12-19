import json
import os
import requests
from flask import Flask, request, abort, session
from functools import wraps
from twilio.util import RequestValidator
from twilio import twiml


app = Flask(__name__)
app.secret_key = 'd1e743a696ae082d24c0458d2b088dd60dee44f4'
validator = RequestValidator(os.environ['TWILIO_AUTH_TOKEN'])
email_address = os.environ['GJB_EMAIL_ADDRESS']
mandrill_key = os.environ['MANDRILL_AUTH_TOKEN']


EMAIL_TEMPLATE = """\
Someone has recorded a message for the show!
They called in from %(phone_number)s.
You can listen to their recording at the following url:

%(recording_url)s

Thanks,
Record-o-bot

PS. Record-o-bot is run by Ben Olive (@sionide21).
If you have questions/comments, or you want me to stop, feel free to email him directly at sionide21@gmail.com.
"""


def send_email(recording_url, phone_number):
    requests.post('https://mandrillapp.com/api/1.0/messages/send.json', data=json.dumps({
        "message": {
            "text": EMAIL_TEMPLATE % dict(recording_url=recording_url, phone_number=phone_number),
            "subject": "Recording for the show from %s" % phone_number,
            "from_email": "record.o.bot@mx.moosen.net",
            "from_name": "Record-o-bot",
            "to": [
                {
                    "email": email_address,
                    "type": "to"
                }
            ]
        },
        "key": mandrill_key
    })).raise_for_status()


def twilio(fn):
    @app.route('/' + fn.__name__, methods=['POST'])
    @wraps(fn)
    def _fn():
        proto = request.headers.get('X-Forwarded-Proto', 'http')
        url = request.url.replace('http:', proto + ':')

        if validator.validate(url, request.values, request.headers.get('X-Twilio-Signature', '')):
            resp = twiml.Response()
            fn(resp)
        else:
            abort(403)
        return str(resp)
    return _fn


@twilio
def start(resp):
    resp.pause(length=1)
    resp.say(
        "After the tone, record your message for good job brain. "
        "Messages are limited to five minutes. "
        "When you are finished recording: press 1 to review the message, or press 2 to send the message."
    )
    resp.pause(length=1)
    resp.record(maxLength="300", action="/finished_recording")


@twilio
def finished_recording(resp):
    recording_url = request.values.get('RecordingUrl', session.get('recording_url'))
    session['recording_url'] = recording_url
    with resp.gather(numDigits=1, action="/key_pressed", method="POST") as g:
        g.say("Press 1 to review the message, press 2 to send the message, or press 3 to delete the message and re-reecord.")


@twilio
def send_recording(resp):
    recording_url = session['recording_url']
    send_email(recording_url, request.values.get('From'))
    resp.say("You recording has been sent. Good bye.")


@twilio
def key_pressed(resp):
    digit_pressed = request.values.get('Digits')
    recording_url = session['recording_url']

    if digit_pressed == "1":
        resp.play(recording_url)
        resp.redirect('/finished_recording')
    elif digit_pressed == "2":
        resp.say("Please hang on while I send your recording.")
        resp.redirect("/send_recording")
    elif digit_pressed == "3":
        resp.record(maxLength="300", action="/finished_recording")
    else:
        resp.say("Invalid key.")
        resp.redirect('/finished_recording')


if __name__ == "__main__":
    app.run(debug=True)
