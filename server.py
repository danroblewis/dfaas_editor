import flask
from flask import Flask, jsonify, request, send_file
import pymongo
import os
import yaml
from kubernetes import client, config
import subprocess
import io
import json

conn = pymongo.MongoClient(os.environ['MONGODB_HOST'], int(os.environ['MONGODB_PORT']), username=os.environ['MONGODB_USER'], password=os.environ['MONGODB_PASSWORD'])
coll = conn.test.dfaas_functions
apps = conn.test.dfaas_function_applications

app = Flask(__name__,
            static_url_path='',
            static_folder='public')

new_deployment_tpl = open('./new_deployment_template.yml').read()


def parse_mappings_from_code(text):
    """
    parses format of:

    application = "asdf"

    t_some_input->change_stuff->t_cool_output
    t_some_input->change_stuff->t_lame_output
    t_funny_input->change_stuff->t_better_output

    ignores lines with no ->
    starts at the first "application = "
    topics must be prepended by "t_"
    """
    parts = text.split("\napplication = ")
    if len(parts) == 1:
        return []
    text = parts[1]
    lines = ("application = " + text).split("\n")
    application_name = next(t for t in lines if t.startswith('application')).split("=")[1].strip().replace('"', '')
    mappings = []
    input_topic = None
    output_topic = None
    for line in lines:
        if '->' not in line:
            continue
        parts =  [ t.strip() for t in line.split("->") ]
        if len(parts) == 2:
            if parts[0].startswith('t_'): # topic -> function
                input_topic = parts[0][2:]
                function = parts[1]
            else: # function -> topic
                function = parts[0]
                output_topic = parts[1][2:]
        else:
            input_topic = parts[0][2:]
            function = parts[1]
            output_topic = parts[2][2:]

        mappings.append({
            "function_application": application_name,
            "function_name": function,
            "input_topic": input_topic,
            "output_topics": { "default": output_topic }
        })

    return mappings



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
    print("writing", code)
    coll.replace_one({'name': fname}, {'name': fname, 'code': code})
    mappings = parse_mappings_from_code(code)
    print('mappings', json.dumps(mappings, indent=4))
    for mapping in mappings:
        r = apps.find_one(mapping)
        if not r:
            apps.insert_one(mapping)
            print("added this one", mapping)
        else:
            print("this one already exists", mapping)
    return {'success': True}

@app.route('/create/<fname>', methods=['POST'])
def createfn(fname):
    coll.insert_one({'name': fname, 'code': ''})
    kube_submission = yaml.safe_load(new_deployment_tpl.format(deployment_name=fname.replace("_","-"), function_name=fname))
    config.load_incluster_config()
    v1 = client.AppsV1Api()
    resp = v1.create_namespaced_deployment(body=kube_submission, namespace="default")
    return {'success': True}

@app.route('/delete/<fname>', methods=['POST'])
def deletefn(fname):
    coll.delete_one({'name': fname})
    config.load_incluster_config()
    v1 = client.AppsV1Api()
    resp = v1.delete_namespaced_deployment(
        name="dfaas-" + fname.replace("_", "-"),
        namespace="default",
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", 
            grace_period_seconds=5
        )
    )
    return {'success': True}

@app.route('/fn_map')
def fn_map():
    fm = apps.find({})
    dotfile = ["digraph a {"]

    graph = {}
    topics = set()
    functions = set()
    for m in fm:
        inp = m['input_topic']
        outs = m['output_topics'].values()
        fname = m['function_name']
        topics.add(inp)
        functions.add(fname)
        if inp not in graph: 
            graph[inp] = set()
        graph[inp].add(fname)
        if fname not in graph: 
            graph[fname] = set()
        for out in outs:
            graph[fname].add(out)
            topics.add(out)
    for topic in topics:
        if topic is None: continue
        dotfile.append(f"\"{topic}\" [style=filled color=darkseagreen1]")
    for fname in functions:
        dotfile.append(f"\"{fname}\" [style=filled color=lightpink]")
    for a,bs in graph.items():
        for b in bs:
            if a is None or b is None: continue
            dotfile.append(f"\"{a}\"->\"{b}\"")
    dotfile.append("}")

    p = subprocess.Popen(['dot', '-Tsvg'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p.stdin.write("\n".join(dotfile).encode())
    p.stdin.flush()
    imgdata = p.communicate()[0]

    svg_io = io.BytesIO()
    svg_io.write(imgdata)
    svg_io.seek(0)
    return send_file(svg_io, mimetype='image/svg+xml')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)

