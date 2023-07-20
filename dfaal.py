from parsimonious.grammar import Grammar
import base64

gram = """
graph = ws (entry ws)+ ws

entry      = (
                 ((function/topic) ws "->" ws entry)
               / ((function/topic) ws "->" ws entry_group)
               / (function/topic)
             )

entry_group  = (
                 ("{" ws (entry ws)+ ws "}" )
               / (topic ws "=" ws (entry))
               )


function   = (
                 (fn_name "(" ws (param ","? ws)* ")")
               / fn_name
             )

param      = fn_param ws ","* ws

param   = (
              (param_name ws "=" ws string)
            / (param_name ws "=" ws string)
            / (param_name ws "=" ws number)
            / (param_name ws "=" ws var_name)
          )

var_name   = ~"[A-Za-z_][A-Za-z0-9_]*"

param_name   = ~"[A-Za-z_][A-Za-z0-9_]*"
string     = (
                 ( '"' ~"[\+\-\.#A-Za-z0-9_\.:/\?=\[\] \*{}]*" '"' )
               / ( "'" ~"[\+\-\.#A-Za-z0-9_\.:/\?=\[\] \*{}]*" "'" )
             )
fn_name    = ~"[A-Za-z_][A-Za-z0-9_]*"

topic      = ~":[A-Za-z_][A-Za-z0-9_]*"

arrow      = "->"
number     = ~"[0-9\.]*"
ws         = (~r"[\\n\s]*")
"""

def getGrammar():
  return Grammar(gram)

grammar = getGrammar()

class Graph:
  def __init__(self): self.entries = []
  def __repr__(self): return "\n".join(str(e) for e in self.entries)
class Function:
  def __init__(self): self.params = {}
  def __repr__(self): return self.name + '(' + ','.join(k+'='+str(("'" + v + "'") if isinstance(v,str) else v) for k,v in self.params.items()) + ')'
class Param:
  def __init__(self): self.name = None; self.value = None
  def __repr__(self): return f"{self.name}={self.value}"
class Topic:
  def __init__(self): self.name = None
  def __repr__(self): return self.name
class Entry:
  def __init__(self): self.val = None; self.n = None
  def __repr__(self):
    if self.val and self.n: return f"{self.val}->{self.n}"
    if self.val: return str(self.val)
    if self.n: return str(self.n)
    return "!!!"
class EntryGroup:
  def __init__(self): self.outs = []
  def __repr__(self): return "{" + " :: ".join(str(o) for o in self.outs) + "}"
 
def p(m, n, s):
  return
  if n.expr.name in ['','ws']: return
  print(m + ' ' + ".".join(a.expr.name for a in s+[n] if a.expr.name not in ['','ws']) + ' => ' + n.text.strip())


def walk_param(n, param, s=[]):
  p('param', n, s)
  if n.expr.name == 'param_name':
    param.name = n.text.strip()
  if n.expr.name == 'string':
    param.value = n.text[1:-1]
  if n.expr.name == 'number':
    param.value = float(n.text)
  for c in n.children: walk_param(c, param, s+[n])

def walk_topic(n, t, s=[]):
  p('topic', n, s)
  return

def walk_function(n, f, s=[]):
  p('funct', n, s)
  if n.expr.name == 'fn_name':
    f.name = n.text.strip()
  if n.expr.name == 'param':
    param = Param()
    walk_param(n, param, s+[n])
    f.params[param.name] = param.value
  for c in n.children: walk_function(c, f, s+[n])

def walk_entry_group(n, eg, s=[]):
  p('group', n, s)
  if n.expr.name == 'entry':
    e = Entry()
    eg.outs.append(e)
    return walk_entry(n, e, s+[n])
  for c in n.children: walk_entry_group(c, eg, s+[n])

def walk_entry(n, e, s=[]):
  # walk_entry should parse the entry (function or topic)
  # and also parse all nested entries
  p('entry', n, s)
  if n.expr.name == 'entry':
    e.n = Entry()
    for c in n.children: # we need this for loop because entries may contain other entries immediately
      walk_entry(c, e.n, s+[c])
    return
  if n.expr.name == 'entry_group':
    e.n = EntryGroup()
    return walk_entry_group(n, e.n, s+[n])
  if n.expr.name == 'function':
    f = Function()
    e.val = f
    return walk_function(n, f, s+[n])
  if n.expr.name == 'topic':
    t = Topic()
    t.name = n.text
    e.val = t
    return
  for c in n.children: walk_entry(c, e, s+[n])

def walk_graph(n, g, s=[]):
  p('graph', n, s)
  if n.expr.name == 'entry':
    e = Entry()
    g.entries.append(e)
    for c in n.children:
      walk_entry(c, e, s+[c])
    return
  for c in n.children: walk_graph(c, g, s+[n])

def walk_entries(n, s=[]):
  if n.expr.name == 'graph':
    g = Graph()
    for a in n.children:
      walk_graph(a, g, s+[n])
    return g
  for c in n.children: walk_entries(c, s+[n])


def walk(n, stack=[]):
  if n.expr.name not in ['','ws','e']:
    print(' __ [' + ".".join(a.expr.name for a in stack if a.expr.name not in ['','ws']) + "] ::: (" + n.expr.name + ") " + " ".join(nn.strip() for nn in n.text.split('\n')))
  stack.append(n)
  for a in n.children: walk(a, stack)
  stack.pop()







def generateDynamicTopic(a, b):
  e = Entry()
  e.val = Topic()
  e.val.name = ':' + f"{a.val}__to__{b.val}".replace("(","").replace(")","")\
    .replace(",","_").replace("=","_").replace("->","_").replace(".","_")
  e.val.name = ':dyntopic_' + base64.b64encode(e.val.name.encode()).decode().replace("=","")
  e.n = b
  return e

def generateTopicCopy(a, b):
  e = Entry()
  e.val = Function()
  e.val.name = 'topic_copy'
  e.n = b
  return e


def is_f(e): return e and isinstance(e, Entry) and isinstance(e.val, Function)
def is_t(e): return e and isinstance(e, Entry) and isinstance(e.val, Topic)
def hash_function_application(app): return "__".join(str(i) for i in app)

def _parse_applications(entry, last, lastlast, applications):
  if isinstance(entry, Graph):
    for i in entry.entries:
      _parse_applications(i, None, None, applications)
    return applications

  if isinstance(entry, EntryGroup):
    for i in entry.outs:
      if i.val is None: i = i.n # this is a hack because i have nested entry records for some reason
      _parse_applications(i, last, lastlast, applications)

  if isinstance(entry, Entry):
    #print(lastlast and lastlast.val, last and last.val, entry and entry.val)

    # ensure functions follow topics and topics follow functions
    if is_f(last) and is_f(entry): entry = generateDynamicTopic(last, entry)
    if is_t(last) and is_t(entry): entry = generateTopicCopy(last, entry)

    # find any function-applications in the last, current, and next entries
    if is_t(lastlast) and is_f(last) and is_t(entry):
      applications.append((lastlast.val, last.val, entry.val))
    else:
      if not lastlast and is_f(last) and is_t(entry):
        applications.append((None, last.val, entry.val))
      
      if not entry.n and is_t(last) and is_f(entry):
        applications.append((last.val, entry.val, None))


    if entry.n:
      _parse_applications(entry.n, entry, last, applications)

  return applications

def parse_applications(sample):
  g = grammar.parse(sample)
  graph = walk_entries(g)
  return _parse_applications(graph, None, None, [])



