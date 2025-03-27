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
section_name = "feature_engineering"

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
driver_consumer_base_gender_table = config.get('section_name', 'driver_consumer_base_gender_table')

# Dependencies from Previous Sections

# === Research Code ===
q=f"""drop table if exists {bq_prefix}driver_simu_txn_365d;
create table {bq_prefix}driver_simu_txn_365d as
select a.*,
date_sub(cast(a.run_date as DATE),INTERVAL 7 DAY) as run_date_7d,
date_sub(cast(a.run_date as DATE),INTERVAL 30 DAY) as run_date_30d,
date_sub(cast(a.run_date as DATE),INTERVAL 180 DAY) as run_date_180d,
date_sub(cast(a.run_date as DATE),INTERVAL 365 DAY) as run_date_365d,
b.payment_transid,b.transaction_created_date,b.transaction_usd_equiv_amt
from {bq_prefix}driver_simu a
join (
select payment_transid,
tran_customer_id,
customer_counterparty,
transaction_created_date,
transaction_created_ts,
-0.01*transaction_usd_equiv_amt as transaction_usd_equiv_amt
from pypl-edw.pp_access_views.dw_payment_sent
where transaction_status='S'
and transaction_created_date >= date_sub({config['driver_config']['train_start_date']},INTERVAL 365 DAY)
)b
on a.cust_id = b.tran_customer_id
and a.rcvr_id = b.customer_counterparty
and a.run_date>b.transaction_created_date
qualify row_number() over (partition by payment_transid order by transaction_created_ts desc)=1;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_simu_txn_365d_agg;
create table {bq_prefix}driver_simu_txn_365d_agg as
select cust_id,rcvr_id,run_date
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_7d then 1 else 0 end) as sndr_rcvr_txn_num_7d
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_30d then 1 else 0 end) as sndr_rcvr_txn_num_30d
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_180d then 1 else 0 end) as sndr_rcvr_txn_num_180d
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_365d then 1 else 0 end) as sndr_rcvr_txn_num_365d
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_7d then transaction_usd_equiv_amt else 0 end) as sndr_rcvr_txn_amt_7d
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_30d then transaction_usd_equiv_amt else 0 end) as sndr_rcvr_txn_amt_30d
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_180d then transaction_usd_equiv_amt else 0 end) as sndr_rcvr_txn_amt_180d
,sum(case when transaction_created_date<cast(run_date as DATE) and transaction_created_date>run_date_365d then transaction_usd_equiv_amt else 0 end) as sndr_rcvr_txn_amt_365d
from {bq_prefix}driver_simu_txn_365d
group by 1,2,3;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_consumer_base;
create table {bq_prefix}driver_consumer_base as
select
cust_id,cast(run_date as DATE) as run_date,
date_sub(cast(run_date as DATE),INTERVAL 30 DAY) as run_date_30d,
date_sub(cast(run_date as DATE),INTERVAL 180 DAY) as run_date_180d,
date_sub(cast(run_date as DATE),INTERVAL 365 DAY) as run_date_365d,
from {bq_prefix}driver_simu
group by 1,2,3,4,5;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_consumer_base_txn_5k_merch_category;
create table {bq_prefix}driver_consumer_base_txn_5k_merch_category as
select
a.*,b.customer_counterparty,b.payment_transid,b.transaction_created_date,b.transaction_created_ts,b.transaction_usd_equiv_amt,c.gpt_1st_category_l2_index,
row_number() over (partition by a.cust_id,a.run_date order by b.transaction_created_ts desc) as recency_rank
from {bq_prefix}driver_consumer_base a
join (
select payment_transid,
tran_customer_id,
customer_counterparty,
transaction_created_date,
transaction_created_ts,
-0.01*transaction_usd_equiv_amt as transaction_usd_equiv_amt,
from pypl-edw.pp_access_views.dw_payment_sent
where transaction_status='S'
and transaction_created_date >= date_sub({config['driver_config']['train_start_date']},INTERVAL 365 DAY)
and tran_customer_id in (select distinct cust_id from {bq_prefix}driver_consumer_base)
and customer_counterparty in (select distinct rcvr_id from {bq_prefix}live_unique_merchants_train)
qualify row_number() over (partition by payment_transid order by transaction_created_ts desc)=1
)b
on a.cust_id = b.tran_customer_id
and a.run_date>b.transaction_created_date
and a.run_date_365d<b.transaction_created_date
join {bq_prefix}live_unique_merchants_train c
on b.customer_counterparty=c.rcvr_id;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_consumer_base_last_10_txn;
create table  {bq_prefix}driver_consumer_base_last_10_txn as
select
a.cust_id,a.run_date
,COALESCE(last_1.transaction_usd_equiv_amt,0) as sndr_last_1_txn_amt
,(COALESCE(last_1.transaction_usd_equiv_amt,0)
+COALESCE(last_2.transaction_usd_equiv_amt,0)
+COALESCE(last_3.transaction_usd_equiv_amt,0)
+COALESCE(last_4.transaction_usd_equiv_amt,0)
+COALESCE(last_5.transaction_usd_equiv_amt,0)
)/(
IF(last_1.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_2.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_3.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_4.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_5.transaction_usd_equiv_amt IS NOT NULL, 1, 0)+1.0
) as sndr_last_5_txn_avg_amt
,(COALESCE(last_1.transaction_usd_equiv_amt,0)
+COALESCE(last_2.transaction_usd_equiv_amt,0)
+COALESCE(last_3.transaction_usd_equiv_amt,0)
+COALESCE(last_4.transaction_usd_equiv_amt,0)
+COALESCE(last_5.transaction_usd_equiv_amt,0)
+COALESCE(last_6.transaction_usd_equiv_amt,0)
+COALESCE(last_7.transaction_usd_equiv_amt,0)
+COALESCE(last_8.transaction_usd_equiv_amt,0)
+COALESCE(last_9.transaction_usd_equiv_amt,0)
+COALESCE(last_10.transaction_usd_equiv_amt,0)
)/(
IF(last_1.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_2.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_3.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_4.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_5.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_6.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_7.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_8.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_9.transaction_usd_equiv_amt IS NOT NULL, 1, 0)
+IF(last_10.transaction_usd_equiv_amt IS NOT NULL, 1, 0)+1.0
) as sndr_last_10_txn_avg_amt
from {bq_prefix}driver_consumer_base a
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=1
) last_1 on a.cust_id=last_1.cust_id and a.run_date=last_1.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=2
) last_2 on a.cust_id=last_2.cust_id and a.run_date=last_2.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=3
) last_3 on a.cust_id=last_3.cust_id and a.run_date=last_3.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=4
) last_4 on a.cust_id=last_4.cust_id and a.run_date=last_4.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=5
) last_5 on a.cust_id=last_5.cust_id and a.run_date=last_5.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=6
) last_6 on a.cust_id=last_6.cust_id and a.run_date=last_6.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=7
) last_7 on a.cust_id=last_7.cust_id and a.run_date=last_7.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=8
) last_8 on a.cust_id=last_8.cust_id and a.run_date=last_8.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=9
) last_9 on a.cust_id=last_9.cust_id and a.run_date=last_9.run_date
left join (
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_usd_equiv_amt,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category where recency_rank=10
) last_10 on a.cust_id=last_10.cust_id and a.run_date=last_10.run_date;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_consumer_base_all_history_array_0;
create table  {bq_prefix}driver_consumer_base_all_history_array_0 as
select cust_id,run_date,customer_counterparty,transaction_created_date,transaction_created_ts,gpt_1st_category_l2_index
from
(select cust_id,run_date, customer_counterparty,transaction_created_date,transaction_created_ts,gpt_1st_category_l2_index
from {bq_prefix}driver_consumer_base_txn_5k_merch_category
)
qualify row_number() over (partition by cust_id,run_date order by transaction_created_ts desc)<=100;
"""
# %ppbq $q
q=f"""drop table if exists {bq_prefix}driver_consumer_base_all_history_array;
create table  {bq_prefix}driver_consumer_base_all_history_array as
select cust_id,run_date
,ARRAY_TO_STRING(ARRAY_AGG(COALESCE(customer_counterparty, '0') ORDER BY transaction_created_ts), ',') AS sndr_most_recent_100_merch_list
,ARRAY_TO_STRING(ARRAY_AGG(COALESCE(cast(gpt_1st_category_l2_index as string), '0') ORDER BY transaction_created_ts), ',') AS sndr_most_recent_100_merch_category
from {bq_prefix}driver_consumer_base_all_history_array_0
group by 1,2;
"""
# %ppbq $q
# # Category aggregation
q=f"""drop table if exists {bq_prefix}driver_combine_category;
create table  {bq_prefix}driver_combine_category as
select a.*,b.gpt_1st_category_l2_index as rcvr_gpt_1st_category_l