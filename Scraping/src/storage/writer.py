import os
import json
import pandas as pd
from typing import List, Union
from pydantic import BaseModel

def save_dataset(records: List[Union[BaseModel, dict]], base_dir: str, file_prefix: str) -> dict:
    """
    Saves a dataset of Pydantic models or dicts into CSV, JSONL, and Parquet formats.
    Creates target directory if it does not exist.
    """
    if not records:
        return {}

    os.makedirs(base_dir, exist_ok=True)
    
    # Convert Pydantic objects or dicts to a list of flat dicts
    flat_records = []
    for r in records:
        if isinstance(r, BaseModel):
            # Model dump handles standard datatypes
            data = r.model_dump()
        else:
            data = r
        
        # Format lists/dicts to json strings for CSV/Parquet columns compatibility if necessary,
        # but pandas can handle simple nested data for JSONL, while for Parquet/CSV it is better to serialize
        processed_data = {}
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                processed_data[k] = json.dumps(v, ensure_ascii=False)
            else:
                processed_data[k] = v
        flat_records.append(processed_data)

    df = pd.DataFrame(flat_records)
    
    # File paths
    csv_path = os.path.join(base_dir, f"{file_prefix}.csv")
    jsonl_path = os.path.join(base_dir, f"{file_prefix}.jsonl")
    parquet_path = os.path.join(base_dir, f"{file_prefix}.parquet")
    
    # Write CSV
    df.to_csv(csv_path, index=False, encoding="utf-8")
    
    # Write JSONL
    # For JSONL, we write the original (potentially nested) data for maximum readability
    jsonl_records = [r.model_dump() if isinstance(r, BaseModel) else r for r in records]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for item in jsonl_records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    # Write Parquet
    df.to_parquet(parquet_path, index=False, engine="pyarrow")
    
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "parquet": parquet_path,
        "count": len(df)
    }
