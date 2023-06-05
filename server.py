import flask
from flask import Flask, jsonify, request
import pymongo
import os

conn = pymongo.MongoClient(os.environ['MONGODB_HOST'], int(os.environ['MONGODB_PORT']), username=os.environ['MONGODB_USER'], password=os.environ['MONGODB_PASSWORD'])
coll = conn.test.dfaas_functions

app = Flask(__name__,
            static_url_path='',
            static_folder='public')


@app.route('/')
def index():
    with open('public/index.html') as f:
        return f.read()


@app.route('/function_list')
def function_list():
    names = [ r['name'] for r in coll.find({}) ]
    return names


@app.route('/read/<fname>')
def readfn(fname):
    rec = coll.find_one({ 'name': fname })
    return jsonify({ 'code': rec['code'] })


@app.route('/write/<fname>', methods=['POST'])
def writefn(fname):
    code = request.json['code']
    coll.replace_one({'name': fname}, {'name': fname, 'code': code})
    return {'success': True}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)

