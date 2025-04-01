from rmr_config.simple_config import Config
from rmr_config.state_manager import StateManager
import os
import sys
import ast
import json
from datetime import datetime
from pathlib import Path

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
section_name = "model_scoring"

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
working_path = config.get('section_name', 'working_path')
params_path = config.get('section_name', 'params_path')
section_name = config.get('section_name', 'section_name')
model_version_path = config.get('section_name', 'model_version_path')
exported_model_base = config.get('section_name', 'exported_model_base')
m_local_folder = config.get('section_name', 'm_local_folder')
m_gcp_folder = config.get('section_name', 'm_gcp_folder')
oot_data_path = config.get('section_name', 'oot_data_path')
eval_path = config.get('section_name', 'eval_path')
mo_name = config.get('section_name', 'mo_name')
gcp_project = config.get('section_name', 'gcp_project')
dataproc_config = config.get('section_name', 'dataproc_config')
eval_result_path = config.get('section_name', 'eval_result_path')
log_file = config.get('section_name', 'log_file')
bigquery_table_uri = config.get('section_name', 'bigquery_table_uri')

# Dependencies from Previous Sections
# Previous section: model_packaging
# Edge Attributes from DAG
tf_model_path = config.get('model_packaging', 'tf_model_path')

# === Research Code ===
from rmr_config.simple_config import Config
from automation_utils.gcp.GSUtil import GSUtilHelper
from model_automation.utils.rmr import run_cmd
from model_automation.gcp import dataproc_config
from aml import cloud_v1 as cloud
import os
import sys
import ast
from datetime import datetime
import pickle

username = os.environ['NB_USER']
params_path = os.path.join(working_path, 'config')
config = Config(params_path)

# set working directory
os.chdir(working_path)
if not config:
    raise ValueError('config is not correctly setup')

section_name = "oot_data_scoring"

with open(os.path.join(working_path, '_current_model_version'), "rb") as f:
    model_version = pickle.load(f)

model_version_base = os.path.join(working_path, 'artifacts', model_version)
exported_model_base = os.path.join(model_version_base, 'exported_models')
exported_model_base

# define function run on gcp
def oot_data_eval(oot_data_path, eval_result_path, m_file_list, score_list, keep_cols=[]):
    from pyScoring.model import ModelScorer
    from pyScoring import UMEModel
    from automation_utils.gcp.GSUtil import GSUtilHelper
    import os
    import sys
    from py_dpu import load_parquet

    oot_df = load_parquet(spark, oot_data_path)
    local_m_path = []
    for file_path in m_file_list:
        model_name = file_path.split('/')[-1]
        GSUtilHelper.cp(file_path, f'/tmp/model_spec/{model_name}')
        local_m_path.append(f'/tmp/model_spec/{model_name}')
    scorer = ModelScorer(spark, validate=False)
    eval_df = scorer.create_score_df(input_df=oot_df, mfile_paths=local_m_path, outputs=score_list)
    if keep_cols:
        for model_path, outputs in zip(local_m_path, score_list):
            model_name = UMEModel(model_path).name
            keep_cols += [f"{model_name}_{score}" for score in outputs]
        eval_df = eval_df.select(*keep_cols)
    eval_df.coalesce(100).write.parquet(eval_result_path, mode="overwrite")

mo_name = config.get('general', 'mo_name')
from pyScoring import UMEModel

m_gcp_path_list = []
score_list = []

for file_name in os.listdir(m_local_folder):
    if not file_name.endswith(".m"):
        continue
    m_local_path = os.path.join(m_local_folder, file_name)
    model_spec = UMEModel(m_local_path)
    score_list.append(model_spec.outputs)
    m_gcp_path = os.path.join(m_gcp_folder, file_name)
    m_gcp_path_list.append(m_gcp_path)

client = cloud.TrainingClient(gcp_project=gcp_project)
job_id = client.create_spark_job(
    func=oot_data_eval,
    packages_to_install=['automation_utils==0.3.0', 'pyScoring==0.8.0.1.post1', 'gcsfs', 'PyDPU==1.1.0', 'pyjnius<1.5.0'],
    custom_billing_tag=f"{mo_name}_{section_name}".lower(),
    oot_data_path=oot_data_path,
    eval_result_path=eval_path,
    m_file_list=m_gcp_path_list,
    score_list=score_list,
    **dataproc_config['large']
)

status = client.wait_job_for_completion(job_id, time_to_sleep=300)

file_name = job_id.split("/")[-1]
log_file = os.path.join(working_path, 'logs', f"{file_name}.log")
with open(log_file, 'w') as f:
    f.write(job_id + '\n')
    client.get_job_driver_logs(job_id, file=f)

print('Script initialized')