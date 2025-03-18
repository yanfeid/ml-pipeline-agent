# Section Name
section_name = "Model Packaging"

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
line_range = "Lines 171-185"
trained_model_path = "os.path.join(exported_model_base, 'din_saved_model')"
onnx_model_path = "os.path.join(exported_model_base, 'din.onnx')"
oot_scoring_path = "os.path.join(exported_model_base, 'oot_scoring')"
prod_model_path = "os.path.join(exported_model_base, 'din_prod.m')"

# Dependencies from Other Sections
# Previous section: model_training
# Edge Attributes from DAG
tf_model_path = "os.path.join(exported_model_base, 'din_saved_model')"

# Research code goes here
def research_function():
    print('Running research code for', section_name)
