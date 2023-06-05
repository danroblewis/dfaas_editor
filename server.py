import flask
from flask import Flask, jsonify

app = Flask(__name__,
            static_url_path='',
            static_folder='public')

@app.route('/')
def index():
    with open('public/index.html') as f:
        return f.read()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)

