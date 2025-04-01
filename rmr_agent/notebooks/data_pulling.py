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

# Set working directory
os.chdir(working_path)
if not config:
    raise ValueError('config is not correctly setup')

print(f'username={username}, working_path={working_path}')

# Section Name
section_name = "data_pulling"

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
stage = config.get('section_name', 'stage')
seq_num = config.get('section_name', 'seq_num')
is_prod = config.get('section_name', 'is_prod')
job_name = config.get('section_name', 'job_name')
group_name = config.get('section_name', 'group_name')
model_name = config.get('section_name', 'model_name')
model_owner = config.get('section_name', 'model_owner')
description = config.get('section_name', 'description')
manager = config.get('section_name', 'manager')
on_gcp = config.get('section_name', 'on_gcp')
gcp_project_id = config.get('section_name', 'gcp_project_id')
gcs_bucket_name = config.get('section_name', 'gcs_bucket_name')
bq_materialization_project = config.get('section_name', 'bq_materialization_project')
bq_materialization_dataset = config.get('section_name', 'bq_materialization_dataset')
driver_loc = config.get('section_name', 'driver_loc')
variables = config.get('section_name', 'variables')
split_ratio = config.get('section_name', 'split_ratio')
num_of_splits = config.get('section_name', 'num_of_splits')
data_loc = config.get('section_name', 'data_loc')

# Dependencies from Previous Sections
# Previous section: driver_creation
# Edge Attributes from DAG
driver_simu_consumer = config.get('driver_creation', 'driver_simu_consumer')

# === Research Code ===
# %reload_ext cloudmagics.bigquery
# %config PPMagics.domain="ccg24-hrzana-gds-pacman"
# %config PPMagics.autolimit = 0
import aml.cloud_v1 as cloud
cloud.notebook.authenticate_user()
import json
import os
import sys
os.environ["PYMLS_DEV_ENABLE"] = 'false'
# %ppauth
# !gsutil rm -r gs://pypl-bkt-rsh-row-std-gds-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_driver_simu_consumer
# !gsutil rm -r gs://pypl-bkt-rsh-row-std-gds-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_driver_simu_consumer_varmart
# %%ppbq
EXPORT DATA
OPTIONS (
    uri = 'gs://pypl-bkt-rsh-row-std-gds-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_driver_simu_consumer/part*.parquet',
    format = 'parquet',
    overwrite = true
)
AS (
    SELECT *
    FROM pypl-bods.gds_pacman_prod.ql_store_rmr_driver_simu_consumer
);

import json
import os
import sys
import datetime
from pymls.component import Fetcher

today = datetime.date.today()
user = os.environ["USER"]
fetcher = Fetcher(stage, seq_num, is_prod=is_prod)
fetcher.job_name = job_name
fetcher.group_name = group_name
fetcher.model_name = model_name
fetcher.model_owner = model_owner
fetcher.description = description
fetcher.manager = manager

# -------- Component specific configs start here --------
# GCP Settings
fetcher.on_gcp = on_gcp
fetcher.gcp_project_id = gcp_project_id
fetcher.gcs_bucket_name = gcs_bucket_name
fetcher.bq_materialization_project = bq_materialization_project
fetcher.bq_materialization_dataset = bq_materialization_dataset
fetcher.driver_loc = driver_loc
fetcher.data_loc = data_loc
fetcher.variables = variables
# Specify your split ratio here. Should add up to 1.0
fetcher.split_ratio = split_ratio
fetcher.num_of_splits = num_of_splits
# default workspace is /home/[user]/mls_workspace
# fetcher.workspace =
# -------- Component specific configs end here --------
res = fetcher.run()

# %%ppbq
CREATE OR REPLACE EXTERNAL TABLE pypl-bods.gds_pacman_prod.ql_store_rmr_driver_simu_consumer_varmart_external
OPTIONS (
    format = "PARQUET",
    uris = ["gs://pypl-bkt-rsh-row-std-gds-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_driver_simu_consumer_varmart/all/parquet/part*"]
)

print('Script initialized')