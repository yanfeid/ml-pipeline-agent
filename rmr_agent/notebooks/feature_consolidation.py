# Section Name
section_name = "Feature Consolidation"

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
file_name = "repos/ql-store-recommendation-prod/research/pipeline/02_combine.ipynb"
line_range = "Lines 17-624"
bq_prefix = "config['general_config']['bq_project_dataset_prefix']"
file_path = "../config/base_config.yaml"
driver_dev_features_table = "'{bq_prefix}driver_dev_features'"
driver_oot_features_expand_seq_table = "'{bq_prefix}driver_oot_features_expand_seq'"
driver_oot_features_table = "'{bq_prefix}driver_oot_features'"
export_uri = "${general:gcs_base_path}/data/ql_store_rmr_driver_dev_features/part*.parquet"

# Dependencies from Other Sections
# No dependencies (first section)

# Research code goes here
def research_function():
    print('Running research code for', section_name)
