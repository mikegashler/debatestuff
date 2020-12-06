import json
import os
import sys

config = {
    'use_mongo': False, # Override with True to store data in a Mongo database instead of a flat file
    'mongo_url': 'mongodb://localhost', # Only used if use_mongo is True
    'mongo_port': 27017, # Only used if use_mongo is True
    'bootstrap': # Values to pre-populate an empty database. (Only a root category is really needed. The rest is just fluff.)
    { 'type': 'cat', 'text': 'Everything', 'children': [
        { 'type': 'cat', 'text': 'Politics', 'children': [
            { 'type': 'op', 'account': 0, 'text': 'Republicans and Democrats are just two sides of the same party. One wants to spend more money on law enforcement and military might. The other wants to spend more money on social welfare. But ultimately they both want bigger government. We need to starve the beast!', 'children': [
            ] },
            { 'type': 'op', 'account': 1, 'text': 'The 2020 election was rigged! Everyone I know voted for Donald Trump.', 'children': [
                { 'type': 'pod', 'account': 1, 'text': 'Open discussion', 'children': [
                    { 'type': 'rp', 'account': 2, 'text': 'So what? Do you think you know a statistically significant portion of the population?', 'children': [
                    ] },
                ] },
            ] },
        ] },
        { 'type': 'cat', 'text': 'Science / Technology / Future', 'children': [
            { 'type': 'op', 'account': 3, 'text': 'I think robots are going to kill off humanity in the next 50 years because technology is advancing at an exponential rate. People suck at comprehending how rapidly exponential growth accelerates. One day, BAM!, and it hits you.', 'children': [
                { 'type': 'pod', 'account': 3, 'text': 'Open discussion', 'children': [
                    { 'type': 'rp', 'account': 4, 'text': 'Maybe. But people have been saying that for decades. How come it never seems to happen?', 'children': [
                        { 'type': 'rp', 'account': 3, 'text': 'If you look at a curve of exponential growth it seems flat for a long time ...until it hockey-sticks up.', 'children': [
                            { 'type': 'rp', 'account': 4, 'text': 'Okay, but how do you know technology is following an exponential curve?', 'children': [
                            ] },
                        ] }
                    ] },
                ] },
            ] },
        ] },
        { 'type': 'cat', 'text': 'Theology / Morality', 'children': [
        ] },
        { 'type': 'cat', 'text': 'Entertainment', 'children': [
            { 'type': 'op', 'account': 1, 'text': 'Who has a more tragic back-story, Darth Vader or Batman?', 'children': [
                { 'type': 'pod', 'account': 1, 'text': 'Open discussion', 'children': [
                    { 'type': 'rp', 'account': 5, 'text': 'Who cares? What a stupid debate topic.', 'children': [
                    ] },
                    { 'type': 'rp', 'account': 6, 'text': 'Batman, definitely. Darth Vader screwed up his own life, so his story is not really even tragic.', 'children': [
                    ] },
                ] },
            ] },
        ] },
        { 'type': 'cat', 'text': 'Testing / Other', 'children': [
        ] },
    ] },
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
