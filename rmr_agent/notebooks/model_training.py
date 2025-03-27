## gsutil authentication
%ppauth
                    
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
section_name = "model_training"

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
att_activation = config.get('section_name', 'att_activation')
att_hidden_size = config.get('section_name', 'att_hidden_size')
att_weight_normalization = config.get('section_name', 'att_weight_normalization')
batch_size = config.get('section_name', 'batch_size')
dnn_activation = config.get('section_name', 'dnn_activation')
dnn_dropout = config.get('section_name', 'dnn_dropout')
dnn_hidden_units = config.get('section_name', 'dnn_hidden_units')
dnn_use_bn = config.get('section_name', 'dnn_use_bn')
epochs = config.get('section_name', 'epochs')
gpt_cate_names = config.get('section_name', 'gpt_cate_names')
l2_reg_dnn = config.get('section_name', 'l2_reg_dnn')
l2_reg_embedding = config.get('section_name', 'l2_reg_embedding')
learning_rate = config.get('section_name', 'learning_rate')
numeric_names = config.get('section_name', 'numeric_names')
rcvr_id_names = config.get('section_name', 'rcvr_id_names')
seed = config.get('section_name', 'seed')
train_data_path = config.get('section_name', 'train_data_path')
model_artifact_path = config.get('section_name', 'model_artifact_path')
tf_model_path = config.get('section_name', 'tf_model_path')

# Dependencies from Previous Sections
# Previous section: data_preprocessing
# Edge Attributes from DAG
output_dir = config.get('data_preprocessing', 'output_dir')


# === Research Code ===
strategy = tf.distribute.MirroredStrategy([]) # single machine multiple gpu
with strategy.scope():
    adam = adam_v2.Adam(learning_rate=learning_rate)
    model = DIN(
        dnn_feature_columns, behavior_feature_list,
        dnn_use_bn=dnn_use_bn,
        dnn_hidden_units=dnn_hidden_units,
        dnn_activation=dnn_activation,
        att_hidden_size=att_hidden_size,
        att_activation=att_activation,
        att_weight_normalization=att_weight_normalization,
        l2_reg_dnn=l2_reg_dnn,
        l2_reg_embedding=l2_reg_embedding,
        dnn_dropout=dnn_dropout,
        seed=seed,
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
        epochs=epochs,
        validation_data=val_dataset,
        validation_steps=validation_steps,
        callbacks=[early_stopping]
    )

print('Script initialized')