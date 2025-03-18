# Section Name
section_name = "Data Pulling"

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
file_name = "repos/ql-store-recommendation-prod/research/pipeline/01_varmart_feat.ipynb"
line_range = "Lines 23-67"
bq_materialization_dataset = "rsh_row_gds_pacman"
bq_materialization_project = "pypl-bods"
description = "ranking_combined_datafetcher"
driver_loc = "${general:gcs_base_path}/data/ql_store_rmr_driver_simu_consumer"
gcp_project_id = "ccg24-hrzana-gds-pacman"
gcs_bucket_name = "pypl-bkt-rsh-row-std-gds-pacman"
group_name = "mls_gads"
is_prod = "'True'"
job_name = "ql_store_rmr"
manager = "Farhad"
model_name = "ql_store_rmr_datafetcher"
model_owner = "chenzhao"
num_of_splits = "'1'"
on_gcp = "'True'"
seq_num = "'20231005'"
split_ratio = "'{"train": 1.0}'"
stage = "training"
variables = "'["prmry_addr_state", "days_on_file", "ebay_member_y_n", "consu_engagmnt_seg_key", "prmry_cc_type_code", "days_appweb_visit", "consu_age_band_key", "consu_income_band_key", "consu_dmgrphc_seg_key"]'"
data_loc = "${general:gcs_base_path}/data/ql_store_rmr_driver_simu_consumer_varmart"

# Dependencies from Other Sections
# Previous section: feature_engineering
# Edge Attributes from DAG
driver_loc = "gs://pypl-bkt-rsh-row-std-gds-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_driver_simu_consumer"
driver_simu_consumer = "{bq_prefix}driver_simu_consumer"

# Research code goes here
def research_function():
    print('Running research code for', section_name)
