import os
from flask import Flask, request, abort, session
from functools import wraps
from twilio.util import RequestValidator
from twilio import twiml


app = Flask(__name__)
app.secret_key = 'd1e743a696ae082d24c0458d2b088dd60dee44f4'
validator = RequestValidator(os.environ['TWILIO_AUTH_TOKEN'])


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
def key_pressed(resp):
    digit_pressed = request.values.get('Digits')
    recording_url = session['recording_url']

    if digit_pressed == "1":
        resp.play(recording_url)
        resp.redirect('/finished_recording')
    elif digit_pressed == "2":
        resp.say("It is done")
    elif digit_pressed == "3":
        resp.record(maxLength="300", action="/finished_recording")
    else:
        resp.say("Invalid key.")
        resp.redirect('/finished_recording')


if __name__ == "__main__":
    app.run(debug=True)
