#Flask app that serves alpha_score.py
import flask
from flask import request, jsonify
import alpha_score

app = flask.Flask(__name__)

