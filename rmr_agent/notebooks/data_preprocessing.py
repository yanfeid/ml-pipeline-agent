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
section_name = "data_preprocessing"

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
directory = config.get('section_name', 'directory')
parquet_files = config.get('section_name', 'parquet_files')
state_to_abbreviation = config.get('section_name', 'state_to_abbreviation')
categorical_features = config.get('section_name', 'categorical_features')
numeric_features = config.get('section_name', 'numeric_features')
sequence_features = config.get('section_name', 'sequence_features')
tokenizer_params = config.get('section_name', 'tokenizer_params')
chunk_size = config.get('section_name', 'chunk_size')
model_version_base = config.get('section_name', 'model_version_base')
exported_feature_transformer = config.get('section_name', 'exported_feature_transformer')
output_dir = config.get('section_name', 'output_dir')
rcvr_id_tokenizer_path = config.get('section_name', 'rcvr_id_tokenizer_path')
categorical_feature_encoders_path = config.get('section_name', 'categorical_feature_encoders_path')
numerical_feature_scalars_path = config.get('section_name', 'numerical_feature_scalars_path')

# Dependencies from Previous Sections
# Previous section: feature_consolidation
# Edge Attributes from DAG
gs = config.get('feature_consolidation', 'gs')

# === Research Code ===
import pickle
from tqdm import tqdm
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.preprocessing.text import Tokenizer
from itertools import chain

today_date = datetime.now().date().strftime("%Y%m%d")
model_version = "din_" + str(today_date)
model_version_base = os.path.join('../artifacts/', model_version)
if not os.path.exists(model_version_base):
    os.mkdir(model_version_base)
exported_feature_transformer = os.path.join(model_version_base, 'exported_feature_transformer')
if not os.path.exists(exported_feature_transformer):
    os.mkdir(exported_feature_transformer)
with open('../_current_model_version', 'wb') as f:
    pickle.dump(model_version, f)

categorical_feature_encoders = {}
numerical_feature_scalars = {}
dfs = []

for file in tqdm(parquet_files, total=len(parquet_files)):
    file_path = os.path.join(directory, file)
    f = pd.read_parquet(file_path)
    dfs.append(f)

data = pd.concat(dfs, ignore_index=True)
state_map = {}

for state in np.unique(data['sndr_prmry_addr_state'].values).tolist():
    if len(state) > 2 and state.upper() in state_to_abbreviation:
        state_map[state.upper()] = state_to_abbreviation[state.upper()]

def clean_states(x):
    if len(x) == 2:
        return x.upper()
    elif x.upper() in state_map:
        return state_map[x.upper()]
    else:
        return '#'

data['sndr_prmry_addr_state'] = data['sndr_prmry_addr_state'].apply(clean_states)
lbe = LabelEncoder()
data['sndr_prmry_addr_state'] = lbe.fit_transform(data['sndr_prmry_addr_state'].values)
state_encoder_dict = {}
labels = lbe.transform(lbe.classes_)

for i in range(len(lbe.classes_)):
    state_encoder_dict[lbe.classes_[i]] = labels[i]

for state in state_map:
    state_encoder_dict[state] = lbe.transform([state_map[state]])[0]

categorical_feature_encoders['sndr_prmry_addr_state'] = state_encoder_dict

for feat in ['sndr_consu_engagmnt_seg_key', 'sndr_ebay_member_y_n', 'gender', 'sndr_prmry_cc_type_code', 'sndr_consu_age_band_key', 'sndr_consu_dmgrphc_seg_key']:
    lbe = LabelEncoder()
    data[feat] = lbe.fit_transform(data[feat].values)
    labels = lbe.transform(lbe.classes_)
    encoder_dict = {}
    for i in range(len(lbe.classes_)):
        encoder_dict[lbe.classes_[i]] = labels[i]
    categorical_feature_encoders[feat] = encoder_dict

for feat in tqdm(numeric_features, total=len(numeric_features)):
    scaler = StandardScaler()
    data[feat] = scaler.fit_transform(data[feat].values.reshape(-1, 1)).reshape(-1)
    numerical_feature_scalars[feat] = {'mean': scaler.mean_[0], 'std': np.sqrt(scaler.var_[0])}

data['sndr_most_recent_100_merch_category'].replace(['0'], pd.NA, inplace=True)
data['sndr_most_recent_100_merch_category'].fillna('', inplace=True)
df_seq = data['sndr_most_recent_100_merch_category'].apply(lambda x: [] if not x else list(map(int, x.split(','))))
df_pad = pad_sequences(df_seq, maxlen=100, truncating='pre', padding='pre', value=0)
data['hist_gpt_1st_category_l2_index'] = df_pad.tolist()

data['sndr_most_recent_100_merch_list'].replace(['0'], pd.NA, inplace=True)
data['sndr_most_recent_100_merch_list'].fillna('', inplace=True)
rcvr_id_tokenizer = Tokenizer(num_words=1000, oov_token='<OOV>')
rcvr_id_tokenizer.fit_on_texts(data['sndr_most_recent_100_merch_list'])
df_seq = rcvr_id_tokenizer.texts_to_sequences(data['sndr_most_recent_100_merch_list'])
df_pad = pad_sequences(df_seq, maxlen=100, truncating="pre", padding="pre", value=0)
data['token'] = df_pad.tolist()
data.rename(columns={'token': 'hist_rcvr_id'}, inplace=True)

for feat in ['rcvr_id']:
    z_seq = rcvr_id_tokenizer.texts_to_sequences(data[feat])
    z_seq = list(chain.from_iterable(z_seq))
    data[feat] = z_seq

data.drop(['sndr_most_recent_100_merch_list', 'sndr_most_recent_100_merch_category'], axis=1, inplace=True)

def write_chunk_to_parquet(df_chunk, chunk_index, output_dir):
    filename = os.path.join(output_dir, f'part_{chunk_index}.parquet')
    df_chunk.to_parquet(filename, index=False)

os.makedirs(output_dir, exist_ok=True)
num_chunks = (len(data) // chunk_size) + 1

for i in range(num_chunks):
    start_idx = i * chunk_size
    end_idx = (i + 1) * chunk_size
    df_chunk = data[start_idx:end_idx]
    write_chunk_to_parquet(df_chunk, i, output_dir)

export_path = os.path.join(exported_feature_transformer, 'rcvr_id_tokenizer')
with open(export_path, 'wb') as f:
    pickle.dump(rcvr_id_tokenizer, f)

export_path = os.path.join(exported_feature_transformer, 'categorical_feature_encoders')
with open(export_path, 'wb') as f:
    pickle.dump(categorical_feature_encoders, f)

export_path = os.path.join(exported_feature_transformer, 'numerical_feature_scalars')
with open(export_path, 'wb') as f:
    pickle.dump(numerical_feature_scalars, f)

print('Script initialized')