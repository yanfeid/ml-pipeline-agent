cd rmr_agent

export PYTHONPATH="/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent"

python3 rmr_agent/workflow.py \
  --github-url "https://github.paypal.com/GADS-Consumer-ML/ql-store-recommendation-prod.git" \
  --input-files "research/pipeline/00_driver.ipynb" "research/pipeline/01_bq_feat.ipynb" "research/pipeline/01_varmart_feat.ipynb" "research/pipeline/02_combine.ipynb" "research/pipeline/03_prepare_training_data.ipynb" "research/pipeline/04_training.ipynb" "research/pipeline/05_scoring_oot.ipynb" "research/pipeline/06_evaluation.ipynb" \
  --run-id 4 \
  --start-from config_agent \
