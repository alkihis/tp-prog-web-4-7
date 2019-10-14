import flask
from flask import send_from_directory

app = flask.Flask(__name__)

import root
import parts
import gene

# Listen for get request on root
@app.route('/<path:filename>')
def serve_root(filename):
  return send_from_directory('static', filename)
