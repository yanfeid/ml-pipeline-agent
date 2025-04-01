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
section_name = "bigquery_table_creation"

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
driver_oot_txn_365d_table = config.get(section_name, 'driver_oot_txn_365d_table')
driver_oot_txn_save_365d_table = config.get(section_name, 'driver_oot_txn_save_365d_table')
mlv2_gpt_similar_map_snapshot_table = config.get(section_name, 'mlv2_gpt_similar_map_snapshot_table')
mlv2_gpt_similar_map_snapshot_1_table = config.get(section_name, 'mlv2_gpt_similar_map_snapshot_1_table')
driver_oot_txn_save_365d_similar_table = config.get(section_name, 'driver_oot_txn_save_365d_similar_table')
driver_oot_txn_save_365d_similar_dedup_table = config.get(section_name, 'driver_oot_txn_save_365d_similar_dedup_table')
driver_oot_two_tower_similar_score_table = config.get(section_name, 'driver_oot_two_tower_similar_score_table')
driver_oot_hueristic_model_comparison_table = config.get(section_name, 'driver_oot_hueristic_model_comparison_table')