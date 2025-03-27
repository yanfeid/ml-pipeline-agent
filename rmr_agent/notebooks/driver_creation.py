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
section_name = "driver_creation"

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
bq_prefix = config.get('section_name', 'bq_prefix')
file_path = config.get('section_name', 'file_path')
hard_negative_impression_time_window = config.get('section_name', 'hard_negative_impression_time_window')
negative_sampling_avoid_delay_postive_feedback_window = config.get('section_name', 'negative_sampling_avoid_delay_postive_feedback_window')
oot_start_date = config.get('section_name', 'oot_start_date')
ratio_for_hard_negtive = config.get('section_name', 'ratio_for_hard_negtive')
removing_highly_active_user_merchant_date_threshold = config.get('section_name', 'removing_highly_active_user_merchant_date_threshold')
removing_highly_active_user_merchant_threshold = config.get('section_name', 'removing_highly_active_user_merchant_threshold')
removing_highly_active_user_threshold = config.get('section_name', 'removing_highly_active_user_threshold')
save_label_mixing_rate = config.get('section_name', 'save_label_mixing_rate')
train_start_date = config.get('section_name', 'train_start_date')
training_attributed_txn_upsampling_rate = config.get('section_name', 'training_attributed_txn_upsampling_rate')
training_exclude_merch = config.get('section_name', 'training_exclude_merch')
training_hot_negative_sampling_alpha = config.get('section_name', 'training_hot_negative_sampling_alpha')
training_hot_positive_attributed_txn_sampling_alpha = config.get('section_name', 'training_hot_positive_attributed_txn_sampling_alpha')
training_hot_positive_organic_txn_sampling_alpha = config.get('section_name', 'training_hot_positive_organic_txn_sampling_alpha')
uniform_negative_postive_ratio = config.get('section_name', 'uniform_negative_postive_ratio')
val_start_date = config.get('section_name', 'val_start_date')
driver_oot = config.get('section_name', 'driver_oot')
driver_simu = config.get('section_name', 'driver_simu')
driver_simu_consumer = config.get('section_name', 'driver_simu_consumer')

# Dependencies from Previous Sections

# === Research Code ===
import yaml

def load_yaml_file(file_path):
    try:
        with open(file_path, 'r') as file:
            yaml_content = yaml.safe_load(file)
        return yaml_content
    except FileNotFoundError:
        return None

file_path = '../config/base_config.yaml'
config = load_yaml_file(file_path)
if config is not None:
    bq_prefix = config['general_config']['bq_project_dataset_prefix']

