
text = """
@dfaas
def something:
	pass # do whatever


application = "asdf"

t_some_input->change_stuff->t_cool_output
t_some_input->change_stuff->t_lame_output
t_funny_input->change_stuff->t_better_output
"""


text = text.split("\napplication = ")[1]
lines = ("application = " + text).split("\n")
application_name = next(t for t in lines if t.startswith('application')).split("=")[1].strip().replace('"', '')
mappings = []
for line in lines:
	if '->' not in line:
		continue
	parts = line.split("->")
	if parts[0].startswith('t_'):
		input_topic = parts[0][2:]
		function = parts[1]
		if len(parts) == 3:
			output_topic = parts[2][2:]
	else:
		function = parts[0]
		output_topic = parts[1][2:]

	mappings.append({
		"function_application": application_name,
		"function_name": function,
		"input_topic": input_topic,
		"output_topics": { "default": output_topic }
	})

for m in mappings:
	print(m)
	# apps.updateOne(m)

