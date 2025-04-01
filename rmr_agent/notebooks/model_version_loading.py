from rmr_config.simple_config import Config
from rmr_config.state_manager import StateManager
import os
import sys
import ast
import json
from datetime import datetime
from pathlib import Path

# gsutil authentication
%ppauth

if "working_path" not in globals():
    path = Path(os.getcwd())
    working_path = path.parent.absolute()

folder = os.getcwd()
username = os.environ['NB_USER']
params_path = os.path.join(working_path, 'config')
config = Config(params_path)
local_base_path = config.get("general", "local_output_base_path")
os.makedirs(local_base_path, exist_ok=True)

# set working directory
os.chdir(working_path)
if not config:
    raise ValueError('config is not correctly setup')

print(f'username={username}, working_path={working_path}')

# Section Name
section_name = "model_version_loading"

# General Parameters (from environment.ini)
mo_name = config.get('general', 'mo_name')
driver_dataset = config.get('general', 'driver_dataset')
dataproc_project_name = config.get('general', 'dataproc_project_name')
dataproc_storage_bucket = config.get('general', 'dataproc_storage_bucket')
gcs_base_path = config.get('general', 'gcs_base_path')
queue_name = config.get('general', 'queue_name')
check_point = config.get('general', 'check_point')
state_file = config.get('general', 'state_file')

# Section-Specific Parameters (from solution.ini)
model_version_path = config.get(section_name, 'model_version_path')
model_version_base = config.get(section_name, 'model_version_base')
exported_eval_readout_base = config.get(section_name, 'exported_eval_readout_base')