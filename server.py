import flask
import traceback
from flask import Flask, jsonify, request, send_file
import pymongo
import os
import yaml
from kubernetes import client, config
import subprocess
import io
import json
from dfaal import parse_applications
import kafka
import datetime
from contextlib import redirect_stdout

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
      #print(f, fn, t)
      #print(fn)
      from_name = f.name.replace(":","") if f else "null"
      fname = fn.name
      to_name = t.name.replace(":","") if t else "null"
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

    # insert all mappings from parameter
    for fname, applications in mappings.items():
      res = apps.insert_one({ "fname": fname, "applications": applications })


@app.route('/')
def index():
    with open('public/index.html') as f:
        return f.read()


@app.route('/themes/<theme_id>')
def theme(theme_id):
    with open('public/themes/prism-' + theme_id + '.css') as f:
        return f.read()


@app.route('/function_list')
def function_list():
    dbnames = [ r['name'] for r in coll.find({}) ]
    dbnames += [ r['name'] for r in processes.find({}) ]

    try:
      config.load_incluster_config()
      v1 = client.AppsV1Api()
    except:
      pass
    replica_counts = {}
    try:
      for b in v1.list_namespaced_deployment('default').items:
        if not b.metadata.name.startswith('dfaas-'):
          continue
        if b.metadata.name == 'dfaas-webide-deployment':
          continue
        names = [ e.value for e in b.spec.template.spec.containers[0].env if e.name == 'FUNCTION_NAME' ]
        if len(names) > 0:
          name = names[0]
          replica_counts[name] = (b.status.available_replicas or 0)
    except:
      pass

    for name in dbnames:
        if name not in replica_counts:
            replica_counts[name] = 0
    
    return replica_counts

@app.route('/read/<fname>')
def readfn(fname):
    c = processes if fname.startswith('process:') else coll
    rec = c.find_one({ 'name': fname })
    c.replace_one({'name': fname}, {'name': fname, 'code': rec['code'], 'last_update': datetime.datetime.now().timestamp() })
    return jsonify({ 'code': rec['code'] })


@app.route('/write/<fname>', methods=['POST'])
def writefn(fname):
    code = request.json['code']
    c = processes if fname.startswith('process:') else coll
    c.replace_one({'name': fname}, {'name': fname, 'code': code, 'last_update': datetime.datetime.now().timestamp() })
    if fname.startswith('process:'):
      f = io.StringIO()
      with redirect_stdout(f):
        try:
          mappings = reprocess_mappings()
          update_mappings(mappings)
        except Exception as e:
          print(traceback.format_exc())
      s = f.getvalue()
      print(s)
      return {'stdout': s}
    return {'success': True}


@app.route('/create/<fname>', methods=['POST'])
def createfn(fname):
    if fname.startswith('process:'):
      processes.insert_one({'name': fname, 'code': ''})
      return {'success': True}
    else:
      coll.insert_one({'name': fname, 'code': '@dfaas\ndef ' + fname + '(rec):\n    return rec\n\n'})
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


