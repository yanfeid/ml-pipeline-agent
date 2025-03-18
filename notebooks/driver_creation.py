# Section Name
section_name = "Driver Creation"

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
file_name = "repos/ql-store-recommendation-prod/research/pipeline/00_driver.ipynb"
line_range = "Lines 4-512"
bq_prefix = "config['general_config']['bq_project_dataset_prefix']"
file_path = "../config/base_config.yaml"
hard_negative_impression_time_window = "config['driver_config']['hard_negative_impression_time_window']"
negative_sampling_avoid_delay_postive_feedback_window = "config['driver_config']['negative_sampling_avoid_delay_postive_feedback_window']"
oot_start_date = "config['driver_config']['oot_start_date']"
ratio_for_hard_negtive = "config['driver_config']['ratio_for_hard_negtive']"
removing_highly_active_user_merchant_date_threshold = "config['driver_config']['removing_highly_active_user_merchant_date_threshold']"
removing_highly_active_user_merchant_threshold = "config['driver_config']['removing_highly_active_user_merchant_threshold']"
removing_highly_active_user_threshold = "config['driver_config']['removing_highly_active_user_threshold']"
save_label_mixing_rate = "config['driver_config']['save_label_mixing_rate']"
train_start_date = "config['driver_config']['train_start_date']"
training_attributed_txn_upsampling_rate = "config['driver_config']['training_attributed_txn_upsampling_rate']"
training_exclude_merch = "config['driver_config']['training_exclude_merch']"
training_hot_negative_sampling_alpha = "config['driver_config']['training_hot_negative_sampling_alpha']"
training_hot_positive_attributed_txn_sampling_alpha = "config['driver_config']['training_hot_positive_attributed_txn_sampling_alpha']"
training_hot_positive_organic_txn_sampling_alpha = "config['driver_config']['training_hot_positive_organic_txn_sampling_alpha']"
uniform_negative_postive_ratio = "config['driver_config']['uniform_negative_postive_ratio']"
val_start_date = "config['driver_config']['val_start_date']"
driver_oot = "'{bq_prefix}driver_oot'"
driver_simu = "'{bq_prefix}driver_simu'"
driver_simu_consumer = "'{bq_prefix}driver_simu_consumer'"

# Dependencies from Other Sections
# No dependencies (first section)

# Research code goes here
def research_function():
    print('Running research code for', section_name)
