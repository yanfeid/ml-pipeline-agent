component_specific_hints = {
    "Driver Creation": [
        "Focus on major inputs like raw data paths (e.g., BigQuery table paths) and SQL query parameters",
        "Output is the final driver dataset, typically saved to GCS (e.g. parquet, CSV)",
        "The 'driver' dataset contains the basic rows and metadata (e.g. class labels (0, 1), class weights, split category (train, val, test/OOT)).",
        "Sometimes the different splits (train, validation, OOT (test)) will be saved in separate tables/datasets. Ensure to include all of these in the output if they are separate."
        "Intermediate table results should not be included. Focus on the major inputs and final output of the entire driver creation process.",
        "The final driver dataset will typically be saved to GCS (e.g. parquet, PIG, CSV)"
    ],
    "Feature Engineering": [
        "Inputs include driver dataset (BigQuery table or GCS path) and SQL query parameters for transformations",
        "Outputs are engineered feature sets, often saved to BigQuery or GCS",
        "Look for aggregation or transformation parameters (e.g., window sizes, group-by keys)"
    ],
    "Data Pulling": [
        "Inputs include driver dataset path and feature store API parameters (e.g., for Data Fetcher, PyOFS, QPull, MadMen, PyDPU, mdlc.dataset)",
        "Data Fetcher produces its output in data_loc"
        ],
    "Feature Consolidation": [
        "Inputs are multiple dataset paths to merge",
        "Output is a unified feature set, often saved to GCS",
        "Intermediate table results should not be included. Focus on the major inputs and final output"
        "Look for join keys or merge parameters"
    ],
    "Data Preprocessing": [
        "Inputs include feature set path and transformation parameters (e.g., imputation method, scaling factors)",
        "Outputs include cleaned/transformed data path and preprocessor save paths",
        "Look for Shifu library usage or WOE/normalization parameters",
        "Shifu runs normalization through the eval() method with the '-norm' flag set. The resulting normalized dataset will be located in the `hdfsModelSetPath` if specified"
    ],
    "Feature Selection": [
        "Input is train dataset path(s), candidate feature lists, meta feature lists, target column lists, etc.",
        "Outputs include final variable list path and optional feature importance path",
        "Look for Shifu or model_automation calls"
    ],
    "TFRecord Conversion": [
        "Input is normalized train/validation data paths",
        "Output is TFRecord file paths (typically on GCS)",
        "Look for Dataproc job submission parameters or tfrecord conversion function args"
    ],
    "Model Training": [
        "Inputs include training data path (potentially normalized data paths or tfrecord paths), hyperparameters (e.g., learning_rate, n_estimators), and training params (e.g., epochs, batch_size)",
        "Output is model artifact path using library-specific formats (e.g., .h5, .tf, .model, .pt, .txt, .json on local or GCS)",
        "Note that Model Packaging to formats such as UME and ONNX is considered a separate component from Model Training, so do not include them here"
    ],
    "Model Packaging": [
        "Input is trained model path (e.g., 'gs://bucket/model.h5') and optional preprocessing logic (e.g., Shifu path, saved preprocessor paths)",
        "Output is deployment-ready model path (e.g., ONNX, UME)",
    ],
    "Model Scoring": [
        "Inputs include model path and test/OOT data path",
        "Output is scored data path",
        "Look for PyScoring tool usage"
    ],
    "Model Evaluation": [
        "Input is scored data path or model predictions",
        "Output is final performance metrics path",
        "Look for metric calculation parameters (e.g., threshold, metric names)"
    ],
    "Model Deployment": [
        "Input is packaged model path",
        # should specify some output hint here, not sure at the moment. Many times research code does not include the deployment code - they do it manually elsewhere or through UI for example. 
    ]
}