@app.route('/stdout/<fnname>')
def stdout(fnname):
    #return {"stdouts":[{"stdout":"asdf\n","tstamp":1687981427.897007},{"stdout":"asdf\n","tstamp":1687981427.897456},{"stdout":"asdf\n","tstamp":1687981427.897657},{"stdout":"asdf\n","tstamp":1687981427.897852},{"stdout":"asdf\n","tstamp":1687981427.898045},{"stdout":"asdf\n","tstamp":1687981432.913297},{"stdout":"asdf\n","tstamp":1687981432.913751},{"stdout":"asdf\n","tstamp":1687981432.913994},{"stdout":"asdf\n","tstamp":1687981432.91423},{"stdout":"asdf\n","tstamp":1687981432.91447},{"stdout":"Traceback (most recent call last):\n  File \"/home/app/gowalla.py\", line 152, in <module>\n    ret = function(rec, **application['params'])\n  File \"<string>\", line 4, in add_field\nException: its exceptin\n\n","tstamp":1687981437.919217},{"stdout":"Traceback (most recent call last):\n  File \"/home/app/gowalla.py\", line 152, in <module>\n    ret = function(rec, **application['params'])\n  File \"<string>\", line 4, in add_field\nException: its exceptin\n\n","tstamp":1687981437.919816},{"stdout":"Traceback (most recent call last):\n  File \"/home/app/gowalla.py\", line 152, in <module>\n    ret = function(rec, **application['params'])\n  File \"<string>\", line 4, in add_field\nException: its exceptin\n\n","tstamp":1687981437.921217},{"stdout":"Traceback (most recent call last):\n  File \"/home/app/gowalla.py\", line 152, in <module>\n    ret = function(rec, **application['params'])\n  File \"<string>\", line 4, in add_field\nException: its exceptin\n\n","tstamp":1687981437.922535},{"stdout":"Traceback (most recent call last):\n  File \"/home/app/gowalla.py\", line 152, in <module>\n    ret = function(rec, **application['params'])\n  File \"<string>\", line 4, in add_field\nException: its exceptin\n\n","tstamp":1687981437.926271}]}
    if fnname.startswith('process:'):
      return ''

    topic = fnname + '_stdout'
    
    consumer = kafka.KafkaConsumer(bootstrap_servers=[ os.environ['KAFKA_ADDRESS'] ])
    
    dtstmp = datetime.datetime.now()-datetime.timedelta(minutes=10)
    
    month_ago = dtstmp.timestamp()
    topic_partition = kafka.TopicPartition(topic, 0)
    assigned_topic = [topic_partition]
    consumer.assign(assigned_topic)
    
    partitions = consumer.assignment()
    partition_to_timestamp = {part: int(month_ago * 1000) for part in partitions}
    end_offsets = consumer.end_offsets(list(partition_to_timestamp.keys()))
    
    mapping = consumer.offsets_for_times(partition_to_timestamp)
    msgs = []
    for partition, ts in mapping.items():
        if not ts:
           continue
        end_offset = end_offsets.get(partition)
        consumer.seek(partition, ts[0])
        for msg in consumer:
            value = json.loads(msg.value.decode('utf-8'))
            msgs.append(value)
            if msg.offset == end_offset - 1:
                consumer.close()
                break
    
    return { "stdouts": msgs[-1:-50:-1] }


@app.route('/fn_map')
def fn_map():
    level = request.args.get('level', 0)
    return "<body style='background-color:black; text-align:center; margin-top:50px;'><a href='/fn_map?level=" + str((int(level)+1)%2) + "'><img src='/fn_map.svg?level=" + str(level) + "' /></a></body>"


@app.route('/fn_map.svg')
def fn_map_svg():
    level = request.args.get('level', 0)
    mappings = reprocess_mappings()

    data = [ "digraph a {", "bgcolor=black" ]
    for fname, apps in mappings.items():
      for from_topic, mapps in apps.items():
        for mapp in mapps:
          params = []
          for k,v in mapp['params'].items():
            if isinstance(v, str):
              params.append(f"{k}='{v}'")
              #params.append(f"'{v}'")
            else:
              params.append(f"{k}={v}")
              #params.append(f"{v}")
          params = "\n".join(params)

          for out in mapp['outputs']:
            if 'default' in out:
              to_topic = out['default']
              for t in [from_topic, to_topic]:
                if t == 'null':
                  continue
                if 'dyntopic_' in t:
                  data.append(f"\":{t}\" [style=filled color=lightblue label=\"\" shape=point]")
                else:
                  data.append(f"\":{t}\" [style=filled color=lightblue]")
              
              if level == '0':
                f = f"{fname}\n{params}"
              elif level == '1':
                f = fname
              else:
                f = fname
              data.append(f"\"{f}\" [style=filled color=darkseagreen1 shape=cylinder]")

              linecolor = 'gold'
              penwidth = 2.0
              if from_topic == 'null':
                data.append(f"\"{f}\"->\":{to_topic}\" [color={linecolor} penwidth={penwidth}]")
              elif to_topic == 'null':
                data.append(f"\":{from_topic}\"->\"{f}\" [color={linecolor} penwidth={penwidth}]")
              else:
                data.append(f"\":{from_topic}\"->\"{f}\"->\":{to_topic}\" [color={linecolor} penwidth={penwidth}]")
    data.append("}")

    p = subprocess.Popen(['dot', '-Tsvg'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p.stdin.write("\n".join(data).encode())
    p.stdin.flush()
    imgdata = p.communicate()[0]

    svg_io = io.BytesIO()
    svg_io.write(imgdata)
    svg_io.seek(0)
    return send_file(svg_io, mimetype='image/svg+xml')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002)


