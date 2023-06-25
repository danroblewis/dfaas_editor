import pymongo
import os

conn = pymongo.MongoClient(os.environ['MONGODB_HOST'], int(os.environ['MONGODB_PORT']), username=os.environ['MONGODB_USER'], password=os.environ['MONGODB_PASSWORD'])
functions = conn.test.dfaas_functions
function_applications = conn.test.dfaas_function_applications

change_stuff_function = {
    "name": "change_stuff",
    "input_topic": "default",
    "output_topics": {
        "default": ""
    },
    "code": "# todo"
}
functions.insert_many([change_stuff_function])

some_to_cool_mapping = {
    "function_application": "sample_application",
    "function_name": "change_stuff",
    "input_topic": "some_input",
    "output_topics": {
        "default": "cool_output"
    }
}
some_to_lame_mapping = {
    "function_application": "sample_application",
    "function_name": "change_stuff",
    "input_topic": "some_input",
    "output_topics": {
        "default": "lame_output"
    }
}
funny_to_better_mapping = {
    "function_application": "sample_application",
    "function_name": "change_stuff",
    "input_topic": "funny_input",
    "output_topics": {
        "default": "better_output"
    }
}
function_applications.insert_many([some_to_cool_mapping, some_to_lame_mapping, funny_to_better_mapping])

