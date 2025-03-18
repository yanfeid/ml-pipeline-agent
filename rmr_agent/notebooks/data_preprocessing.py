# Section Name
section_name = "Data Preprocessing"

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
file_name = "repos/ql-store-recommendation-prod/research/pipeline/03_prepare_training_data.ipynb"
line_range = "Lines 21-175"
categorical_features = "'["sndr_consu_engagmnt_seg_key", "sndr_ebay_member_y_n", "gender", ...]'"
chunk_size = "'1000000'"
directory = "../data/ql_store_rmr_driver_dev_features"
model_version_base = "../artifacts/din_<today_date>"
numeric_features = "'["sndr_rcvr_txn_num_30d", "sndr_rcvr_txn_num_180d", ...]'"
parquet_files = "'["file1.parquet", "file2.parquet", ...]'"
rcvr_id_tokenizer_params = "'{"num_words": 1000, "oov_token": "<OOV>"}'"
state_to_abbreviation = "'{"ALABAMA": "AL", "ALASKA": "AK", ...}'"
categorical_feature_encoders_path = "../artifacts/din_<today_date>/exported_feature_transformer/categorical_feature_encoders"
exported_feature_transformer = "../artifacts/din_<today_date>/exported_feature_transformer"
model_version = "din_<today_date>"
numerical_feature_scalars_path = "../artifacts/din_<today_date>/exported_feature_transformer/numerical_feature_scalars"
output_dir = "../data/ql_store_rmr_driver_dev_features_transformed"
rcvr_id_tokenizer_path = "../artifacts/din_<today_date>/exported_feature_transformer/rcvr_id_tokenizer"

# Dependencies from Other Sections
# Previous section: feature_consolidation
# Edge Attributes from DAG
export_uri = "gs://pypl-bkt-rsh-row-std-gds-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_driver_dev_features/part*.parquet"

# Research code goes here
def research_function():
    print('Running research code for', section_name)
