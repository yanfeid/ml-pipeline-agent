# Section Name
section_name = "Model Scoring"

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
file_name = "repos/ql-store-recommendation-prod/research/pipeline/05_scoring_oot.ipynb"
line_range = "Lines 25-94"
eval_path = "${general:gcs_base_path}/data/ql_store_rmr_oot_transformed_scored"
exported_model_base = "/projects/gds-packman/apps/ql-store-recommendation-prod/research/artifacts/{model_version}/exported_models"
m_gcp_folder = "${general:gcs_base_path}/challenger/oot_scoring"
m_local_folder = "/projects/gds-packman/apps/ql-store-recommendation-prod/research/artifacts/din_20240708/18/exported_models/oot_scoring"
model_version_path = "/projects/gds-packman/apps/ql-store-recommendation-prod/research/_current_model_version"
oot_data_path = "${general:gcs_base_path}/data/ql_store_rmr_oot_transformed"
params_path = "/projects/gds-packman/apps/ql-store-recommendation-prod/research/config"
section_name = "oot_data_scoring"
working_path = "/projects/gds-packman/apps/ql-store-recommendation-prod/research"
eval_result_path = "${general:gcs_base_path}/data/ql_store_rmr_oot_transformed_scored"
log_file = "${general:local_output_base_path}/logs/{job_id}.log"

# Dependencies from Other Sections
# Previous section: model_packaging
# Edge Attributes from DAG
oot_scoring_path = "os.path.join(exported_model_base, 'oot_scoring')"

# Research code goes here
def research_function():
    print('Running research code for', section_name)
