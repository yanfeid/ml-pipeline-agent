## gsutil authentication
%ppauth


from rmr_config.simple_config import Config
from rmr_config.state_manager import StateManager
import os
import sys
import ast
import json
from datetime import datetime


if "working_path" not in globals():
    from pathlib import Path
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
section_name = "model_training"


# General Parameters 
mo_name = config.get('general', 'mo_name')
driver_dataset = config.get('general', 'driver_dataset')
dataproc_project_name = config.get('general', 'dataproc_project_name')
dataproc_storage_bucket = config.get('general', 'dataproc_storage_bucket')
gcs_base_path = config.get('general', 'gcs_base_path')
queue_name = config.get('general', 'queue_name')
check_point = config.get('general', 'check_point')
state_file = config.get('general', 'state_file')


# Section-Specific Parameters (from solution.ini)
model_version_base = config.get(section_name, 'model_version_base')
exported_feature_transformer = config.get(section_name, 'exported_feature_transformer')
numeric_names = config.get(section_name, 'numeric_names')
rcvr_id_names = config.get(section_name, 'rcvr_id_names')
gpt_cate_names = config.get(section_name, 'gpt_cate_names')
batch_size = config.get(section_name, 'batch_size')
learning_rate = config.get(section_name, 'learning_rate')
dnn_use_bn = config.get(section_name, 'dnn_use_bn')
dnn_hidden_units = config.get(section_name, 'dnn_hidden_units')
dnn_activation = config.get(section_name, 'dnn_activation')
att_hidden_size = config.get(section_name, 'att_hidden_size')
att_activation = config.get(section_name, 'att_activation')
att_weight_normalization = config.get(section_name, 'att_weight_normalization')
l2_reg_dnn = config.get(section_name, 'l2_reg_dnn')
l2_reg_embedding = config.get(section_name, 'l2_reg_embedding')
dnn_dropout = config.get(section_name, 'dnn_dropout')
seed = config.get(section_name, 'seed')
epochs = config.get(section_name, 'epochs')
h5_model_path = config.get(section_name, 'h5_model_path')
tf_model_path = config.get(section_name, 'tf_model_path')


# Dependencies from Previous Sections
# Previous section: data_preprocessing
# Edge Attributes from DAG
directory = config.get('data_preprocessing', 'transformed_data_path')


# Research Code
import pickle
from tqdm import tqdm
import yaml
import tensorflow as tf
import numpy as np
import pandas as pd
from tensorflow.python.keras.optimizers import adam_v2
from deepctr.feature_column import SparseFeat, VarLenSparseFeat, DenseFeat, get_feature_names
from deepctr.models import DIN


gpus = tf.config.experimental.list_physical_devices('GPU')
for i in range(len(gpus)):
    tf.config.experimental.set_memory_growth(gpus[i], True)


def load_yaml_file(file_path):
    try:
        with open(file_path, 'r') as file:
            yaml_content = yaml.safe_load(file)
        return yaml_content
    except FileNotFoundError:
        return None


file_path = '../config/base_config.yaml'  # Path to your YAML file
config = load_yaml_file(file_path)
if config is not None:
    with open('../_current_model_version', "rb") as f:
        model_version = pickle.load(f)
    model_version_base = os.path.join('../artifacts/', model_version)
    exported_feature_transformer = os.path.join(model_version_base, 'exported_feature_transformer')
    model_version_base = os.path.join(model_version_base, '19')
    if not os.path.exists(model_version_base):
        os.mkdir(model_version_base)
    exported_model_base = os.path.join(model_version_base, 'exported_models')
    if not os.path.exists(exported_model_base):
        os.mkdir(exported_model_base)


directory = '../data/ql_store_rmr_driver_dev_features_transformed'
parquet_files = [f for f in os.listdir(directory) if f.endswith(".parquet")]
dfs = []
for file in tqdm(parquet_files, total=len(parquet_files)):
    file_path = os.path.join(directory, file)
    f = pd.read_parquet(file_path)
    dfs.append(f)
data = pd.concat(dfs, ignore_index=True)


with open(os.path.join(exported_feature_transformer, 'categorical_feature_encoders'), "rb") as f:
    categorical_feature_encoders = pickle.load(f)
with open(os.path.join(exported_feature_transformer, 'rcvr_id_tokenizer'), "rb") as f:
    rcvr_id_tokenizer = pickle.load(f)


data_train = data[data['split'] == 'train'].copy()
data_val = data[data['split'] == 'val'].copy()