## eligible merchants
q = f"""
DROP TABLE IF EXISTS {bq_prefix}live_unique_merchants_train;
CREATE TABLE {bq_prefix}live_unique_merchants_train AS
WITH
stores_paypalMerchant_raw AS (
SELECT
storeid,
encryptedid
FROM
pypl-edl.honey_raw_tables.stores_paypalMerchant_raw
QUALIFY
ROW_NUMBER() OVER (PARTITION BY storeid ORDER BY last_ingestion_utc_time DESC)=1 )
SELECT
a.store_id AS honey_store_id,
a.name AS honey_store_name,
CAST(SUBSTR(a.max_cash_back, 1, LENGTH(a.max_cash_back) - 1) AS FLOAT64) AS cashback_percent,
b.encryptedid AS encrypt_id,
c.customer_id AS rcvr_id,
COALESCE(d.gpt_1st_category_l2_index,0) AS gpt_1st_category_l2_index
FROM
honey-production.aoi.live_unique_merchants a
JOIN
stores_paypalMerchant_raw b
ON
a.store_id = b.storeid
JOIN
pypl-edw.pp_access_views.dw_customer_map c
ON
b.encryptedid = c.dienc13i6_id
LEFT JOIN
pypl-bods.gds_pacman_prod.ql_store_rmr_merchant_info d
ON
b.encryptedid = d.encrypt_id
where rcvr_id not in ({config['driver_config']['training_exclude_merch']})
"""
# %ppbq $q
q=f"""
drop table if exists {bq_prefix}driver_00 ;
create table {bq_prefix}driver_00 as
SELECT
cust_id,
b.rcvr_id,
a.evnt_dt-1 as run_date,
a.placement,
a.client_os,
a.devc_type,
a.rfmbc_seg,
a.consu_dmgrphc_seg,
a.consu_age_band,
a.consu_inc_band,
case when coalesce(saves_clk_unique_cnt,0)+coalesce(saves_outclick_unique_cnt,0)+coalesce(saves_save_unique_cnt,0)>0 then 1 else 0 end as save,
case when coalesce(saves_leap_txns,0)+coalesce(saves_left_aft_txn,0)>0 then 1 else 0 end as leap_aft_txn,
b.gpt_1st_category_l2_index,
b.honey_store_name
from pypl-edw.pp_scratch.tmp_offers_output_dedup_archive a
JOIN {bq_prefix}live_unique_merchants_train b
on a.pp_merchant_id=b.encrypt_id
where evnt_dt >= {config['driver_config']['train_start_date']}
and placement in ('deals_explore_tertiary','ql_home','rewards_zone_new','reboarding')
and cust_id is not null
and cust_id<>'na'
and cust_id<>'no_cust_id'
and pp_merchant_id is not null
and saves_imp_unique_cnt>0;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_0 ;
create table {bq_prefix}driver_0 as
with temp as (
select cust_id,count(distinct placement) as cnt_placement
from {bq_prefix}driver_00
group by 1
)
select * from {bq_prefix}driver_00
where cust_id in (
select distinct cust_id from temp
where cnt_placement>1
)
union all
select * from {bq_prefix}driver_00
where cust_id in (
select distinct cust_id from temp
where cnt_placement=1
)
and (save>0 or leap_aft_txn>0);
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_1;
create table {bq_prefix}driver_1 as
SELECT
a.payment_transid,
a.tran_customer_id as cust_id,
a.customer_counterparty as rcvr_id,
a.transaction_created_date-1 as run_date,
b.gpt_1st_category_l2_index,
b.honey_store_name
FROM pypl-edw.pp_access_views.dw_payment_sent a
JOIN {bq_prefix}live_unique_merchants_train b
on a.customer_counterparty=b.rcvr_id
where tran_customer_id in (select distinct cust_id from {bq_prefix}driver_0)
and customer_counterparty in (select distinct rcvr_id from {bq_prefix}live_unique_merchants_train)
and transaction_created_date >= {config['driver_config']['train_start_date']}
and transaction_status='S';
"""
# %ppbq $q
# # Positive Samples
q=f"""drop table if exists {bq_prefix}driver_positive_train_attributed;
create table {bq_prefix}driver_positive_train_attributed as
WITH t1 as (
SELECT * FROM {bq_prefix}driver_0
WHERE leap_aft_txn>0
AND run_date<{config['driver_config']['oot_start_date']}),
t2 as (
SELECT count(*) as total_cnt
FROM {bq_prefix}driver_0
WHERE leap_aft_txn>0
AND run_date<{config['driver_config']['oot_start_date']}
),
t3 as (
SELECT rcvr_id,count(*) as cnt
FROM {bq_prefix}driver_0
WHERE leap_aft_txn>0
AND run_date<{config['driver_config']['oot_start_date']}
GROUP BY 1
),
t4 as (
SELECT
t3.rcvr_id,
t3.cnt/t2.total_cnt as merchant_ratio,
(SQRT(t3.cnt/t2.total_cnt/{config['driver_config']['training_hot_positive_attributed_txn_sampling_alpha']})+1)*{config['driver_config']['training_hot_positive_attributed_txn_sampling_alpha']}*t2.total_cnt/t3.cnt as merchant_sampling_ratio
FROM t3
JOIN t2
ON 1=1
),
t5 as (
SELECT t1.*,t4,merchant_ratio,t4.merchant_sampling_ratio
FROM t1
JOIN t4
ON t1.rcvr_id=t4.rcvr_id
),
t6 as (
SELECT *
FROM t5
WHERE RAND()<=merchant_sampling_ratio
)
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,merchant_ratio,merchant_sampling_ratio,
'attributed_txn' as pos_tag_type,
case when run_date<{config['driver_config']['val_start_date']} then 'train' else 'val' end as split
FROM t6
CROSS JOIN UNNEST(GENERATE_ARRAY(1,{config['driver_config']['training_attributed_txn_upsampling_rate']})) AS repeat
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_positive_train_organic_0;
create table {bq_prefix}driver_positive_train_organic_0 as
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index
FROM {bq_prefix}driver_1
WHERE CONCAT(cust_id,rcvr_id) not in (
select distinct concat(cust_id,rcvr_id) from {bq_prefix}driver_0 where leap_aft_txn>0
)
AND CONCAT(cust_id,rcvr_id) not in (
select distinct concat(cust_id,rcvr_id) from {bq_prefix}driver_0 where save>0
)
AND run_date<{config['driver_config']['oot_start_date']}
AND cust_id in (
SELECT distinct cust_id from (
SELECT cust_id,count(distinct payment_transid)
FROM {bq_prefix}driver_1
GROUP BY 1
HAVING count(distinct payment_transid)<{config['driver_config']['removing_highly_active_user_threshold']} -- remove highly active user's bias
)
)
AND concat(cust_id,rcvr_id) in (
SELECT concat(cust_id,rcvr_id) from (
SELECT cust_id,rcvr_id,count(distinct payment_transid)
FROM {bq_prefix}driver_1
GROUP BY 1,2
HAVING count(distinct payment_transid)<{config['driver_config']['removing_highly_active_user_merchant_threshold']} -- remove highly active user-merchant pairs bias
)
)
AND concat(cust_id,rcvr_id,run_date) in (
SELECT concat(cust_id,rcvr_id,run_date) from (
SELECT cust_id,rcvr_id,run_date,count(distinct payment_transid)
FROM {bq_prefix}driver_1
GROUP BY 1,2,3
HAVING count(distinct payment_transid)<{config['driver_config']['removing_highly_active_user_merchant_date_threshold']} -- remove highly active user-merchant-date bias
)
);
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_positive_train_organic;
create table {bq_prefix}driver_positive_train_organic as
WITH t1 as (
SELECT *
FROM {bq_prefix}driver_positive_train_organic_0),
t2 as (
SELECT count(*) as total_cnt
FROM {bq_prefix}driver_positive_train_organic_0
),
t3 as (
SELECT rcvr_id,count(*) as cnt
FROM {bq_prefix}driver_positive_train_organic_0
GROUP BY 1
),
t4 as (
SELECT
t3.rcvr_id,
t3.cnt/t2.total_cnt as merchant_ratio,
(SQRT(t3.cnt/t2.total_cnt/{config['driver_config']['training_hot_positive_organic_txn_sampling_alpha']})+1)*{config['driver_config']['training_hot_positive_organic_txn_sampling_alpha']}*t2.total_cnt/t3.cnt as merchant_sampling_ratio
FROM t3
JOIN t2
ON 1=1
),
t5 as (
SELECT t1.*,t4,merchant_ratio,t4.merchant_sampling_ratio
FROM t1
JOIN t4
ON t1.rcvr_id=t4.rcvr_id
),
t6 as (
SELECT *
FROM t5
WHERE RAND()<=merchant_sampling_ratio
)
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,merchant_ratio,merchant_sampling_ratio,
'pure_organirc_txn' as pos_tag_type,
case when run_date<{config['driver_config']['val_start_date']} then 'train' else 'val' end as split
FROM t6;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_positive;
create table {bq_prefix}driver_positive as
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,pos_tag_type,split
FROM {bq_prefix}driver_positive_train_attributed
UNION ALL
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,'attributed_txn' as pos_tag_type,'oot' as split
FROM {bq_prefix}driver_0
WHERE leap_aft_txn>0
AND run_date>={config['driver_config']['oot_start_date']}
UNION ALL
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,'save' as pos_tag_type,'train' as split
FROM {bq_prefix}driver_0
WHERE save>0
AND run_date<{config['driver_config']['oot_start_date']}
AND rand()<{config['driver_config']['save_label_mixing_rate']}
UNION ALL
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,'save' as pos_tag_type,'oot' as split
FROM {bq_prefix}driver_0
WHERE save>0
AND run_date>={config['driver_config']['oot_start_date']}
UNION ALL
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,pos_tag_type,split
FROM {bq_prefix}driver_positive_train_organic
UNION ALL
SELECT cust_id,rcvr_id,run_date,gpt_1st_category_l2_index,'pure_organirc_txn' as pos_tag_type,'oot' as split
FROM {bq_prefix}driver_1
WHERE CONCAT(cust_id,rcvr_id) not in (select distinct concat(cust_id,rcvr_id)
from {bq_prefix}driver_0 where leap_aft_txn>0)
AND CONCAT(cust_id,rcvr_id) not in (select distinct concat(cust_id,rcvr_id)
from {bq_prefix}driver_0 where save>0)
AND run_date>={config['driver_config']['oot_start_date']};
"""
#