from rmr_config.simple_config import Config
from rmr_config.state_manager import StateManager
import os
from datetime import datetime
from pathlib import Path

if "working_path" not in globals():
    path = Path(os.getcwd())
    working_path = path.parent.absolute()

folder = os.getcwd()
username = os.environ['NB_USER']
params_path = os.path.join(working_path, 'config')
config = Config(params_path)
local_base_path = config.get("general", "local_output_base_path")
os.makedirs(local_base_path, exist_ok=True)

# set working directory
os.chdir(working_path)
if not config:
    raise ValueError('config is not correctly setup')

print(f'username={username}, working_path={working_path}')

# Section Name
section_name = "feature_consolidation"

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
driver_dev_features_table = config.get(section_name, 'driver_dev_features_table')
driver_oot_features_expand_seq_table = config.get(section_name, 'driver_oot_features_expand_seq_table')
driver_oot_features_table = config.get(section_name, 'driver_oot_features_table')
export_uri = config.get(section_name, 'export_uri')

# === Research Code ===
q = f"""drop table if exists {bq_prefix}driver_dev_features;
create table {bq_prefix}driver_dev_features as
SELECT
t.*,
COALESCE(sndr_rcvr_txn_num_30d,0) AS sndr_rcvr_txn_num_30d,
COALESCE(sndr_rcvr_txn_num_180d,0) AS sndr_rcvr_txn_num_180d,
COALESCE(sndr_rcvr_txn_num_365d,0) AS sndr_rcvr_txn_num_365d,
COALESCE(sndr_rcvr_txn_amt_30d,0) AS sndr_rcvr_txn_amt_30d,
COALESCE(sndr_rcvr_txn_amt_180d,0) AS sndr_rcvr_txn_amt_180d,
COALESCE(sndr_rcvr_txn_amt_365d,0) AS sndr_rcvr_txn_amt_365d,
COALESCE(sndr_last_5_txn_avg_amt,0) AS sndr_last_5_txn_avg_amt,
COALESCE(sndr_last_10_txn_avg_amt,0) AS sndr_last_10_txn_avg_amt,
COALESCE(sndr_most_recent_100_merch_list,'0') as sndr_most_recent_100_merch_list,
COALESCE(sndr_most_recent_100_merch_category,'0') as sndr_most_recent_100_merch_category,
COALESCE(sndr_rcvr_category_breadth_30d,0) AS sndr_rcvr_category_breadth_30d,
COALESCE(sndr_rcvr_category_breadth_180d,0) AS sndr_rcvr_category_breadth_180d,
COALESCE(sndr_rcvr_category_breadth_365d,0) AS sndr_rcvr_category_breadth_365d,
COALESCE(sndr_rcvr_category_txn_num_30d,0) AS sndr_rcvr_category_txn_num_30d,
COALESCE(sndr_rcvr_category_txn_num_180d,0) AS sndr_rcvr_category_txn_num_180d,
COALESCE(sndr_rcvr_category_txn_num_365d,0) AS sndr_rcvr_category_txn_num_365d,
COALESCE(sndr_rcvr_category_txn_amt_30d,0) AS sndr_rcvr_category_txn_amt_30d,
COALESCE(sndr_rcvr_category_txn_amt_180d,0) AS sndr_rcvr_category_txn_amt_180d,
COALESCE(sndr_rcvr_category_txn_amt_365d,0) AS sndr_rcvr_category_txn_amt_365d,
COALESCE(sndr_rcvr_category_avg_txn_amt_30d,0) AS sndr_rcvr_category_avg_txn_amt_30d,
COALESCE(sndr_rcvr_category_avg_txn_amt_180d,0) AS sndr_rcvr_category_avg_txn_amt_180d,
COALESCE(sndr_rcvr_category_avg_txn_amt_365d,0) AS sndr_rcvr_category_avg_txn_amt_365d,
COALESCE(sndr_1st_freq_merchant_category_30d, 0) AS sndr_1st_freq_merchant_category_30d,
COALESCE(sndr_2nd_freq_merchant_category_30d, 0) AS sndr_2nd_freq_merchant_category_30d,
COALESCE(sndr_3rd_freq_merchant_category_30d, 0) AS sndr_3rd_freq_merchant_category_30d,
COALESCE(sndr_1st_freq_merchant_category_180d, 0) AS sndr_1st_freq_merchant_category_180d,
COALESCE(sndr_2nd_freq_merchant_category_180d, 0) AS sndr_2nd_freq_merchant_category_180d,
COALESCE(sndr_3rd_freq_merchant_category_180d, 0) AS sndr_3rd_freq_merchant_category_180d,
COALESCE(sndr_1st_freq_merchant_category_365d, 0) AS sndr_1st_freq_merchant_category_365d,
COALESCE(sndr_2nd_freq_merchant_category_365d, 0) AS sndr_2nd_freq_merchant_category_365d,
COALESCE(sndr_3rd_freq_merchant_category_365d, 0) AS sndr_3rd_freq_merchant_category_365d,
COALESCE(sndr_1st_freq_merchant_category_cnt_30d, 0) AS sndr_1st_freq_merchant_category_cnt_30d,
COALESCE(sndr_2nd_freq_merchant_category_cnt_30d, 0) AS sndr_2nd_freq_merchant_category_cnt_30d,
COALESCE(sndr_3rd_freq_merchant_category_cnt_30d, 0) AS sndr_3rd_freq_merchant_category_cnt_30d,
COALESCE(sndr_1st_freq_merchant_category_cnt_180d, 0) AS sndr_1st_freq_merchant_category_cnt_180d,
COALESCE(sndr_2nd_freq_merchant_category_cnt_180d, 0) AS sndr_2nd_freq_merchant_category_cnt_180d,
COALESCE(sndr_3rd_freq_merchant_category_cnt_180d, 0) AS sndr_3rd_freq_merchant_category_cnt_180d,
COALESCE(sndr_1st_freq_merchant_category_cnt_365d, 0) AS sndr_1st_freq_merchant_category_cnt_365d,
COALESCE(sndr_2nd_freq_merchant_category_cnt_365d, 0) AS sndr_2nd_freq_merchant_category_cnt_365d,
COALESCE(sndr_3rd_freq_merchant_category_cnt_365d, 0) AS sndr_3rd_freq_merchant_category_cnt_365d,
COALESCE(rcvr_avg_price_30d,0) AS rcvr_avg_price_30d,
COALESCE(rcvr_price_10_penentile_30d,0) AS rcvr_price_10_penentile_30d,
COALESCE(rcvr_price_30_penentile_30d,0) AS rcvr_price_30_penentile_30d,
COALESCE(rcvr_price_50_penentile_30d,0) AS rcvr_price_50_penentile_30d,
COALESCE(rcvr_price_70_penentile_30d,0) AS rcvr_price_70_penentile_30d,
COALESCE(rcvr_price_90_penentile_30d,0) AS rcvr_price_90_penentile_30d,
COALESCE(rcvr_rcvd_txn_num_30d,0) AS rcvr_rcvd_txn_num_30d,
COALESCE(rcvr_rcvd_distinct_consumer_num_30d,0) AS rcvr_rcvd_distinct_consumer_num_30d,
COALESCE(rcvr_rcvd_txn_amt_30d,0) AS rcvr_rcvd_txn_amt_30d,
ABS(COALESCE(sndr_last_1_txn_amt,0)-COALESCE(rcvr_avg_price_30d,0)) AS sndr_last_1_txn_avg_amt_rcvr_avg_price_diff,
ABS(COALESCE(sndr_last_1_txn_amt,0)-COALESCE(rcvr_price_50_penentile_30d,0)) AS sndr_last_1_txn_avg_amt_rcvr_median_price_diff,
ABS(COALESCE(sndr_last_5_txn_avg_amt,0)-COALESCE(rcvr_avg_price_30d,0)) AS sndr_last_5_txn_avg_amt_rcvr_avg_price_diff,
ABS(COALESCE(sndr_last_5_txn_avg_amt,0)-COALESCE(rcvr_price_50_penentile_30d,0)) AS sndr_last_5_txn_avg_amt_rcvr_median_price_diff,
ABS(COALESCE(sndr_last_10_txn_avg_amt,0)-COALESCE(rcvr_avg_price_30d,0)) AS sndr_last_10_txn_avg_amt_rcvr_avg_price_diff,
ABS(COALESCE(sndr_last_10_txn_avg_amt,0)-COALESCE(rcvr_price_50_penentile_30d,0)) AS sndr_last_10_txn_avg_amt_rcvr_median_price_diff,
COALESCE(sndr_rcvr_num_save_7day,0) AS sndr_rcvr_num_save_7day,
COALESCE(sndr_rcvr_num_save_30day,0) AS sndr_rcvr_num_save_30day,
COALESCE(sndr_rcvr_num_save_180day,0) AS sndr_rcvr_num_save_180day,
COALESCE(sndr_num_save_7day,0) AS sndr_num_save_7day,
COALESCE(sndr_num_save_30day,0) AS sndr_num_save_30day,
COALESCE(sndr_num_save_180day,0) AS sndr_num_save_180day,
COALESCE(sndr_rcvr_num_sameindustry_save_7day, 0) AS sndr_rcvr_num_sameindustry_save_7day,
COALESCE(sndr_rcvr_num_sameindustry_save_30day, 0) AS sndr_rcvr_num_sameindustry_save_30day,
COALESCE(sndr_rcvr_num_sameindustry_save_180day, 0) AS sndr_rcvr_num_sameindustry_save_180day,
COALESCE(rcvr_save_cnt_30d, 0) AS rcvr_save_cnt_30d,
COALESCE(rcvr_save_cnt_deals_explore_tertiary_30d,0) AS rcvr_save_cnt_deals_explore_tertiary_30d,
COALESCE(rcvr_save_cnt_ql_home_30d,0) AS rcvr_save_cnt_ql_home_30d,
COALESCE(rcvr_save_cnt_rewards_zone_new_30d,0) AS rcvr_save_cnt_rewards_zone_new_30d,
COALESCE(rcvr_save_cnt_reboarding_30d,0) AS rcvr_save_cnt_reboarding_30d,
COALESCE(rcvr_save_cnt_high_engaged_30d,0) AS rcvr_save_cnt_high_engaged_30d,
COALESCE(rcvr_save_cnt_mid_engaged_30d,0) AS rcvr_save_cnt_mid_engaged_30d,
COALESCE(rcvr_save_cnt_low_engaged_30d,0) AS rcvr_save_cnt_low_engaged_30d,
COALESCE(rcvr_save_cnt_likely_to_churn_30d,0) AS rcvr_save_cnt_likely_to_churn_30d,
COALESCE(rcvr_save_cnt_new_not_active_30d,0) AS rcvr_save_cnt_new_not_active_30d,
COALESCE(rcvr_save_cnt_never_active_30d,0) AS rcvr_save_cnt_never_active_30d,
COALESCE(rcvr_save_cnt_churned_30d,0) AS rcvr_save_cnt_churned_30d,
COALESCE(rcvr_save_cnt_re_engaged_30d,0) AS rcvr_save_cnt_re_engaged_30d,
COALESCE(rcvr_save_cnt_new_active_30d,0) AS rcvr_save_cnt_new_active_30d,
COALESCE(gender,'unknown') as gender,
COALESCE(score_transformed,0) as rcvr_tpv_score,
COALESCE(consu_engagmnt_seg_key,0) as sndr_consu_engagmnt_seg_key,
COALESCE(days_on_file,0) as sndr_days_on_file,
COALESCE(ebay_member_y_n,'unknown') as sndr_ebay_member_y_n,
COALESCE(prmry_cc_type_code,'#') as sndr_prmry_cc_type_code,
COALESCE(prmry_addr_state,'#') as sndr_prmry_addr_state,
COALESCE(days_appweb_visit,0) as sndr_days_appweb_visit,
COALESCE(consu_age_band_key,-99) as sndr_consu_age_band_key,
COALESCE(consu_dmgrphc_seg_key,-99) as sndr_consu_dmgrphc_seg_key,
COALESCE(embedding_1,0) AS embedding_1,
COALESCE(embedding_2,0) AS embedding_2,
COALESCE(embedding_3,0) AS embedding_3,
COALESCE(embedding_4,0) AS embedding_4,
COALESCE(embedding_5,0) AS embedding_5,
COALESCE(embedding_6,0) AS embedding_6,
COALESCE(embedding_7,0) AS embedding_7,
COALESCE(embedding_8,0) AS embedding_8,
COALESCE(embedding_9,0) AS embedding_9,
COALESCE(embedding_10,0) AS embedding_10,
COALESCE(embedding_11,0) AS embedding_11,
COALESCE(embedding_12,0) AS embedding_12,
COALESCE(embedding_13,0) AS embedding_13,
COALESCE(embedding_14,0) AS embedding_14,
COALESCE(embedding_15,0) AS embedding_15,
COALESCE(embedding_16,0) AS embedding_16,
COALESCE(embedding_17,0) AS embedding_17,
COALESCE(embedding_18,0) AS embedding_18,
COALESCE(embedding_19,0) AS embedding_19,
COALESCE(embedding_20,0) AS embedding_20,
COALESCE(embedding_21,0) AS embedding_21,
COALESCE(embedding_22,0) AS embedding_22,
COALESCE(embedding_23,0) AS embedding_23,
COALESCE(embedding_24,0) AS embedding_24,
COALESCE(embedding_25,0) AS embedding_25,
COALESCE(embedding_26,0) AS embedding_26,
COALESCE(embedding_27,0) AS embedding_27,
COALESCE(embedding_28,0) AS embedding_28,
COALESCE(embedding_29,0) AS embedding_29,
COALESCE(embedding_30,0) AS embedding_30,
COALESCE(embedding_31,0) AS embedding_