numeric_names = [
    "sndr_rcvr_txn_num_30d", "sndr_rcvr_txn_num_180d", "sndr_rcvr_txn_num_365d", "sndr_rcvr_txn_amt_30d", "sndr_rcvr_txn_amt_180d",
    "sndr_rcvr_txn_amt_365d", "sndr_last_5_txn_avg_amt", "sndr_last_10_txn_avg_amt", "sndr_rcvr_category_breadth_30d", "sndr_rcvr_category_breadth_180d",
    "sndr_rcvr_category_breadth_365d", "sndr_rcvr_category_txn_num_30d", "sndr_rcvr_category_txn_num_180d", "sndr_rcvr_category_txn_num_365d",
    "sndr_rcvr_category_txn_amt_30d", "sndr_rcvr_category_txn_amt_180d", "sndr_rcvr_category_txn_amt_365d", "sndr_rcvr_category_avg_txn_amt_30d",
    "sndr_rcvr_category_avg_txn_amt_180d", "sndr_rcvr_category_avg_txn_amt_365d", "sndr_1st_freq_merchant_category_cnt_30d",
    "sndr_2nd_freq_merchant_category_cnt_30d", "sndr_3rd_freq_merchant_category_cnt_30d", "sndr_1st_freq_merchant_category_cnt_180d",
    "sndr_2nd_freq_merchant_category_cnt_180d", "sndr_3rd_freq_merchant_category_cnt_180d", "sndr_1st_freq_merchant_category_cnt_365d",
    "sndr_2nd_freq_merchant_category_cnt_365d", "sndr_3rd_freq_merchant_category_cnt_365d", "rcvr_avg_price_30d", "rcvr_price_10_penentile_30d",
    "rcvr_price_30_penentile_30d", "rcvr_price_50_penentile_30d", "rcvr_price_70_penentile_30d", "rcvr_price_90_penentile_30d", "rcvr_rcvd_txn_num_30d",
    "rcvr_rcvd_distinct_consumer_num_30d", "rcvr_rcvd_txn_amt_30d", "sndr_last_1_txn_avg_amt_rcvr_avg_price_diff",
    "sndr_last_1_txn_avg_amt_rcvr_median_price_diff", "sndr_last_5_txn_avg_amt_rcvr_avg_price_diff", "sndr_last_5_txn_avg_amt_rcvr_median_price_diff",
    "sndr_last_10_txn_avg_amt_rcvr_avg_price_diff", "sndr_last_10_txn_avg_amt_rcvr_median_price_diff", "sndr_rcvr_num_save_7day",
    "sndr_rcvr_num_save_30day", "sndr_rcvr_num_save_180day", "sndr_num_save_7day", "sndr_num_save_30day", "sndr_num_save_180day",
    "sndr_rcvr_num_sameindustry_save_7day", "sndr_rcvr_num_sameindustry_save_30day", "sndr_rcvr_num_sameindustry_save_180day",
    "rcvr_save_cnt_30d", "rcvr_save_cnt_deals_explore_tertiary_30d", "rcvr_save_cnt_ql_home_30d", "rcvr_save_cnt_rewards_zone_new_30d",
    "rcvr_save_cnt_reboarding_30d", "rcvr_save_cnt_high_engaged_30d", "rcvr_save_cnt_mid_engaged_30d", "rcvr_save_cnt_low_engaged_30d",
    "rcvr_save_cnt_likely_to_churn_30d", "rcvr_save_cnt_new_not_active_30d", "rcvr_save_cnt_never_active_30d", "rcvr_save_cnt_churned_30d",
    "rcvr_save_cnt_re_engaged_30d", "rcvr_save_cnt_new_active_30d", "sndr_days_on_file", "sndr_days_appweb_visit", "rcvr_tpv_score"
] + [f"embedding_{i+1}" for i in range(32)]


rcvr_id_names = ['rcvr_id']
gpt_cate_names = [
    'gpt_1st_category_l2_index', 'sndr_1st_freq_merchant_category_30d', 'sndr_2nd_freq_merchant_category_30d', 'sndr_3rd_freq_merchant_category_30d',
    'sndr_1st_freq_merchant_category_180d', 'sndr_2nd_freq_merchant_category_180d', 'sndr_3rd_freq_merchant_category_180d',
    'sndr_1st_freq_merchant_category_365d', 'sndr_2nd_freq_merchant_category_365d', 'sndr_3rd_freq_merchant_category_365d'
]


