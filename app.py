from flask import Flask

app = Flask(__name__)

import config

import models

from controllers import register_blueprints

register_blueprints(app)

if __name__ == "__main__":
    app.run(debug=True)