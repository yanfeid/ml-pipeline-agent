# Section Name
section_name = "Model Training"

# General Parameters (from environment.ini)
refresh_date = "2023-10-05"
user = "chenzhao"
environment = "dev"
mo_name = ""
driver_dataset = ""
dataproc_project_name = "ccg24-hrzana-gds-pacman"
dataproc_storage_bucket = "pypl-bkt-rsh-row-std-gds-pacman"
local_output_base_path = "/projects/gds-packman/apps/ql-store-recommendation-prod/research"
gcs_base_path = "gs://${general:dataproc_storage_bucket}/user/${general:user}/prod/ql-store-rmr"
queue_name = "default"
namespace = "gds-packman"
model_name = "RMR_MODEL_ID"
check_point = ""
email_to = "chenzhao"
state_file = ""
cosmos_project = "chenzhao"
gcp_app_id = ""

# Section-Specific Parameters (from solution.ini)
file_name = "repos/ql-store-recommendation-prod/research/pipeline/04_training.ipynb"
line_range = "Lines 140-170"
att_activation = "config['training_config']['DIN']['att_activation']"
att_hidden_size = "config['training_config']['DIN']['att_hidden_size']"
att_weight_normalization = "config['training_config']['DIN']['att_weight_normalization']"
batch_size = "config['training_config']['DIN']['batch_size']"
dnn_activation = "config['training_config']['DIN']['dnn_activation']"
dnn_dropout = "config['training_config']['DIN']['dnn_dropout']"
dnn_hidden_units = "config['training_config']['DIN']['dnn_hidden_units']"
dnn_use_bn = "config['training_config']['DIN']['dnn_use_bn']"
epochs = "config['training_config']['DIN']['epochs']"
gpt_cate_names = "'["gpt_1st_category_l2_index", "sndr_1st_freq_merchant_category_30d", ...]'"
l2_reg_dnn = "config['training_config']['DIN']['l2_reg_dnn']"
l2_reg_embedding = "config['training_config']['DIN']['l2_reg_embedding']"
learning_rate = "config['training_config']['DIN']['learning_rate']"
numeric_names = "'["sndr_rcvr_txn_num_30d", "sndr_rcvr_txn_num_180d", "sndr_rcvr_txn_num_365d", ...]'"
rcvr_id_names = "'["rcvr_id"]'"
seed = "config['training_config']['DIN']['seed']"
train_data_path = "../data/ql_store_rmr_driver_dev_features_transformed"
model_artifact_path = "os.path.join(exported_model_base, 'din.h5')"
tf_model_path = "os.path.join(exported_model_base, 'din_saved_model')"

# Dependencies from Other Sections
# Previous section: data_preprocessing
# Edge Attributes from DAG
output_dir = "../data/ql_store_rmr_driver_dev_features_transformed"

# Research code goes here
def research_function():
    print('Running research code for', section_name)
