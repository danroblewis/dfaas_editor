import flask
from flask import Flask, jsonify, request, send_file
import pymongo
import os
import yaml
from kubernetes import client, config
import subprocess
import io
import json
from dfaal import parse_applications

conn = pymongo.MongoClient(os.environ['MONGODB_HOST'], int(os.environ['MONGODB_PORT']), username=os.environ['MONGODB_USER'], password=os.environ['MONGODB_PASSWORD'])
coll = conn.test.dfaas_functions
processes = conn.test.dfaas_processes
apps = conn.test.dfaas_function_applications

app = Flask(__name__,
            static_url_path='',
            static_folder='public')

new_deployment_tpl = open('./new_deployment_template.yml').read()


def reprocess_mappings(sample=""):
    # get all processes from the database
    # add sample to it, so we can use this function for testing before uploading
    # parse the whole text
    # process it into the database format also
    # return database formatted records for re-upload
    texts = [ p['code'] for p in processes.find({}) ]
    texts.append(sample)
    text = "\n".join(texts)
    applications = parse_applications(text)
    
    mappings = {}

    for f, fn, t in applications:
      from_name = f.name if f else "null"
      fname = fn.name
      to_name = t.name if t else "null"
      if fn.name not in mappings: mappings[fname] = {}
      fmap = mappings[fname]
      
      if from_name not in fmap: fmap[from_name] = []
    
      # find out if this function+params is in the mappings already
      p1 = json.dumps(fn.params, sort_keys=True)
    
      topic_map = None
      if from_name in fmap:
        for i in fmap[from_name]:
          p2 = json.dumps(i['params'], sort_keys=True)
          if p1 == p2:
            topic_map = i
            break
      if topic_map is None:
        topic_map = { "params": fn.params, "outputs": [] }
        fmap[from_name].append(topic_map)
      
      # find out if the output topic set exists already
      output_set = { "default": to_name }
      t1 = json.dumps(output_set, sort_keys=True)
      found_output_set = False
      for out in topic_map['outputs']:
        t2 = json.dumps(out, sort_keys=True)
        if t1 == t2:
          found_output_set = True
          break
      
      if not found_output_set: topic_map['outputs'].append({ "default": to_name })

    return mappings


def update_mappings(mappings):
    global apps
    # delete all current mappings
    res = apps.delete_many({})
    print(res)
    print(res.deleted_count)

    # insert all mappings from parameter
    for fname, applications in mappings.items():
      res = apps.insert_one({ "fname": fname, "applications": applications })
      print(res)


@app.route('/')
def index():
    with open('public/index.html') as f:
        return f.read()


@app.route('/function_list')
def function_list():
    names = [ r['name'] for r in coll.find({}) ]
    names += [ r['name'] for r in processes.find({}) ]
    return names


@app.route('/read/<fname>')
def readfn(fname):
    c = processes if fname.startswith('process:') else coll
    rec = c.find_one({ 'name': fname })
    return jsonify({ 'code': rec['code'] })


@app.route('/write/<fname>', methods=['POST'])
def writefn(fname):
    code = request.json['code']
    print("writing", code)
    c = processes if fname.startswith('process:') else coll
    c.replace_one({'name': fname}, {'name': fname, 'code': code})
    if fname.startswith('process:'):
      mappings = reprocess_mappings()
      update_mappings(mappings)
    return {'success': True}


@app.route('/create/<fname>', methods=['POST'])
def createfn(fname):
    if fname.startswith('process:'):
      processes.insert_one({'name': fname, 'code': ''})
      return {'success': True}
    else:
      coll.insert_one({'name': fname, 'code': ''})
      kube_submission = yaml.safe_load(new_deployment_tpl.format(deployment_name=fname.replace("_","-"), function_name=fname))
      config.load_incluster_config()
      v1 = client.AppsV1Api()
      resp = v1.create_namespaced_deployment(body=kube_submission, namespace="default")
      return {'success': True}


@app.route('/delete/<fname>', methods=['POST'])
def deletefn(fname):
    if fname.startswith('process:'):
      processes.delete_one({'name': fname})
      return {'success': True}

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
    app.run(host='0.0.0.0', port=3006)


