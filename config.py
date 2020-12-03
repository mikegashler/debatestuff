import json
import os
import sys

config = {
    'use_mongo': False,
    'mongo_url': 'mongodb://localhost',
    'mongo_port': 27017,
}

# Load config.json and override the default settings (above) with its values
if len(sys.argv) > 1:
    os.chdir(sys.argv[1])
print('__________________________________________________')
print(f'Starting up in dir: {os.getcwd()}')
print('(Note: The starting directory can be specified with the first argument to the application.')
print('That is the only command-line argument. All other settings are specified in config.json,')
print('which should be found in that directory, along with other required files.)')
if os.path.exists('config.json'):
    with open('config.json', mode='rb') as file:
        filecontents = file.read()
    overrides = json.loads(filecontents)
    config.update(overrides)
else:
    print('Warning: No config.json file was found. Using defaults.')
