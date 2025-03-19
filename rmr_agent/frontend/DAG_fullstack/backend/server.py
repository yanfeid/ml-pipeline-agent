from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yaml
from pydantic import BaseModel

app = FastAPI()

# allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# config for path
ORIGINAL_YAML = "original_dag.yaml"      # keep the origin version in case of missing data
VERIFIED_YAML = "verified_yaml.yaml"      # write in the file while changing

# load verified_yaml file
def load_verified_yaml():
    with open(VERIFIED_YAML, "r") as file:
        return yaml.safe_load(file)

# load origin YAML file
def load_original_yaml():
    with open(ORIGINAL_YAML, "r") as file:
        return yaml.safe_load(file)

# define data format
class DAGUpdateRequest(BaseModel):
    dag_yaml: str

@app.get("/get-dag")
def get_dag():
    """return updated DAG(verified_yaml)"""
    return load_verified_yaml()

@app.get("/get-original-dag")
def get_original_dag():
    """return original DAG, will not be updated"""
    return load_original_yaml()

@app.post("/update-dag")
def update_dag(request: DAGUpdateRequest):
    dag_data = yaml.safe_load(request.dag_yaml)
    # update verified DAG file
    with open(VERIFIED_YAML, "w") as file:
        yaml.dump(dag_data, file)
    return {"message": "verified DAG is saved!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