def get_xy_fd_share_embdding(data, numeric_names, rcvr_id_names, gpt_cate_names):
    feature_columns = []
    for column_name in numeric_names:
        feature_columns.append(DenseFeat(column_name, 1))
    feature_columns.append(SparseFeat('sndr_prmry_addr_state', len(categorical_feature_encoders['sndr_prmry_addr_state']) + 1, embedding_dim="auto"))
    feature_columns.append(SparseFeat('sndr_consu_engagmnt_seg_key', len(categorical_feature_encoders['sndr_consu_engagmnt_seg_key']) + 1, embedding_dim="auto"))
    feature_columns.append(SparseFeat('sndr_ebay_member_y_n', len(categorical_feature_encoders['sndr_ebay_member_y_n']) + 1, embedding_dim="auto"))
    feature_columns.append(SparseFeat('gender', len(categorical_feature_encoders['gender']) + 1, embedding_dim="auto"))
    feature_columns.append(SparseFeat('sndr_prmry_cc_type_code', len(categorical_feature_encoders['sndr_prmry_cc_type_code']) + 1, embedding_dim="auto"))
    feature_columns.append(SparseFeat('sndr_consu_age_band_key', len(categorical_feature_encoders['sndr_consu_age_band_key']) + 1, embedding_dim="auto"))
    feature_columns.append(SparseFeat('sndr_consu_dmgrphc_seg_key', len(categorical_feature_encoders['sndr_consu_dmgrphc_seg_key']) + 1, embedding_dim="auto"))
    for column_name in rcvr_id_names:
        feature_columns.append(SparseFeat(column_name, max(rcvr_id_tokenizer.word_index.values()) + 1, embedding_dim="auto", embedding_name='rcvr_id'))
    for column_name in gpt_cate_names:
        feature_columns.append(SparseFeat(column_name, 51 + 1, embedding_dim="auto", embedding_name='gpt_1st_category_l2_index'))
    feature_columns += [
        VarLenSparseFeat(SparseFeat('hist_rcvr_id', max(rcvr_id_tokenizer.word_index.values()) + 1, embedding_dim='auto', embedding_name='rcvr_id'), maxlen=100),
        VarLenSparseFeat(SparseFeat('hist_gpt_1st_category_l2_index', 51 + 1, embedding_dim='auto', embedding_name='gpt_1st_category_l2_index'), maxlen=100)
    ]
    dnn_feature_columns = feature_columns
    feature_names = get_feature_names(feature_columns)
    behavior_feature_list = ["rcvr_id", "gpt_1st_category_l2_index"]
    x = {name: data[name].values for name in feature_names}
    token = data['hist_rcvr_id']
    x['hist_rcvr_id'] = np.array(token.values.tolist())
    token = data['hist_gpt_1st_category_l2_index']
    x['hist_gpt_1st_category_l2_index'] = np.array(token.values.tolist())
    y = data['target'].values
    return x, y, dnn_feature_columns, behavior_feature_list


x_train, y_train, dnn_feature_columns, behavior_feature_list = get_xy_fd_share_embdding(data_train, numeric_names, rcvr_id_names, gpt_cate_names)
x_val, y_val, _, _ = get_xy_fd_share_embdding(data_val, numeric_names, rcvr_id_names, gpt_cate_names)
feature_names = get_feature_names(dnn_feature_columns)


def data_generator(x_data, y_data, batch_size):
    keys = list(x_data.keys())
    length = len(y_data)
    while True:
        indices = np.random.permutation(length)
        for start in range(0, length, batch_size):
            end = min(start + batch_size, length)
            batch_indices = indices[start:end]
            x_batch = {key: np.array([x_data[key][i] for i in batch_indices]) for key in keys}
            y_batch = np.array([y_data[i] for i in batch_indices])
            yield x_batch, y_batch


# Parameters
batch_size = config['training_config']['DIN']['batch_size']


# Create training and validation datasets
train_dataset = tf.data.Dataset.from_generator(
    lambda: data_generator(x_train, y_train, batch_size),
    output_signature=(
        {key: tf.TensorSpec(shape=(None, *x_train[key].shape[1:]), dtype=tf.float32) for key in x_train.keys()},
        tf.TensorSpec(shape=(None,), dtype=tf.float32)
    )
).shuffle(len(x_train))

val_dataset = tf.data.Dataset.from_generator(
    lambda: data_generator(x_val, y_val, batch_size),
    output_signature=(
        {key: tf.TensorSpec(shape=(None, *x_val[key].shape[1:]), dtype=tf.float32) for key in x_val.keys()},
        tf.TensorSpec(shape=(None,), dtype=tf.float32)
    )
).shuffle(len(x_val))


steps_per_epoch = len(y_train) // batch_size
validation_steps = len(y_val) // batch_size
strategy = tf.distribute.MirroredStrategy([])  # single machine multiple gpu


with strategy.scope():
    adam = adam_v2.Adam(learning_rate=config['training_config']['DIN']['learning_rate'])
    model = DIN(
        dnn_feature_columns, behavior_feature_list,
        dnn_use_bn=config['training_config']['DIN']['dnn_use_bn'],
        dnn_hidden_units=config['training_config']['DIN']['dnn_hidden_units'],
        dnn_activation=config['training_config']['DIN']['dnn_activation'],
        att_hidden_size=config['training_config']['DIN']['att_hidden_size'],
        att_activation=config['training_config']['DIN']['att_activation'],
        att_weight_normalization=config['training_config']['DIN']['att_weight_normalization'],
        l2_reg_dnn=config['training_config']['DIN']['l2_reg_dnn'],
        l2_reg_embedding=config['training_config']['DIN']['l2_reg_embedding'],
        dnn_dropout=config['training_config']['DIN']['dnn_dropout'],
        seed=config['training_config']['DIN']['seed'],
        task='binary'
    )
    model.compile(adam, loss="binary_crossentropy", metrics=[tf.keras.metrics.AUC()])


early_stopping = tf.keras.callbacks.EarlyStopping(
    monitor='val_loss',
    patience=3,
    mode='max',
    restore_best_weights=True,
    verbose=1
)


history = model.fit(
    train_dataset,
    steps_per_epoch=steps_per_epoch,
    epochs=config['training_config']['DIN']['epochs'],
    validation_data=val_dataset,
    validation_steps=validation_steps,
    callbacks=[early_stopping]
)


print('Script initialized')