from rmr_config.simple_config import Config
from rmr_config.state_manager import StateManager
import os
import sys
import ast
import json
from datetime import datetime
from pathlib import Path
from tensorflow.python.keras.models import save_model
from pyScoring.graph import Graph
from pyScoring.onnx.support.tf2.tf2_to_onnx import tf_model_to_onnx_node, tf_model_to_onnx_as_spec
from pyScoring.node import ReNameBuilder, LookupBuilder, ScalerBuilder
import pickle
import numpy as np
import onnxruntime as ort

if "working_path" not in globals():
    path = Path(os.getcwd())
    working_path = path.parent.absolute()

folder = os.getcwd()
username = os.environ['NB_USER']
params_path = os.path.join(working_path, 'config')
config = Config(params_path)
local_base_path = config.get("general", "local_output_base_path")
os.makedirs(local_base_path, exist_ok=True)

os.chdir(working_path)
if not config:
    raise ValueError('config is not correctly setup')

print(f'username={username}, working_path={working_path}')

section_name = "model_packaging"

mo_name = config.get('general', 'mo_name')
driver_dataset = config.get('general', 'driver_dataset')
dataproc_project_name = config.get('general', 'dataproc_project_name')
dataproc_storage_bucket = config.get('general', 'dataproc_storage_bucket')
gcs_base_path = config.get('general', 'gcs_base_path')
queue_name = config.get('general', 'queue_name')
check_point = config.get('general', 'check_point')
state_file = config.get('general', 'state_file')

categorical_feature_encoders = config.get('section_name', 'categorical_feature_encoders')
numerical_feature_scalars = config.get('section_name', 'numerical_feature_scalars')
onnx_spec_path = config.get('section_name', 'onnx_spec_path')
oot_scoring_directory = config.get('section_name', 'oot_scoring_directory')
onnx_model_path = config.get('section_name', 'onnx_model_path')
renamed_onnx_model_path = config.get('section_name', 'renamed_onnx_model_path')
prod_model_path = config.get('section_name', 'prod_model_path')
test_data_json_path = config.get('section_name', 'test_data_json_path')
onnx_output_path = config.get('section_name', 'onnx_output_path')

h5_model_path = config.get('model_training', 'h5_model_path')
tf_model_path = config.get('model_training', 'tf_model_path')

save_model(model, h5_model_path)
model.save(tf_model_path)

onnx_spec = tf_model_to_onnx_as_spec(
    tf_model=model,
    input_mappings={
        'hist_rcvr_id': [f'hist_rcvr_id_{i}' for i in range(1, 101)],
        'hist_gpt_1st_category_l2_index': [f'hist_gpt_1st_category_{i}' for i in range(1, 101)]
    },
    output_mappings={model.output.name[:-2]: 'out'}
)
assert len(onnx_spec.outputs) == 1
onnx_spec.save(onnx_spec_path)
onnx_spec

if not os.path.exists(oot_scoring_directory):
    os.mkdir(oot_scoring_directory)

file = onnx_model_path
rename_file = renamed_onnx_model_path

def is_ascii(s):
    try:
        str(s).encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

for cat_feat in categorical_feature_encoders:
    for key in categorical_feature_encoders[cat_feat].keys():
        categorical_feature_encoders[cat_feat] = {k: v for k, v in categorical_feature_encoders[cat_feat].items() if is_ascii(key)}

with open(numerical_feature_scalars, "rb") as f:
    numerical_feature_scalars = pickle.load(f)

g = Graph()
base_model_node, _, _ = tf_model_to_onnx_node(tf_model=model)
g.add_node(base_model_node[0])
node = ReNameBuilder('output', base_model_node[0].outputs[0]).build()
g.add_node(node)

for key in categorical_feature_encoders:
    node = LookupBuilder(
        key, f'{key}_raw',
        {str(k): v for k, v in categorical_feature_encoders[key].items()}
    ).set_default(0).build()
    g.add_node(node)

for key in numerical_feature_scalars:
    node = ScalerBuilder(
        f'{key}_scalar',
        [f'{key}_raw'],
        [key],
        [numerical_feature_scalars[key]['mean']],
        [1 / numerical_feature_scalars[key]['std']]
    ).build()
    g.add_node(node)

prod_model = g.generate_model_by_graph(model_name='din_prod', optimization=True)
prod_model.save(prod_model_path)

test_df = data[(data['cust_id'] == test_cust) & (data['run_date'] == test_date)]

test_data_local = {}
for feat in model.inputs:
    if feat.name in categorical_feature_encoders or feat.name in numerical_feature_scalars:
        test_data_local[feat.name + '_raw'] = [test_df[feat.name].values[i].tolist() for i in range(len(test_df))]
    else:
        test_data_local[feat.name] = [test_df[feat.name].values[i].tolist() for i in range(len(test_df))]

re = prod_model.predict(test_data_local)
inputs = [k for k in test_data_local.keys()]
test_data = {"data": {"names": inputs, "ndarray": [test_data_local[feat][0] for feat in inputs]}}

if not os.path.exists('./testdata'):
    os.mkdir('./testdata')

output_file = test_data_json_path
with open(output_file, 'w') as file:
    json.dump(test_data, file)

sess = ort.InferenceSession(onnx_output_path, providers=["CPUExecutionProvider"])
test_df = data[(data['cust_id'] == test_cust) & (data['run_date'] == test_date)]

test_data_tf = {}
for feat in model.inputs:
    test_data_tf[feat.name] = np.array([test_df[feat.name].values[i].tolist() for i in range(len(test_df))], dtype=np.float32)

test_data_onnx = {key: [[item] for item in value] for key, value in test_data_tf.items()}
test_data_onnx['hist_gpt_1st_category_l2_index'] = [item[0] for item in test_data_onnx['hist_gpt_1st_category_l2_index']]
test_data_onnx['hist_rcvr_id'] = [item[0] for item in test_data_onnx['hist_rcvr_id']]

result_tf = model.predict(test_data_tf)
results_ort = sess.run(None, test_data_onnx)
np.testing.assert_allclose(results_ort[0], result_tf, rtol=1e-5, atol=1e-5)
results_ort = sess.run(None, test_data_onnx)
test_data_tf

print('Script initialized')