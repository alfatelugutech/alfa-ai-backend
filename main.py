from fastapi import FastAPI
import pandas as pd

app = FastAPI()

@app.get("/")
def read_root():
    df = pd.DataFrame({"msg": ["Hello, world!"]})
    return {"result": df.to_dict()}
