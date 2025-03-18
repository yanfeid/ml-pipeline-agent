# Section Name
section_name = "Model Evaluation"

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
file_name = "repos/ql-store-recommendation-prod/research/pipeline/06_evaluation.ipynb"
line_range = "Lines 375-731"
bq_project_dataset_prefix = "'{config['general_config']['bq_project_dataset_prefix']}'"
config_file_path = "../config/base_config.yaml"
model_version_base = "../artifacts/{model_version}/18"
model_version_path = "../_current_model_version"
oot_start_date = "'{config['driver_config']['oot_start_date']}'"
remove_list = "'''1365556366671835703'',''2254348706417584521'',''1581565211190403045'',''1157330454984142772'',''1339933886421356550'',''1812170125034785903'',''6053464759929799123'',''1587111025150613712'',''1672368731209095395'',''1365556366671835703'',''6085552794250364378'',''1954349237309389875'''"
exported_eval_readout_base = "../artifacts/{model_version}/18/exported_eval_readouts"
performance_all_csv = "../artifacts/{model_version}/18/exported_eval_readouts/performane_all.csv"
performance_all_png = "../artifacts/{model_version}/18/exported_eval_readouts/performane_all.png"
performance_ftu_csv = "../artifacts/{model_version}/18/exported_eval_readouts/performane_ftu.csv"
performance_ftu_png = "../artifacts/{model_version}/18/exported_eval_readouts/performane_ftu.png"
performance_wo_ebay_csv = "../artifacts/{model_version}/18/exported_eval_readouts/performane_wo_ebay.csv"
performance_wo_ebay_png = "../artifacts/{model_version}/18/exported_eval_readouts/performane_wo_ebay.png"

# Dependencies from Other Sections
# Previous section: model_scoring
# Edge Attributes from DAG
eval_result_path = "gs://pypl-bkt-rsh-row-std-gds-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_oot_transformed_scored"

# Research code goes here
def research_function():
    print('Running research code for', section_name)
