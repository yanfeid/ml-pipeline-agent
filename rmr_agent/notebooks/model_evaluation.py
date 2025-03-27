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
section_name = "model_evaluation"

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
bq_project_dataset_prefix = config.get('section_name', 'bq_project_dataset_prefix')
config_file_path = config.get('section_name', 'config_file_path')
model_version_base = config.get('section_name', 'model_version_base')
model_version_path = config.get('section_name', 'model_version_path')
oot_start_date = config.get('section_name', 'oot_start_date')
remove_list = config.get('section_name', 'remove_list')
exported_eval_readout_base = config.get('section_name', 'exported_eval_readout_base')
performance_all_csv = config.get('section_name', 'performance_all_csv')
performance_all_png = config.get('section_name', 'performance_all_png')
performance_ftu_csv = config.get('section_name', 'performance_ftu_csv')
performance_ftu_png = config.get('section_name', 'performance_ftu_png')
performance_wo_ebay_csv = config.get('section_name', 'performance_wo_ebay_csv')
performance_wo_ebay_png = config.get('section_name', 'performance_wo_ebay_png')

# Dependencies from Previous Sections
# Previous section: model_scoring
# Edge Attributes from DAG
eval_result_path = config.get('model_scoring', 'eval_result_path')

# === Research Code ===
q = f"""with temp as (select
'tpv' as model,
sum(case when tpv_rank<=1 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_1,
sum(case when tpv_rank<=2 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_2,
sum(case when tpv_rank<=5 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_5,
sum(case when tpv_rank<=1 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_1,
sum(case when tpv_rank<=2 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_2,
sum(case when tpv_rank<=5 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_5,
sum(case when tpv_rank<=1 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_1,
sum(case when tpv_rank<=2 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_2,
sum(case when tpv_rank<=5 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_5,
sum(case when tpv_rank<=1 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_1,
sum(case when tpv_rank<=2 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_2,
sum(case when tpv_rank<=5 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_5,
from {bq_project_dataset_prefix}driver_oot_hueristic_model_comparison
group by 1
union all
select
'mlv2' as model,
sum(case when mlv2_rank<=1 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_1,
sum(case when mlv2_rank<=2 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_2,
sum(case when mlv2_rank<=5 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_5,
sum(case when mlv2_rank<=1 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_1,
sum(case when mlv2_rank<=2 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_2,
sum(case when mlv2_rank<=5 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_5,
sum(case when mlv2_rank<=1 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_1,
sum(case when mlv2_rank<=2 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_2,
sum(case when mlv2_rank<=5 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_5,
sum(case when mlv2_rank<=1 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_1,
sum(case when mlv2_rank<=2 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_2,
sum(case when mlv2_rank<=5 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_5,
from {bq_project_dataset_prefix}driver_oot_hueristic_model_comparison
group by 1
union all
select
'mlv3' as model,
sum(case when mlv3_rank<=1 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_1,
sum(case when mlv3_rank<=2 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_2,
sum(case when mlv3_rank<=5 and target=1 then 1 else 0 end)/sum(case when target=1 then 1 else 0 end) as recall_at_5,
sum(case when mlv3_rank<=1 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_1,
sum(case when mlv3_rank<=2 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_2,
sum(case when mlv3_rank<=5 and target=1 and pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_5,
sum(case when mlv3_rank<=1 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_1,
sum(case when mlv3_rank<=2 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_2,
sum(case when mlv3_rank<=5 and target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_5,
sum(case when mlv3_rank<=1 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_1,
sum(case when mlv3_rank<=2 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_2,
sum(case when mlv3_rank<=5 and target=1 and pos_tag_type='save' then 1 else 0 end)/sum(case when target=1 and pos_tag_type='save' then 1 else 0 end) as save_recall_at_5,
from {bq_project_dataset_prefix}driver_oot_hueristic_model_comparison
group by 1)
select * from temp
order by case model
when 'tpv' then 1
when 'mlv2' then 2
when 'mlv3' then 3
END;
"""
# df_all = %ppbq $q
df_all.to_csv(os.path.join(exported_eval_readout_base, performance_all_csv), index=False)
import seaborn as sns
import matplotlib.pyplot as plt
fig, axes = plt.subplots(4, 3, figsize=(5, 5))
axes = axes.flatten()
for i in range(12):
    sub_df = df_all[['model', df_all.columns[i+1]]]
    sns.barplot(x=sub_df.columns[0], y=sub_df.columns[1], ax=axes[i], data=sub_df)
    axes[i].set_xlabel('')
    axes[i].tick_params(axis='x', labelsize=5)
    axes[i].tick_params(axis='y', labelsize=5)
    axes[i].set_ylabel(axes[i].get_ylabel(), fontsize=5)
plt.tight_layout()
plt.savefig(os.path.join(exported_eval_readout_base, performance_all_png), dpi=300)
plt.show()

q = f"""
with temp as (select
'tpv' as model,
sum(case when tpv_rank<=1 and a.target=1 then 1 else 0 end)/sum(case when a.target=1 then 1 else 0 end) as recall_at_1,
sum(case when tpv_rank<=2 and a.target=1 then 1 else 0 end)/sum(case when a.target=1 then 1 else 0 end) as recall_at_2,
sum(case when tpv_rank<=5 and a.target=1 then 1 else 0 end)/sum(case when a.target=1 then 1 else 0 end) as recall_at_5,
sum(case when tpv_rank<=1 and a.target=1 and a.pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when a.target=1 and a.pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_1,
sum(case when tpv_rank<=2 and a.target=1 and a.pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when a.target=1 and a.pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_2,
sum(case when tpv_rank<=5 and a.target=1 and a.pos_tag_type='attributed_txn' then 1 else 0 end)/sum(case when a.target=1 and a.pos_tag_type='attributed_txn' then 1 else 0 end) as attributed_txn_recall_at_5,
sum(case when tpv_rank<=1 and a.target=1 and a.pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when a.target=1 and a.pos_tag_type='pure_organirc_txn' then 1 else 0 end) as pure_organirc_txn_recall_at_1,
sum(case when tpv_rank<=2 and a.target=1 and a.pos_tag_type='pure_organirc_txn' then 1 else 0 end)/sum(case when a.target=1 and a.pos_tag_type='pure_