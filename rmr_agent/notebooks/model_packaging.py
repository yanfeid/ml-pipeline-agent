from rmr_config.simple_config import Config
from rmr_config.state_manager import StateManager
import os, sys, ast, json
from datetime import datetime

if "working_path" not in globals():
    from pathlib import Path
    path = Path(os.getcwd())
    working_path = path.parent.absolute()

folder = os.getcwd()
username = os.environ['NB_USER']
params_path = os.path.join(working_path, 'config')
config = Config(params_path)
local_base_path = config.get("general","local_output_base_path")
os.makedirs(local_base_path, exist_ok=True)

# set working directory
os.chdir(working_path)
if not config:
    raise ValueError('config is not correctly setup')
                
print(f'username={username}, working_path={working_path}')
                    
# Section Name
section_name = "model_packaging"

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
trained_model_path = config.get('section_name', 'trained_model_path')
onnx_model_path = config.get('section_name', 'onnx_model_path')
oot_scoring_path = config.get('section_name', 'oot_scoring_path')
prod_model_path = config.get('section_name', 'prod_model_path')

# Dependencies from Previous Sections
# Previous section: model_training
# Edge Attributes from DAG
tf_model_path = config.get('model_training', 'tf_model_path')


# === Research Code ===
from tensorflow.python.keras.models import save_model
h5_model_path = os.path.join(local_base_path, 'din.h5')
save_model(model, h5_model_path)
tf_model_path = os.path.join(local_base_path, 'din_saved_model')
model.save(tf_model_path)
from pyScoring.graph import Graph
from pyScoring.onnx.support.tf2.tf2_to_onnx import tf_model_to_onnx_node, tf_model_to_onnx_as_spec
from pyScoring.node import ReNameBuilder, LookupBuilder, ScalerBuilder
onnx_spec = tf_model_to_onnx_as_spec(tf_model=model,
input_mappings={
'hist_rcvr_id': [f'hist_rcvr_id_{i}' for i in range(1, 101)],
'hist_gpt_1st_category_l2_index': [f'hist_gpt_1st_category_{i}' for i in range(1, 101)]
},
output_mappings={model.output.name[:-2]: 'out'})
assert(len(onnx_spec.outputs) == 1)

print('Script initialized')